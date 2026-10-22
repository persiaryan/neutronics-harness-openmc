"""Prepare metadata-masked source review and validate separately declared reviews.

Only trusted AST parsing and byte copies occur. Candidate modules are never
imported or executed. Syntax is a review aid, never a mechanism verdict.
"""
import argparse
import ast
from collections import Counter, defaultdict
import json
from pathlib import Path
import random

import confirmation_closeout as closeout

STATUSES = ("pending", "demonstrated", "not_observed_within_reviewed_scope", "unassessable")
FIELDS = ("sharing", "mutation", "downstream_use", "damaging_consequence")
MUTATORS = {"append", "extend", "insert", "remove", "pop", "clear", "reverse",
            "sort", "__iand__", "__ior__", "__setitem__", "__delitem__", "__iadd__",
            "iand", "ior", "setitem", "delitem", "translate", "rotate",
            "remove_redundant_surfaces"}


def syntax_facts(source):
    """Return exhaustive named syntax locations, without claiming object types."""
    tree = ast.parse(source)
    facts = dict(augmented_region_syntax=[], mutating_calls=[], direct_aliases=[],
                 region_attribute_writes=[], dynamic_features=[], operator_mutator_references=[])
    for node in ast.walk(tree):
        if isinstance(node, ast.AugAssign) and isinstance(node.op, (ast.BitAnd, ast.BitOr)):
            facts["augmented_region_syntax"].append(dict(
                line=node.lineno, end_line=node.end_lineno, target=ast.unparse(node.target),
                operator="&=" if isinstance(node.op, ast.BitAnd) else "|=",
                value=ast.unparse(node.value)))
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in MUTATORS:
                facts["mutating_calls"].append(dict(
                    line=node.lineno, receiver=ast.unparse(node.func.value),
                    method=node.func.attr, expression=ast.unparse(node)))
            if isinstance(node.func, ast.Name) and node.func.id in (
                    "exec", "eval", "compile", "setattr", "delattr", "getattr", "__import__"):
                facts["dynamic_features"].append(dict(line=node.lineno, expression=ast.unparse(node)))
        if isinstance(node, ast.Delete):
            facts["region_attribute_writes"].append(dict(
                line=node.lineno, target=ast.unparse(node), value="deletion"))
        if isinstance(node, ast.Attribute) and node.attr in (
                "iand", "ior", "setitem", "delitem", "__iand__", "__ior__"):
            facts["operator_mutator_references"].append(dict(line=node.lineno, expression=ast.unparse(node)))
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(node.value, (ast.Name, ast.Subscript, ast.Attribute)):
                facts["direct_aliases"].append(dict(
                    line=node.lineno, targets=[ast.unparse(t) for t in targets],
                    value=ast.unparse(node.value)))
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in ("region", "node", "_node", "nodes", "_nodes"):
                    facts["region_attribute_writes"].append(dict(
                        line=node.lineno, target=ast.unparse(target), value=ast.unparse(node.value)))
                if isinstance(target, ast.Subscript):
                    facts["region_attribute_writes"].append(dict(
                        line=node.lineno, target=ast.unparse(target), value=ast.unparse(node.value)))
    for values in facts.values():
        values.sort(key=lambda v: v["line"])
    return facts


def receiver_bindings(source):
    """Describe named mutation receivers and lexical list definitions, not harm."""
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree)
               for child in ast.iter_child_nodes(parent)}

    def scope(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node
        return tree

    assignments = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assignments[(scope(node), target.id)].append(node)
    result = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in MUTATORS):
            continue
        receiver = node.func.value
        definitions, owner = [], scope(node)
        if isinstance(receiver, ast.Name):
            while True:
                definitions = assignments.get((owner, receiver.id), [])
                if definitions or owner is tree:
                    break
                owner = scope(owner)
        result.append(dict(line=node.lineno, receiver=ast.unparse(receiver),
                           method=node.func.attr,
                           lexical_list_definitions=[n.lineno for n in definitions
                               if isinstance(n.value, (ast.List, ast.ListComp))],
                           unresolved_receiver=(not definitions or any(
                               not isinstance(n.value, (ast.List, ast.ListComp))
                               for n in definitions))))
    return sorted(result, key=lambda r: r["line"])


