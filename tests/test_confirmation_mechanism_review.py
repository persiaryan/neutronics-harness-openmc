"""Negative controls: syntax is not semantics and AI proposals are not human labels."""
from pathlib import Path
import tempfile
import json
import unittest
from unittest.mock import patch

import confirmation_mechanism_review as review
import confirmation_closeout as c


class MechanismReviewTests(unittest.TestCase):
    def test_syntax_does_not_label_safe_or_unsafe_accumulation(self):
        safe = "base = left & right\nowned = base\nowned &= limit\n"
        unsafe = "base = left & right\ncell.region = base\nowned = base\nowned &= limit\n"
        a, b = review.syntax_facts(safe), review.syntax_facts(unsafe)
        self.assertEqual(len(a["augmented_region_syntax"]), 1)
        self.assertEqual(len(b["augmented_region_syntax"]), 1)
        self.assertNotIn("status", a)
        self.assertEqual(b["region_attribute_writes"][0]["target"], "cell.region")

    def test_method_mutation_and_operator_reference_are_not_missed(self):
        facts = review.syntax_facts(
            "region.append(term)\nnew = reduce(operator.iand, parts)\nregion.nodes[0] = other\n")
        self.assertEqual(facts["mutating_calls"][0]["receiver"], "region")
        self.assertEqual(facts["operator_mutator_references"][0]["expression"], "operator.iand")
        self.assertEqual(facts["region_attribute_writes"][0]["target"], "region.nodes[0]")

    def test_parsing_never_executes_top_level_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "executed"
            facts = review.syntax_facts(
                f"open({str(marker)!r}, 'w').write('unsafe')\nregion &= other\n")
            self.assertFalse(marker.exists())
            self.assertEqual(len(facts["augmented_region_syntax"]), 1)

    def test_dynamic_sources_remain_explicit_review_hazards(self):
        facts = review.syntax_facts("getattr(region, method)(part)\nsetattr(region, '_nodes', parts)\n")
        self.assertEqual(len(facts["dynamic_features"]), 2)

    def test_ai_cannot_be_imported_as_declared_human_and_full_chain_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root / "candidate.py"
            source.write_text("base = left & right\nowned = base\nowned &= limit\n")
            with patch.object(c, "ordinary", side_effect=lambda p, root=root: Path(p)):
                record = dict(status="demonstrated", reviewer="Codex", reviewer_type="ai",
                              source_sha256=c.sha(source), limitations="Static proposal only",
                              sharing="Alias at line 2", mutation="Line 3 changes same object",
                              downstream_use="Must still be demonstrated",
                              damaging_consequence="Must still be demonstrated",
                              evidence=[dict(path="candidate.py", sha256=c.sha(source), lines=[1,3])])
                review.validate_record(record, source, "ai")
                with self.assertRaises(ValueError):
                    review.validate_record(record, source, "human")
                changed = dict(record, damaging_consequence="")
                with self.assertRaises(ValueError):
                    review.validate_record(changed, source, "ai")
                changed = dict(record, evidence=[dict(
                    path="candidate.py", sha256=c.sha(source), lines=[1,4])])
                with self.assertRaises(ValueError):
                    review.validate_record(changed, source, "ai")

    def test_mutable_list_receiver_in_a_closure_is_distinct_from_region_method(self):
        source = "def build():\n    cells = []\n    def add():\n        cells.append(value)\n    region.append(term)\n"
        facts = review.receiver_bindings(source)
        self.assertEqual(facts[0]["lexical_list_definitions"], [2])
        self.assertFalse(facts[0]["unresolved_receiver"])
        self.assertTrue(facts[1]["unresolved_receiver"])

    def test_source_tamper_is_rejected_even_for_pending_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root / "candidate.py"
            source.write_text("original\n")
            with patch.object(c, "ordinary", side_effect=lambda p, root=root: Path(p)):
                record = dict(status="pending", source_sha256=c.sha(source))
                source.write_text("changed\n")
                with self.assertRaises(ValueError):
                    review.validate_record(record, source, "ai")


    def packet_fixture(self, root):
        frozen, prepared = root / "frozen", root / "prepared"
        frozen.mkdir()
        packet = prepared / "anonymous-source-review"
        directory = packet / "review-001"
        directory.mkdir(parents=True)
        original = root / "original/candidate.py"
        original.parent.mkdir()
        original.write_text("region = left & right\n")
        (directory / "candidate.py").write_bytes(original.read_bytes())
        (directory / "public-task.md").write_text("Required geometry\n")
        c.dump(packet / "measurement-definition.json", {"four_links": True})
        (packet / "README.md").write_text("Independent review instructions\n")
        c.dump(packet / "inventory.json", [dict(
            id="review-001", source_sha256=c.sha(original),
            task_sha256=c.sha(directory / "public-task.md"))])
        c.dump(prepared / "operator-key.json", [dict(
            review_id="review-001", assignment="001", source_path="original/candidate.py")])
        c.dump(prepared / "source-review-index.json", dict(
            sources=1, anonymous_inventory_sha256=c.sha(packet / "inventory.json"),
            operator_key_sha256=c.sha(prepared / "operator-key.json"),
            measurement_definition_sha256=c.sha(packet / "measurement-definition.json"),
            instructions_sha256=c.sha(packet / "README.md"),
            aggregate_sha256="bound_later"))
        c.dump(frozen / "aggregate.json", dict(rows=[dict(
            id="001", model="gpt-5.6-luna", arm="A", case="case",
            outcome="protocol_success", source_sha256=c.sha(original))]))
        digest = c.sha(frozen / "aggregate.json")
        index = c.read(prepared / "source-review-index.json")
        index["aggregate_sha256"] = digest
        (prepared / "source-review-index.json").write_text(json.dumps(index))
        c.dump(frozen / "seal.json", dict(aggregate_sha256=digest, roots=["original"]))
        record = dict(id="review-001", status="not_observed_within_reviewed_scope",
                      reviewer="Codex", reviewer_type="ai", source_sha256=c.sha(original),
                      limitations="Static synthetic review only",
                      sharing="Inspected alias", mutation="No observed mutation",
                      downstream_use="Constructed expression", damaging_consequence="Not observed",
                      evidence=[dict(path="candidate.py", sha256=c.sha(original), lines=[1,1])])
        c.dump(prepared / "draft.json", dict(
            format="confirmation-masked-mechanism-review-v1",
            aggregate_sha256=digest, records=[record]))
        return frozen, prepared

    def test_import_preserves_primary_and_cannot_promote_ai_to_human(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch.object(c, "ROOT", root), patch.object(c, "ordinary",
                    side_effect=lambda p, root=root: Path(p).absolute()):
                frozen, prepared = self.packet_fixture(root)
                output = prepared / "proposals.json"
                review.import_review(frozen, prepared, prepared / "draft.json", output, "ai")
                result = c.read(output)
                self.assertEqual(result["format"], "confirmation-mechanism-proposals-v1")
                self.assertEqual(result["rows"][0]["primary_outcome"], "protocol_success")
                self.assertEqual(result["mechanism_adjudication"], "pending")
                self.assertFalse(result["original_verdicts_modified"])
                with self.assertRaises(ValueError):
                    review.import_review(frozen, prepared, prepared / "draft.json",
                                         prepared / "human.json", "human")
                with self.assertRaises(ValueError):
                    review.import_review(frozen, prepared, prepared / "draft.json",
                                         root / "original/new.json", "ai")

    def test_packet_task_criteria_and_added_files_are_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch.object(c, "ROOT", root), patch.object(c, "ordinary",
                    side_effect=lambda p, root=root: Path(p).absolute()):
                _, prepared = self.packet_fixture(root)
                packet = prepared / "anonymous-source-review"
                task = packet / "review-001/public-task.md"
                original = task.read_bytes()
                review.verify_packet(prepared)
                task.write_text("Different scientific task\n")
                with self.assertRaises(ValueError):
                    review.verify_packet(prepared)
                task.write_bytes(original)
                definition = packet / "measurement-definition.json"
                original_definition = definition.read_bytes()
                definition.write_text("{}")
                with self.assertRaises(ValueError):
                    review.verify_packet(prepared)
                definition.write_bytes(original_definition)
                (packet / "review-001/hidden-score.json").write_text("{}")
                with self.assertRaises(ValueError):
                    review.verify_packet(prepared)


    def test_published_draft_cannot_be_mistaken_for_human_or_primary_results(self):
        path = Path(__file__).resolve().parents[1] / "docs/experiments/confirmation-mechanism-preliminary-v1.json"
        value = json.loads(path.read_text())
        self.assertEqual(value["reviewer_type"], "ai")
        self.assertFalse(value["blinded"])
        self.assertEqual(value["human_adjudication"], "pending")
        self.assertFalse(value["canonical_human_annotations_changed"])
        self.assertFalse(value["original_verdicts_modified"])
        self.assertEqual(value["source_count"], 238)
        self.assertEqual(value["missing_submission_ids"], ["030", "236"])
        counts = {arm: sum(g["sources_with_bitwise_augmented_assignment"]
                          for g in value["syntax_groups"] if g["arm"] == arm)
                  for arm in ("A", "D")}
        self.assertEqual(counts, {"A": 36, "D": 0})
        original = Path(__file__).resolve().parents[1] / "docs/experiments/confirmation-240-results-v1.json"
        self.assertEqual(value["aggregate_sha256"], c.sha(original))

    def test_future_evaluator_matrix_is_specification_not_a_passed_qualification(self):
        path = Path(__file__).resolve().parents[1] / "docs/experiments/confirmation-next-evaluator-controls-v1.json"
        value = json.loads(path.read_text())
        self.assertEqual(value["status"], "specified_not_qualified")
        self.assertFalse(value["active_campaign_route_changed"])
        self.assertFalse(value["original_outcomes_reassessed"])
        self.assertEqual(len(value["controls"]), 10)
        self.assertEqual({r["status"] for r in value["controls"]}, {"not_run"})
        self.assertEqual(len({r["id"] for r in value["controls"]}), 10)
        for row in value["controls"]:
            self.assertTrue(row["positive"])
            self.assertTrue(row["negative"])


if __name__ == "__main__":
    unittest.main()
