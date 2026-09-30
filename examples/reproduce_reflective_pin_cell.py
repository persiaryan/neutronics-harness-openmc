"""Assess the handwritten fixture through the real factory/inspection/transport path."""
import argparse
import json
from pathlib import Path
import subprocess
from evaluator.public_runtime import ROOT, load
from evaluator.profiles import BOUNDARY_PROTOCOL
from evaluator.run import digest, write_json
from evaluation.candidates.run import evaluate
from evaluation.candidates.verify import review_assessment
from evaluation.public_reference import target
from evaluator.run import data_directory

REFERENCE = ROOT/"examples/reflective_pin_cell/reference"
CANDIDATE = ROOT/"examples/reflective_pin_cell/candidate.py"


def run(output, index, runtime):
    if output.exists():
        raise ValueError("Use a new output directory; no automatic retries")
    index, _ = data_directory(index)
    goal = target("reflective_pin_cell", REFERENCE, runtime)
    output.mkdir(parents=True)
    report = evaluate("reflective_pin_cell", output/"assessment", index=index, candidate=CANDIDATE,
                      reference=REFERENCE, runtime=runtime)
    review = review_assessment(output/"assessment", index, reference=REFERENCE, runtime=runtime)
    write_json(output/"review.json", review)
    # Publishable summary: explicit fields only, never raw paths/container configs.
    summary = dict(
        format="public-native-example-report-v1",
        repository_commit=subprocess.check_output(["git","rev-parse","HEAD"], cwd=ROOT).decode().strip(),
        tracked_worktree_dirty=bool(subprocess.check_output(["git","diff","HEAD","--"], cwd=ROOT)),
        protocol=BOUNDARY_PROTOCOL, case="reflective_pin_cell", fixture="handwritten_not_historical_llm_trial",
        runtime=runtime, data=goal["data"], reference=goal["reference"],
        candidate_sha256=digest(CANDIDATE.read_bytes()), final_model=report.get("final_model"),
        status=report["status"], contract_status=report["gates"]["model_builds"]["passed"],
        gates={n: {k: v[k] for k in ("passed", "cause")} for n,v in report["gates"].items()},
        checks=report["checks"], native_completion=report["gates"]["openmc_runs"]["passed"],
        native_execution={k: report.get("phases", {}).get("transport", {}).get(k)
                          for k in ("status", "elapsed_seconds", "sampling")},
        candidate_keff=report.get("candidate_keff"), reference_keff=goal["reference"]["primary_mean"],
        comparison=report.get("comparison"), diagnostic_score=report["diagnostic_score"],
        verification_status=review["evidence_status"],
        verified_protocol_success=review.get("strict_correct") if review["evidence_status"]=="coherent" else None,
        elapsed_seconds=report["elapsed_seconds"], cleanup_confirmed=report["cleanup_confirmed"],
        limitations=[
            "One public handwritten computational example; no LLM invocation or historical study replay.",
            "Same existing scoring and uncalibrated +/-150 pcm criterion; grading activation remains disabled.",
            "Finite geometry/boundary observations; shared model/data biases and unproven convergence remain.",
            "The public reference emitted a Zr96 probability-table warning at 294 K; its shared-data bias is not quantified.",
            "Exact numerical reruns are only claimed for the same local runtime, data and seed after testing.",
            "Raw local assessment receipts can contain host paths; share report.json/report.md only."])
    write_json(output/"report.json", summary)
    lines=["# Public native pin-cell reproduction", "",
           "Protocol: `"+BOUNDARY_PROTOCOL+"`.",
           "Status: **"+summary["status"]+"**; retained-evidence review: **"+review["evidence_status"]+"**.",
           "Verified protocol success: **"+str(summary["verified_protocol_success"])+"**.",
           "Factory contract passed: **"+str(summary["contract_status"])+"**; native completion: **"+str(summary["native_completion"])+"**.",
           "Final XML: `"+str((summary["final_model"] or {}).get("sha256"))+"`.", "",
           "| Check category | Results |", "|---|---|"]
    for name, value in summary["checks"].items():
        lines.append("| "+name+" | "+json.dumps(value, sort_keys=True)+" |")
    lines += ["", "Candidate k-effective: "+json.dumps(summary["candidate_keff"])+".",
              "Public reference k-effective: "+json.dumps(summary["reference_keff"])+".",
              "Numerical comparison: "+json.dumps(summary["comparison"])+".",
              "", "Identities and execution details are in report.json.", ""]
    lines += ["- "+s for s in summary["limitations"]]
    (output/"report.md").write_text("\n".join(lines)+"\n")
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime", required=True, type=Path)
    p.add_argument("--data-index", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a=p.parse_args()
    result=run(a.output, a.data_index, load(a.runtime))
    print(json.dumps({k:result[k] for k in ("status","verification_status","verified_protocol_success")}))
    raise SystemExit(0 if result["verified_protocol_success"] is True else 1)


if __name__ == "__main__":
    main()