def prepare(frozen, output):
    frozen, output = closeout.ordinary(frozen), closeout.ordinary(output)
    closeout.require(not output.exists(), "Review output already exists")
    seal, public = closeout.read(frozen / "seal.json"), closeout.read(frozen / "aggregate.json")
    closeout.require(not output.is_relative_to(frozen) and all(
        not output.is_relative_to(closeout.ROOT / r) for r in seal["roots"]),
        "Review output must stay outside original frozen evidence")
    closeout.require(closeout.sha(frozen / "aggregate.json") == seal["aggregate_sha256"]
                     and closeout.sha(frozen / "operator-map.json") == seal["operator_map_sha256"],
                     "Frozen closeout changed")
    mapping = {r["id"]: r for r in closeout.read(frozen / "operator-map.json")}
    rows = public["rows"]
    ordered = [r for r in rows if r["source_sha256"]]
    random.Random(20261022).shuffle(ordered)
    manifests = [closeout.ROOT / r / "manifest.json" for r in seal["roots"]]
    manifests = [p for p in manifests if p.is_file()
                 and closeout.sha(p) == public["campaign_manifest_sha256"]]
    closeout.require(len(manifests) == 1, "Frozen campaign manifest missing")
    original_manifest = closeout.read(manifests[0])
    closeout.require(closeout.sha(closeout.ROOT / "prompts/confirmation_v2/manifest.json")
                     == original_manifest["suite_manifest_sha256"], "Public suite changed")
    suite = closeout.read(closeout.ROOT / "prompts/confirmation_v2/manifest.json")
    specs = {r["id"]: r for r in suite["tasks"]}
    output.mkdir()
    packet = output / "anonymous-source-review"
    packet.mkdir()
    inventory, key, facts, records = [], [], [], []
    for index, row in enumerate(ordered, 1):
        ident = f"review-{index:03d}"
        directory = packet / ident
        directory.mkdir()
        source = closeout.ROOT / mapping[row["id"]]["task_path"] / "candidate.py"
        closeout.require(closeout.sha(source) == row["source_sha256"], "Submitted source changed")
        specification = closeout.ROOT / "prompts" / specs[row["case"]]["path"]
        closeout.require(closeout.sha(specification) == specs[row["case"]]["sha256"],
                         "Public task changed")
        raw = source.read_bytes()
        (directory / "candidate.py").write_bytes(raw)
        (directory / "public-task.md").write_bytes(specification.read_bytes())
        inventory.append(dict(id=ident, source_sha256=row["source_sha256"],
                              task_sha256=specs[row["case"]]["sha256"]))
        key.append(dict(review_id=ident, assignment=row["id"],
                        source_path=str(source.relative_to(closeout.ROOT))))
        facts.append(dict(id=row["id"], source_sha256=row["source_sha256"],
                          facts=syntax_facts(raw.decode())))
        records.append(dict(id=ident, status="pending", reviewer=None, reviewer_type=None,
                            source_sha256=row["source_sha256"], evidence=[], limitations=None,
                            **{field: None for field in FIELDS}))
    definition = closeout.read(closeout.ROOT / "experiments/region_ad_protocol.json")["secondary"]
    closeout.dump(packet / "inventory.json", inventory)
    closeout.dump(packet / "measurement-definition.json", definition)
    closeout.dump(packet / "review-template.json", dict(
        format="confirmation-masked-mechanism-review-v1",
        aggregate_sha256=seal["aggregate_sha256"], records=records))
    (packet / "README.md").write_text(
        "# Independent source review\n\n"
        "Review each unchanged candidate.py against public-task.md and the frozen "
        "measurement-definition.json. Do not execute candidate Python on the host.\n\n"
        "The packet omits assignment IDs, model/arm labels, outcomes, private references "
        "and assistant proposals. Source style can reveal clues: metadata masking does "
        "not guarantee blinding. The operator key and assistant draft are outside this packet.\n\n"
        "Complete all four causal-chain fields and source line references. An in-place "
        "operator alone is not a defect; no absence claim follows from its absence alone. "
        "Preserve uncertain cases as unassessable. A named human reviewer must supply "
        "human judgments. The importer validates declared provenance, not human identity.\n\n"
        "Record the initial review before consulting the public aggregate, operator key, or "
        "assistant draft. Source hashes can be joined to published metadata, and source "
        "style can suggest condition. The assistant pre-review was not blinded.\n")
    closeout.dump(output / "operator-key.json", key)
    closeout.dump(output / "syntax-facts.json", dict(
        format="confirmation-source-syntax-facts-v1", interpretation="not_mechanism_labels",
        records=sorted(facts, key=lambda v: v["id"])))
    closeout.dump(output / "source-review-index.json", dict(
        format="confirmation-mechanism-review-index-v1",
        aggregate_sha256=seal["aggregate_sha256"],
        anonymous_inventory_sha256=closeout.sha(packet / "inventory.json"),
        measurement_definition_sha256=closeout.sha(packet / "measurement-definition.json"),
        instructions_sha256=closeout.sha(packet / "README.md"),
        preparation_controller_sha256=closeout.sha(Path(__file__)),
        operator_key_sha256=closeout.sha(output / "operator-key.json"),
        syntax_facts_sha256=closeout.sha(output / "syntax-facts.json"),
        sources=len(ordered), missing_source_ids=[r["id"] for r in rows if not r["source_sha256"]],
        original_evidence_modified=False, candidate_execution=False))
    return dict(sources=len(ordered), missing=240-len(ordered), human_labels="pending")


