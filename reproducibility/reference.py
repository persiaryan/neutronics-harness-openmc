"""Generate a NEW public demonstration reference from public source and data.

Maintainer command, separate from assessment; never reads historical references.
Raw local receipts stay in --output. Only a small checked package is published.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from evaluator import run as exporter, transport
from evaluator.public_runtime import ROOT, load, semantic
from evaluator.transport_input import accepted_export
from evaluation.candidates import assessment, boundary_assessment, receipts
from evaluation.candidates.phase_evidence import export_outcome
from evaluation.candidates.run import clean_resources
from evaluation.scientific import boundaries
from evaluation.scientific.inspection import inspect_xml, WORKER, admit
from evaluation.scientific.records import inspection_record, require, leakage
from evaluation.benchmark_suite import scoring
from evaluation.benchmark_suite.suite_cases import probes
from evaluation.benchmark_suite.suite_checks import assess
from prompts.prepare import CASE_FILES, read_public_text

CASE = "reflective_pin_cell"
SOURCE = "examples/reflective_pin_cell/reference_model.py"
SAMPLING = dict(particles=25000, batches=800, inactive=200, generations_per_batch=2, seed=19, source="uniform")


def generate(output, package, index, runtime, data_receipt):
    require(not output.exists() and not package.exists(), "Use new evidence and reference directories")
    expected_data = json.loads(data_receipt.read_bytes())["data"]
    actual = transport.data_identity(index, {"required_tables": [
        t for f in expected_data["files"].values() for t in f["tables"]]})
    require(actual == expected_data, "Data differ from public acquisition receipt")
    clean_resources()
    output.mkdir(parents=True)
    source_sha = exporter.digest((ROOT/SOURCE).read_bytes())
    image = runtime["export_image"]
    result = exporter.evaluate(ROOT/SOURCE, output/"export", index=index, image=image, runtime=runtime)
    require(result["status"] == "exported", "Reference export failed")
    require(export_outcome(output/"export", image, index, source_sha, runtime=runtime) ==
            dict(cause=None, reason=None), "Reference export receipts failed")
    xml, _ = accepted_export(output/"export")
    inspect_xml(xml, probes(CASE)[0], output/"inspection", wall_seconds=120, image=image)
    obs = inspection_record(CASE, output/"inspection", xml, WORKER.read_bytes(), image=image)
    require(obs["status"] == "inspected", "Reference inspection unavailable")
    boundaries.observe(xml, output/"boundaries", image=image)
    br = boundary_assessment.evaluate(boundaries.record(output/"boundaries", xml, image=image),
                                     boundaries.requirements(CASE), obs)
    fidelity = assess(CASE, admit(xml), obs, SAMPLING, boundary_result=br)
    checks = assessment.fidelity_checks(CASE, fidelity, obs)
    require(all(v is True for category in ("materials", "geometry", "physics_settings")
                for v in checks[category].values()), "Reference physics/settings did not pass")
    result = transport.transport(output/"export", output/"transport", index=index,
                                 image=runtime["transport_image"], wall_seconds=1800, runtime=runtime)
    require(result["status"] == "calculated_unreviewed", "Reference native transport incomplete")
    record = receipts.transport_record(output, source_sha, runtime["transport_image"], index)
    require(record["runtime"] == runtime["native_identity"] and record["data"] == expected_data,
            "Reference runtime/data changed")
    leak = leakage((output/"transport/openmc-stdout.txt").read_text())
    drift = record["convergence"]["statistics"]["entropy_bits"]["second_minus_first"]
    require(leak["mean"] == 0 and record["keff"]["std_dev"]*1e5 <= scoring.RUBRIC["maximum_candidate_std_dev_pcm"]
            and abs(drift) <= scoring.RUBRIC["entropy_active_half_drift_screen_bits"],
            "Reference precision/entropy/leakage screen failed")
    clean_resources()
    package.mkdir(parents=True)
    (package/"model.xml").write_bytes(xml)
    for filename in ("calculation.json", "convergence.csv"):
        shutil.copyfile(output/"transport/artifacts"/filename, package/filename)
    exporter.write_json(package/"fidelity.json", fidelity)
    exporter.write_json(package/"data-acquisition.json", json.loads(data_receipt.read_bytes()))
    files = {p.name: dict(sha256=exporter.digest(p.read_bytes()), bytes=p.stat().st_size)
             for p in sorted(package.iterdir())}
    manifest = dict(
        format="public-pin-cell-demo-reference-v1", case=CASE, grading_enabled=False,
        historical_reference=False, scope="computational_reproduction_fixture_not_experimental_validation",
        created_utc=datetime.now(timezone.utc).isoformat(),
        public_task_sha256=exporter.digest(read_public_text(CASE_FILES[CASE]).encode()),
        source_sha256={p:exporter.digest((ROOT/p).read_bytes()) for p in (SOURCE,"reproducibility/reference.py")},
        runtime_semantic=semantic(), generation_runtime=runtime, data=expected_data,
        data_acquisition=json.loads(data_receipt.read_bytes()), rubric=scoring.identity(),
        sampling=SAMPLING, threads=1, keff=record["keff"], convergence=record["convergence"],
        command='python3 -B -m reproducibility.reference --runtime "$RUNTIME" --data-index "$DATA_INDEX" --data-receipt "$DATA_RECEIPT" --output "$REFERENCE_EVIDENCE" --package "$REFERENCE_PACKAGE"',
        files=files, limitations=[
            "Separate public-specification transcription; no historical private reference bytes.",
            "Computational reproduction fixture, not experimental validation or independent physics certification.",
            "Stronger sampling and a different seed from candidate; shared OpenMC/data/model bias remains.",
            "Finite geometry probes and entropy drift screen do not prove global geometry validity or convergence."])
    exporter.write_json(package/"manifest.json", manifest)
    (package/"seal.sha256").write_text(exporter.digest((package/"manifest.json").read_bytes())+"\n")
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ("runtime","data-index","data-receipt","output","package"):
        p.add_argument("--"+arg, required=True, type=Path)
    a=p.parse_args()
    generate(a.output, a.package, a.data_index.resolve(strict=True), load(a.runtime), a.data_receipt)


if __name__ == "__main__":
    main()
