"""Read a separately generated, explicitly selected public demonstration reference.

This is never an implicit replacement for the private six-case reference set.
"""
import json
from pathlib import Path
from evaluator.run import digest
from evaluator.public_runtime import validate, semantic
from evaluation.benchmark_suite import scoring
from evaluation.scientific.records import require, validate_keff
from prompts.prepare import CASE_FILES, read_public_text

ROOT = Path(__file__).resolve().parents[1]


def target(case, package, runtime):
    validate(runtime)
    package = Path(package)
    require(case == "reflective_pin_cell" and package.is_dir() and not package.is_symlink(),
            "Public demo reference supports only reflective_pin_cell")
    actual = {}
    for p in sorted(package.iterdir()):
        require(p.is_file() and not p.is_symlink() and p.stat().st_nlink == 1
                and p.stat().st_size <= 2_000_000, "Invalid public reference artifact")
        actual[p.name] = p.read_bytes()
    require("manifest.json" in actual and "seal.sha256" in actual, "Missing public reference seal")
    raw = actual.pop("manifest.json")
    require(actual.pop("seal.sha256").decode().strip() == digest(raw), "Public reference seal changed")
    value = json.loads(raw)
    require(value["format"] == "public-pin-cell-demo-reference-v1" and value["case"] == case
            and value["grading_enabled"] is False and value["historical_reference"] is False,
            "Not a public demonstration reference")
    require({n: dict(sha256=digest(b), bytes=len(b)) for n,b in actual.items()} == value["files"],
            "Public reference inventory changed")
    require(value["public_task_sha256"] == digest(read_public_text(CASE_FILES[case]).encode()),
            "Public task identity changed")
    require(value["runtime_semantic"] == semantic() and value["rubric"] == scoring.identity(),
            "Public reference recipe or scientific criteria changed")
    for path, sha in value["source_sha256"].items():
        require(path in {"examples/reflective_pin_cell/reference_model.py",
                         "reproducibility/reference.py"} and digest((ROOT/path).read_bytes()) == sha,
                "Public reference source changed")
    require(set(value["source_sha256"]) == {"examples/reflective_pin_cell/reference_model.py",
                                           "reproducibility/reference.py"}, "Missing reference source identities")
    require(set(actual) == {"model.xml", "calculation.json", "convergence.csv", "fidelity.json", "data-acquisition.json"},
            "Incomplete public reference evidence")
    sampling = dict(particles=25000, batches=800, inactive=200, generations_per_batch=2, seed=19)
    require(value["sampling"] == dict(sampling, source="uniform") and value["threads"] == 1,
            "Public reference sampling changed")
    calculation = json.loads(actual["calculation.json"])
    require(calculation["status"] == "calculated_unreviewed" and calculation["openmc_version"] == [0,15,3]
            and calculation["model_xml_sha256"] == digest(actual["model.xml"])
            and calculation["sampling"] == sampling and calculation["keff"] == value["keff"],
            "Public reference calculation identity changed")
    from evaluation.candidates.receipts import histories
    require(histories(actual["convergence.csv"], sampling) == value["convergence"],
            "Public reference history summary changed")
    from reproducibility.data import TABLES
    data = value["data"]
    require(json.loads(actual["data-acquisition.json"]) == value["data_acquisition"],
            "Public acquisition provenance changed")
    require(value["data_acquisition"]["data"] == data and set(data["files"]) == {t+".h5" for t in TABLES},
            "Public reference data collection changed")
    require(all(data["files"][t+".h5"]["tables"] == [[k,t]] for t,k in TABLES.items()),
            "Public reference data tables changed")
    validate(value["generation_runtime"])
    mean = validate_keff(value["keff"])
    require(value["scope"] == "computational_reproduction_fixture_not_experimental_validation",
            "Unsupported reference claim")
    reference = dict(kind=value["format"], manifest_sha256=digest(raw), primary_mean=mean,
                     scientific_review="public_demo_only", historical_reference=False)
    return dict(index=dict(manifest_sha256=digest(raw), status="verified", cases=1),
                reference=reference,
                protocol={k:runtime[k] for k in ("export_image", "transport_image")},
                runtime=runtime["native_identity"], data=value["data"])