def validate_record(record, source, reviewer_type):
    closeout.require(record["status"] in STATUSES, "Unknown mechanism status")
    closeout.require(record.get("source_sha256") == closeout.sha(source),
                     "Review source changed")
    if record["status"] == "pending":
        return
    closeout.require(record.get("reviewer_type") == reviewer_type,
                     "AI and declared human reviews must remain separate")
    closeout.require(isinstance(record.get("reviewer"), str) and record["reviewer"].strip(),
                     "Name the reviewer")
    closeout.require(isinstance(record.get("limitations"), str) and record["limitations"].strip(),
                     "Review coverage and limitations missing")
    if record["status"] == "unassessable":
        return
    for field in FIELDS:
        closeout.require(isinstance(record.get(field), str) and record[field].strip(),
                         "Incomplete causal chain: " + field)
    lines = len(source.read_text().splitlines())
    closeout.require(bool(record.get("evidence")), "Source evidence missing")
    for item in record["evidence"]:
        closeout.require(item.get("path") == "candidate.py"
                         and item.get("sha256") == record["source_sha256"],
                         "Only the unchanged packet source is admitted")
        interval = item.get("lines")
        closeout.require(isinstance(interval, list) and len(interval) == 2
                         and all(type(n) is int for n in interval)
                         and 1 <= interval[0] <= interval[1] <= lines,
                         "Invalid source evidence interval")


def verify_packet(prepared):
    index = closeout.read(prepared / "source-review-index.json")
    packet = prepared / "anonymous-source-review"
    closeout.require(closeout.sha(prepared / "operator-key.json") == index["operator_key_sha256"]
                     and closeout.sha(packet / "inventory.json")
                     == index["anonymous_inventory_sha256"], "Packet mapping changed")
    closeout.require(closeout.sha(packet / "measurement-definition.json")
                     == index["measurement_definition_sha256"]
                     and closeout.sha(packet / "README.md") == index["instructions_sha256"],
                     "Review criteria or instructions changed")
    inventory = closeout.read(packet / "inventory.json")
    closeout.require(len(inventory) == index["sources"]
                     and len({r["id"] for r in inventory}) == len(inventory),
                     "Duplicate anonymous source")
    for row in inventory:
        closeout.require(row["id"].startswith("review-")
                         and Path(row["id"]).name == row["id"],
                         "Anonymous source path changed")
        directory = packet / row["id"]
        closeout.require({p.name for p in directory.iterdir()} ==
                         {"candidate.py", "public-task.md"}, "Unexpected packet files")
        closeout.require(closeout.sha(directory / "candidate.py") == row["source_sha256"]
                         and closeout.sha(directory / "public-task.md") == row["task_sha256"],
                         "Review source or public specification changed")
    return index


