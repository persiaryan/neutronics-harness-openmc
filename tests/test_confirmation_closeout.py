"""Independent tally, null-preservation and evidence-freeze regression controls."""
from pathlib import Path
import tempfile
import json
from collections import Counter
import unittest
from unittest.mock import patch

import confirmation_closeout as c


class CloseoutTests(unittest.TestCase):
    def test_success_requires_strict_true_and_coherent_matching_score(self):
        row = dict(state="finished", score=96.42857142857143, strict_correct=False)
        verdict = dict(evidence_status="coherent", score=row["score"], strict_correct=False)
        self.assertEqual(c.outcome(row, verdict), "evaluated_failure")
        for key, value in (("score", 100), ("strict_correct", True),
                           ("evidence_status", "insufficient")):
            changed = dict(verdict, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.outcome(row, changed)

    def test_unknown_with_raw_false_is_never_a_model_failure(self):
        row = dict(state="incident", score=None, strict_correct=None)
        verdict = dict(evidence_status="coherent", score=None, strict_correct=False)
        self.assertEqual(c.outcome(row, verdict), "unscored_incident")
        self.assertEqual(c.outcome(row), "unscored_incident")
        with self.assertRaises(ValueError):
            c.outcome(dict(row, score=0), verdict)

    def test_pending_is_rejected_instead_of_becoming_an_incident(self):
        with self.assertRaises(ValueError):
            c.outcome(dict(state="pending"))

    def test_all_assigned_denominator_and_partial_failures(self):
        rows = [dict(model="m", arm=arm, case="case", outcome=outcome)
                for arm, outcomes in (
                    ("A", ("protocol_success", "evaluated_failure", "unscored_incident")),
                    ("D", ("protocol_success", "protocol_success", "unscored_incident")))
                for outcome in outcomes]
        value = c.aggregate(rows)
        self.assertEqual((value["assigned"], value["protocol_success"],
                          value["evaluated_failure"], value["unscored_incident"]), (6, 3, 1, 2))
        self.assertAlmostEqual(value["by_model"][0]["D_minus_A_success_fraction"], 1/3)
        self.assertEqual(value["by_model"][0]["arms"]["A"]["assigned"], 3)

    def test_symlink_and_outside_scope_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            target = root / "original"
            target.write_text("retained")
            alias = root / "alias"
            alias.symlink_to(target)
            self.assertEqual(c.ordinary(target, root), target)
            with self.assertRaises(ValueError):
                c.ordinary(alias, root)
            with self.assertRaises(ValueError):
                c.ordinary(root.parent / "outside", root)
            with self.assertRaises(ValueError):
                c.ordinary(root / ".." / "outside", root)

    def test_seal_detects_changed_missing_and_added_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            evidence = root / "evidence"
            evidence.mkdir()
            frozen = evidence / "verdict.json"
            frozen.write_text("original")
            output = root / "closeout"
            output.mkdir()
            with patch.object(c, "ROOT", root), patch.object(c, "ordinary",
                    side_effect=lambda p, root=root: Path(p)):
                c.dump(output / "aggregate.json", {"unchanged": True})
                c.dump(output / "operator-map.json", [])
                inventory = c.inventory([evidence])
                c.dump(output / "evidence-inventory.json", inventory)
                c.dump(output / "seal.json", dict(
                    inventory_sha256=c.sha(output / "evidence-inventory.json"),
                    aggregate_sha256=c.sha(output / "aggregate.json"),
                    operator_map_sha256=c.sha(output / "operator-map.json"),
                    roots=["evidence"]))
                self.assertEqual(c.verify(output)["status"], "passed")
                frozen.write_text("tampered")
                with self.assertRaises(ValueError):
                    c.verify(output)
                frozen.write_text("original")
                extra = evidence / "extra"
                extra.write_text("new execution")
                with self.assertRaises(ValueError):
                    c.verify(output)
                extra.unlink()
                frozen.unlink()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    c.verify(output)


    def test_public_result_counts_are_independently_reconciled(self):
        public = json.loads((Path(__file__).resolve().parents[1] /
            "docs/experiments/confirmation-240-results-v1.json").read_text())
        rows = public["rows"]
        self.assertEqual(len(rows), 240)
        self.assertEqual(Counter(r["outcome"] for r in rows), Counter(
            protocol_success=202, evaluated_failure=20, unscored_incident=18))
        expected = {("gpt-5.6-luna", "A"): (44, 11, 5),
                    ("gpt-5.6-luna", "D"): (50, 7, 3),
                    ("gpt-5.6-sol", "A"): (57, 0, 3),
                    ("gpt-5.6-sol", "D"): (51, 2, 7)}
        for key, values in expected.items():
            counts = Counter(r["outcome"] for r in rows if (r["model"], r["arm"]) == key)
            self.assertEqual(tuple(counts[k] for k in c.OUTCOMES), values)
        for row in rows:
            if row["outcome"] == "unscored_incident":
                self.assertIsNone(row["score"])
                self.assertIsNone(row["strict_correct"])
        self.assertEqual(rows[11]["score"], 0.0)
        self.assertEqual(rows[235]["outcome"], "unscored_incident")

    def test_public_projection_has_no_raw_or_operator_fields(self):
        public = json.loads((Path(__file__).resolve().parents[1] /
            "docs/experiments/confirmation-240-results-v1.json").read_text())
        allowed = {"id", "model", "arm", "case", "repeat", "outcome", "score",
                   "strict_correct", "source_sha256", "verdict_sha256", "unscored_reason",
                   "requests_received", "authoring_seconds", "mechanism_human_status"}
        for row in public["rows"]:
            self.assertEqual(set(row), allowed)
        serialized = json.dumps(public)
        for marker in ("/Users/", "Bearer ", "candidate.py", "request-01.json",
                       "reference_path", "candidate_keff"):
            self.assertNotIn(marker, serialized)


if __name__ == "__main__":
    unittest.main()
