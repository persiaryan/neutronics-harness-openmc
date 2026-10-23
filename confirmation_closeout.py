"""Freeze retained A/D outcomes without executing candidates or changing verdicts.

This operator-only entry point deliberately lives outside the campaign's frozen
source inventory. Public output is an explicit allowlist; full evidence stays local.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMMUTABLE = ("id", "model", "arm", "case", "repeat", "path", "plan_sha256")
OUTCOMES = ("protocol_success", "evaluated_failure", "unscored_incident")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ordinary(path, root=ROOT):
    path, root = Path(path).absolute(), Path(root).resolve()
    require(".." not in path.parts and path.is_relative_to(root),
            "Evidence path outside selected repository")
    for item in (path, *path.parents):
        if item == root.parent:
            break
        require(not item.is_symlink(), "Symlink evidence is not admitted")
    return path


def sha(path):
    h = sha256()
    with ordinary(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(ordinary(path).read_text())


def bound(value):
    path = ordinary(value["path"])
    require(sha(path) == value["sha256"], "Bound evidence changed")
    return path


def inventory(roots):
    values = {}
    for root in sorted(set(Path(p).absolute() for p in roots)):
        ordinary(root)
        require(root.is_dir(), "Evidence root missing")
        for path in sorted(root.rglob("*")):
            ordinary(path)
            if path.is_file():
                values[str(path.relative_to(ROOT))] = sha(path)
    return values


def outcome(row, verdict=None):
    if row["state"] == "incident":
        require(row.get("score") is None and row.get("strict_correct") is not True,
                "An incident cannot receive a score or success")
        if verdict is not None:
            require(verdict["evidence_status"] == "coherent"
                    and verdict["score"] is None and verdict["strict_correct"] is False,
                    "Unscored retained verdict changed")
        return "unscored_incident"
    require(row["state"] == "finished" and verdict is not None,
            "Expected a terminal assignment with retained verdict")
    require(verdict["evidence_status"] == "coherent"
            and verdict["score"] is not None
            and verdict["score"] == row["score"]
            and type(verdict["strict_correct"]) is bool
            and verdict["strict_correct"] == row["strict_correct"],
            "Progress contradicts retained verdict")
    return "protocol_success" if verdict["strict_correct"] else "evaluated_failure"


def aggregate(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["model"], row["arm"], row["case"])].append(row)
    cells = []
    for (model, arm, case), cell in sorted(groups.items()):
        counts = Counter(r["outcome"] for r in cell)
        cells.append(dict(model=model, arm=arm, case=case, assigned=len(cell),
                          **{k: counts[k] for k in OUTCOMES}))
    models = []
    for model in sorted({r["model"] for r in rows}):
        arms = {}
        for arm in ("A", "D"):
            selected = [r for r in rows if (r["model"], r["arm"]) == (model, arm)]
            counts = Counter(r["outcome"] for r in selected)
            arms[arm] = dict(assigned=len(selected), **{k: counts[k] for k in OUTCOMES})
        models.append(dict(model=model, arms=arms,
                           D_minus_A_success_fraction=(
                               arms["D"]["protocol_success"] / arms["D"]["assigned"]
                               - arms["A"]["protocol_success"] / arms["A"]["assigned"])))
    counts = Counter(r["outcome"] for r in rows)
    return dict(assigned=len(rows), **{k: counts[k] for k in OUTCOMES},
                by_model=models, by_task_model_arm=cells)


def collect(campaign):
    campaign = ordinary(Path(campaign).absolute())
    m, progress = read(campaign / "manifest.json"), read(campaign / "progress.json")
    require(progress["state"] == "complete" and len(progress["rows"]) == len(m["rows"]) == 240,
            "Closeout requires all 240 assignments consumed")
    require(sha(campaign / "manifest.json") ==
            (campaign / "manifest.sha256").read_text().strip(), "Manifest changed")
    require([r["id"] for r in progress["rows"]] == [f"{i:03d}" for i in range(1, 241)],
            "Assignment order changed")
    matrix = {(r["model"], r["arm"], r["case"], r["repeat"]) for r in progress["rows"]}
    cases = {r["case"] for r in m["rows"]}
    require(len(cases) == 12 and matrix == {
        (model, arm, case, repeat)
        for model in ("gpt-5.6-luna", "gpt-5.6-sol")
        for arm in ("A", "D") for case in cases for repeat in range(1, 6)},
        "Task/model/arm/repeat matrix changed")
    roots = {campaign}
    bindings = []
    continuation = m["continuation"]
    original = bound(continuation["original_manifest"]).parent
    migration = bound(continuation["revision"]).parent
    roots.update((original, migration))
    for name, block in m.items():
        if not name.startswith("resumption"):
            continue
        for key in ("controller", "previous_manifest", "previous_progress",
                    "previous_launch", "previous_inventory", "diagnosis", "policy_document"):
            if key in block:
                path = bound(block[key])
                bindings.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path)))
        previous = bound(block["previous_manifest"]).parent
        roots.add(previous)
        prefix = block["consumed_prefix_ids"]
        previous_rows = read(previous / "progress.json")["rows"]
        require([r["id"] for r in previous_rows[:len(prefix)]] == prefix
                and previous_rows[:len(prefix)] == progress["rows"][:len(prefix)],
                "Consumed prefix changed")
        old = read(bound(block["previous_inventory"]))
        actual = {str(p.relative_to(previous)): sha(p)
                  for p in sorted(previous.rglob("*")) if p.is_file()}
        require(old == actual, "Sealed prior segment inventory changed")
    rows, private = [], []
    for plan, row in zip(m["rows"], progress["rows"]):
        require(all(plan[k] == row[k] for k in IMMUTABLE), "Assignment identity changed")
        candidates = [root / row["path"] / "runs" / row["case"]
                      for root in roots if (root / row["path"] / "runs" /
                                             row["case"] / "builder/result.json").is_file()]
        require(len(candidates) == 1, "Missing or duplicate original execution")
        task = candidates[0]
        result = read(task / "builder/result.json")
        require(result["cleanup_confirmed"] is True, "Builder cleanup unresolved")
        require(type(result["request_count"]) is int and 1 <= result["request_count"] <= 16,
                "Authoring request budget invalid")
        require(type(result["elapsed_seconds"]) in (int, float)
                and 0 <= result["elapsed_seconds"] <= 600, "Authoring time budget invalid")
        assessment = task / "assessment"
        vp = (ordinary(row["verdict_path"]) if row.get("verdict_path") else
              assessment / "revised-verdict.json" if assessment.is_dir() else None)
        value, verdict = (read(vp), None) if vp else (None, None)
        if value:
            verdict = value["verdict"]
            require(sha(assessment / "report.json") == value["original_report_file_sha256"]
                    and sha(assessment / "review.json") == value["original_review_file_sha256"],
                    "Original report/review changed")
        label = outcome(row, verdict)
        source = task / "candidate.py"
        source_sha = sha(source) if source.is_file() else None
        require((source_sha is not None) == (result["status"] == "completed"),
                "Submission availability contradicts builder")
        reason = None
        if label == "unscored_incident":
            if verdict is None:
                reason = "provider_relay_stream"
            else:
                fidelity = read(assessment / "export-fidelity.json")
                unresolved = {v["cause"] for v in fidelity["boundaries"]["verdicts"]
                              if v["verdict"] == "indeterminate"}
                reason = ",".join(sorted(unresolved)) if unresolved else "unsupported_source_constraints"
        public = {k: row[k] for k in ("id", "model", "arm", "case", "repeat")}
        public.update(outcome=label, score=row.get("score"),
                      strict_correct=row.get("strict_correct"), source_sha256=source_sha,
                      verdict_sha256=sha(vp) if vp else None,
                      unscored_reason=reason, requests_received=result["request_count"],
                      authoring_seconds=result["elapsed_seconds"],
                      mechanism_human_status="pending" if source_sha else "unassessable")
        rows.append(public)
        private.append(dict(id=row["id"], task_path=str(task.relative_to(ROOT)),
                            verdict_path=str(vp.relative_to(ROOT)) if vp else None))
    result = aggregate(rows)
    require((result["protocol_success"], result["evaluated_failure"],
             result["unscored_incident"]) == (202, 20, 18), "Unexpected terminal tally")
    public = dict(format="confirmation-240-closeout-v1",
                  campaign_manifest_sha256=sha(campaign / "manifest.json"),
                  campaign_progress_sha256=sha(campaign / "progress.json"),
                  finished=progress["finished"], primary="all_assigned_protocol_success",
                  scientific_review=m["scientific_review"], grading_enabled=m["grading_enabled"],
                  sample_size_justification=m["sample_size_justification"],
                  mechanism_review="pending_human_adjudication",
                  operational_policy="confirmation-deferred-anomalies-v1",
                  evaluator_reassessment_performed=False, counts=result, rows=rows)
    return public, private, roots, bindings


def dump(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def freeze(campaign, output):
    output = ordinary(Path(output).absolute())
    require(not output.exists(), "Closeout output already exists")
    public, mapping, roots, bindings = collect(campaign)
    require(all(output != root and not output.is_relative_to(root) for root in roots),
            "Closeout must not write inside frozen execution evidence")
    before = inventory(roots)
    for item in bindings:
        before[item["path"]] = item["sha256"]
    output.mkdir()
    dump(output / "aggregate.json", public)
    dump(output / "operator-map.json", mapping)
    dump(output / "evidence-inventory.json", before)
    seal = dict(format="confirmation-240-evidence-seal-v1", files=len(before),
                inventory_sha256=sha(output / "evidence-inventory.json"),
                aggregate_sha256=sha(output / "aggregate.json"),
                operator_map_sha256=sha(output / "operator-map.json"),
                roots=[str(p.relative_to(ROOT)) for p in sorted(roots)])
    dump(output / "seal.json", seal)
    require(all(sha(ROOT / path) == digest for path, digest in before.items()),
            "Original evidence changed while freezing")
    return seal


def verify(output):
    output = ordinary(Path(output).absolute())
    seal = read(output / "seal.json")
    require(sha(output / "evidence-inventory.json") == seal["inventory_sha256"]
            and sha(output / "aggregate.json") == seal["aggregate_sha256"]
            and sha(output / "operator-map.json") == seal["operator_map_sha256"],
            "Closeout artifact changed")
    expected = read(output / "evidence-inventory.json")
    actual = inventory([ROOT / r for r in seal["roots"]])
    require(all(actual.get(p) == digest for p, digest in expected.items() if p in actual),
            "Retained execution changed")
    for path, digest in expected.items():
        require(sha(ROOT / path) == digest, "Frozen file changed or missing")
    require(set(actual) <= set(expected), "Unexpected new execution evidence")
    return dict(status="passed", files_verified=len(expected), aggregate_sha256=seal["aggregate_sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "verify"))
    parser.add_argument("--campaign", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "freeze":
        require(args.campaign is not None, "Specify the terminal campaign")
        result = freeze(args.campaign, args.output)
    else:
        result = verify(args.output)
    print(json.dumps(result, sort_keys=True))