def import_review(frozen, prepared, review_file, output, reviewer_type):
    frozen, prepared, review_file, output = (
        closeout.ordinary(p) for p in (frozen, prepared, review_file, output))
    closeout.require(reviewer_type in ("human", "ai"), "Declare reviewer type")
    closeout.require(not output.exists(), "Review result already exists")
    public = closeout.read(frozen / "aggregate.json")
    seal = closeout.read(frozen / "seal.json")
    index = verify_packet(prepared)
    closeout.require(not output.is_relative_to(frozen)
                     and not output.is_relative_to(prepared / "anonymous-source-review")
                     and all(not output.is_relative_to(closeout.ROOT / r) for r in seal["roots"]),
                     "Review import cannot write into frozen evidence or masked sources")
    closeout.require(closeout.sha(frozen / "aggregate.json") == seal["aggregate_sha256"]
                     == index["aggregate_sha256"], "Review study identity changed")
    closeout.require(closeout.sha(prepared / "operator-key.json") == index["operator_key_sha256"]
                     and closeout.sha(prepared / "anonymous-source-review/inventory.json")
                     == index["anonymous_inventory_sha256"], "Packet mapping changed")
    value = closeout.read(review_file)
    closeout.require(value["format"] == "confirmation-masked-mechanism-review-v1"
                     and value["aggregate_sha256"] == seal["aggregate_sha256"],
                     "Review binding changed")
    key = {r["review_id"]: r for r in closeout.read(prepared / "operator-key.json")}
    given = {r["id"]: r for r in value["records"]}
    closeout.require(len(given) == len(value["records"]) and set(given) == set(key),
                     "Review must cover exactly all submitted sources")
    mapped = {}
    for ident, binding in key.items():
        source = prepared / "anonymous-source-review" / ident / "candidate.py"
        record = given[ident]
        validate_record(record, source, reviewer_type)
        original = closeout.ROOT / binding["source_path"]
        closeout.require(closeout.sha(original) == closeout.sha(source),
                         "Packet differs from frozen submitted source")
        mapped[binding["assignment"]] = dict(record, id=binding["assignment"], review_id=ident)
    closeout.require(set(mapped) == {r["id"] for r in public["rows"] if r["source_sha256"]}
                     and len(mapped) == len(key), "Assignment mapping duplicated or incomplete")
    rows = []
    for row in public["rows"]:
        judgment = mapped.get(row["id"])
        closeout.require(judgment is None or judgment["source_sha256"] == row["source_sha256"],
                         "Review assigned to a different source")
        rows.append(dict(id=row["id"], model=row["model"], arm=row["arm"], case=row["case"],
                         primary_outcome=row["outcome"], source_sha256=row["source_sha256"],
                         judgment=judgment if judgment else dict(
                             status="unassessable", reason="no_final_submission")))
    groups = []
    for model in ("gpt-5.6-luna", "gpt-5.6-sol"):
        for arm in ("A", "D"):
            selected = [r for r in rows if (r["model"], r["arm"]) == (model, arm)]
            counts = Counter(r["judgment"]["status"] for r in selected)
            groups.append(dict(model=model, arm=arm, assigned=len(selected),
                               **{status: counts[status] for status in STATUSES}))
    result = dict(format="confirmation-mechanism-proposals-v1" if reviewer_type == "ai"
                  else "confirmation-declared-human-mechanism-review-v1",
                  aggregate_sha256=seal["aggregate_sha256"], reviewer_type=reviewer_type,
                  human_identity_authenticated=False,
                  mechanism_adjudication="pending" if reviewer_type == "ai" else "declared_human_review",
                  original_verdicts_modified=False, rows=rows, groups=groups)
    closeout.dump(output, result)
    return dict(rows=len(rows), groups=groups, reviewer_type=reviewer_type,
                scientific_primary_unchanged=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "import"))
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--reviewer-type", choices=("ai", "human"))
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.frozen, args.output)
    else:
        closeout.require(args.prepared and args.review and args.reviewer_type,
                         "Specify packet, review and reviewer type")
        result = import_review(args.frozen, args.prepared, args.review, args.output,
                               args.reviewer_type)
    print(json.dumps(result, sort_keys=True))
