"""Portable controls for public bindings and orchestration; no native claims."""
import ast
from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from evaluator import profiles, public_runtime
from evaluator.run import digest
from evaluation import public_reference
from evaluation.benchmark_suite import scoring
from prompts.prepare import CASE_FILES, read_public_text
from reproducibility import data
from examples import reproduce_reflective_pin_cell as example

ROOT = Path(__file__).resolve().parents[1]


def binding():
    return dict(format="public-runtime-binding-v1", semantic=public_runtime.semantic(),
                export_image="sha256:"+"a"*64, transport_image="sha256:"+"b"*64,
                native_identity=dict(worker_sha256=digest((ROOT/"evaluator/runtime/transport_worker.py").read_bytes()),
                                     solver_files={"/opt/openmc/bin/openmc": "c"*64}))


def package(folder):
    folder.mkdir()
    meta = dict(format="public-pin-cell-demo-reference-v1", case="reflective_pin_cell",
                grading_enabled=False, historical_reference=False, files={},
                public_task_sha256=digest(read_public_text(CASE_FILES["reflective_pin_cell"]).encode()),
                runtime_semantic=public_runtime.semantic(), rubric=scoring.identity(),
                source_sha256={p:digest((ROOT/p).read_bytes()) for p in
                               ("examples/reflective_pin_cell/reference_model.py", "reproducibility/reference.py")},
                keff=dict(mean=1.2, std_dev=.0001, uncertainty="one sigma"),
                scope="computational_reproduction_fixture_not_experimental_validation",
                data=dict(index_sha256="d"*64, files={}))
    sampling=dict(particles=25000,batches=800,inactive=200,generations_per_batch=2,seed=19)
    xml=b"<model/>"
    calc=dict(status="calculated_unreviewed",openmc_version=[0,15,3],model_xml_sha256=digest(xml),
              sampling=sampling,keff=meta["keff"])
    csv=("generation,active,k_generation,entropy_bits\n"+
         "".join(f"{i},{i>400},1.2,3.0\n" for i in range(1,1601))).encode()
    contents={"model.xml":xml,"calculation.json":json.dumps(calc).encode(),
              "convergence.csv":csv,"fidelity.json":b"{}"}
    for n,b in contents.items():
        (folder/n).write_bytes(b)
    from evaluation.candidates.receipts import histories
    meta.update(files={n:dict(sha256=digest(b),bytes=len(b)) for n,b in contents.items()},
                sampling=dict(sampling,source="uniform"),threads=1,
                convergence=histories(csv,sampling),generation_runtime=binding())
    meta["data"]["files"]={t+".h5":dict(sha256="e"*64,bytes=1,tables=[[k,t]]) for t,k in data.TABLES.items()}
    meta["data_acquisition"]=dict(data=meta["data"])
    raw=json.dumps(meta["data_acquisition"]).encode()
    (folder/"data-acquisition.json").write_bytes(raw)
    meta["files"]["data-acquisition.json"]=dict(sha256=digest(raw),bytes=len(raw))
    write_package(folder, meta)
    return meta


def write_package(folder, meta):
    raw = json.dumps(meta).encode()
    (folder/"manifest.json").write_bytes(raw)
    (folder/"seal.sha256").write_text(digest(raw)+"\n")


class RuntimeTests(unittest.TestCase):
    def test_semantic_identity_separate_from_local_digest(self):
        first, second = binding(), binding()
        second["export_image"] = "sha256:"+"d"*64
        self.assertEqual(public_runtime.validate(first)["semantic"], public_runtime.validate(second)["semantic"])
        self.assertNotEqual(first["export_image"], second["export_image"])

    def test_bound_profile_preserves_protocol_budgets_and_defaults(self):
        original = profiles.execution_profile(profiles.FACTORY_PROFILE, "openmc-model-factory-v1")
        route = profiles.assessment_route("openmc-model-factory-v1", profiles.FACTORY_PROFILE,
                                         profiles.BOUNDARY_PROTOCOL, runtime=binding())
        value = route["execution_profile"]
        self.assertEqual(value["budgets"], dict(export=60,inspection=120,transport=1800,automatic_retries=0))
        self.assertEqual(value["native_threads"], 1)
        self.assertEqual(value["export_image"], binding()["export_image"])
        self.assertEqual(profiles.execution_profile(profiles.FACTORY_PROFILE, "openmc-model-factory-v1"), original)

    def test_wrong_protocol_recipe_platform_mutable_tag_and_worker_rejected(self):
        with self.assertRaises(ValueError):
            profiles.assessment_route("openmc-model-factory-v1", profiles.FACTORY_PROFILE, "fake", runtime=binding())
        for change in ("recipe", "platform", "tag", "worker", "extra"):
            value = binding()
            if change == "recipe":
                value["semantic"]["recipe_sha256"]["evaluator/runtime/probe.py"] = "0"*64
            elif change == "platform":
                value["semantic"]["platform"] = "linux/amd64"
            elif change == "tag":
                value["export_image"] = "latest"
            elif change == "worker":
                value["native_identity"]["worker_sha256"] = "0"*64
            else:
                value["extra"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                public_runtime.validate(value)

    def test_public_recipe_has_no_project_image_dependency(self):
        recipe = (ROOT/"reproducibility/runtime/Dockerfile").read_text()
        self.assertNotIn("DEPENDENCY_IMAGE", recipe)
        self.assertNotIn("NATIVE_IMAGE", recipe)
        self.assertIn("27e38e894697bb32a1dac7848d2618818b6b8daf", recipe)
        self.assertIn("OPENMC_USE_MPI=OFF", recipe)
        self.assertIn("snapshot.debian.org", recipe)
        self.assertNotIn("trusted=yes", recipe)
        self.assertNotIn("allow-unauthenticated", recipe)

    def test_fixture_contract_is_static_and_no_host_execution(self):
        for name in ("candidate.py", "reference_model.py"):
            raw = (ROOT/"examples/reflective_pin_cell"/name).read_text()
            tree = ast.parse(raw)
            functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
            self.assertEqual([n.name for n in functions], ["build_model"])
            self.assertEqual(functions[0].args.args, [])
            self.assertIsInstance(functions[0].body[-1], ast.Return)
            imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
            self.assertEqual(len(imports), 1)
            self.assertEqual(imports[0].names[0].name, "openmc")
            for private in ("/Users/", "/home/", "keff", "OPENAI_API_KEY", "CODEX_HOME"):
                self.assertNotIn(private, raw)


class ReferenceTests(unittest.TestCase):
    def test_published_reference_inventory_and_route(self):
        folder = ROOT/"examples/reflective_pin_cell/reference"
        goal = public_reference.target("reflective_pin_cell", folder, binding())
        self.assertEqual(goal["reference"]["primary_mean"],
                         dict(mean=1.4488925454032306, std_dev=0.00016175366894689348,
                              uncertainty="one sigma"))
        self.assertEqual(goal["reference"]["scientific_review"], "public_demo_only")
        self.assertIs(goal["reference"]["historical_reference"], False)
        self.assertEqual(goal["protocol"]["export_image"], binding()["export_image"])
        fidelity = json.loads((folder/"fidelity.json").read_bytes())
        self.assertEqual(fidelity["status"], "passed_checks")
        self.assertEqual(fidelity["boundaries"]["score_check"], True)

    def test_explicit_public_reference_and_no_private_fallback(self):
        from evaluation.candidates import run
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/"reference"
            package(folder)
            with patch.object(run, "verify_suite", side_effect=AssertionError("private reference access")):
                result = run.target("reflective_pin_cell", reference=folder, runtime=binding())
                self.assertEqual(result["reference"]["primary_mean"]["mean"], 1.2)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    run.target("reflective_pin_cell", reference=Path(tmp)/"missing", runtime=binding())
                with self.assertRaises(ValueError):
                    run.target("reflective_pin_cell", runtime=binding())

    def test_stale_tampered_wrong_case_reference_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/"reference"
            meta = package(folder)
            (folder/"manifest.json").write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "seal"):
                public_reference.target("reflective_pin_cell", folder, binding())
            for key, value in (("case", "reflected_7x7"), ("public_task_sha256", "0"*64),
                               ("historical_reference", True), ("rubric", {}),
                               ("keff", dict(mean=1.2, std_dev=0, uncertainty="one sigma"))):
                changed = dict(meta, **{key:value})
                write_package(folder, changed)
                with self.subTest(key=key), self.assertRaises((ValueError, KeyError)):
                    public_reference.target("reflective_pin_cell", folder, binding())
            write_package(folder, meta)
            (folder/"unlisted.txt").write_text("extra")
            with self.assertRaisesRegex(ValueError, "inventory"):
                public_reference.target("reflective_pin_cell", folder, binding())

    def test_runner_rejects_reused_output_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(example, "evaluate",
                side_effect=AssertionError("unexpected model dispatch")):
            with self.assertRaisesRegex(ValueError, "new output"):
                example.run(Path(tmp), Path(tmp)/"cross_sections.xml", binding())

    def test_runner_missing_reference_stops_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(example, "data_directory", return_value=(Path("index"), {})), \
                 patch.object(example, "REFERENCE", Path(tmp)/"missing"), \
                 patch.object(example, "evaluate", side_effect=AssertionError("unexpected model dispatch")):
                with self.assertRaises(ValueError):
                    example.run(Path(tmp)/"new", Path("index"), binding())

    def test_required_cli_arguments(self):
        with patch("sys.argv", ["example"]), self.assertRaises(SystemExit) as cm:
            example.main()
        self.assertEqual(cm.exception.code, 2)


class DataTests(unittest.TestCase):
    def archive(self, path, *, link=False, duplicate=False, missing=False):
        with tarfile.open(path, "w:xz") as tar:
            for i, name in enumerate(data.TABLES):
                if missing and i == 0:
                    continue
                content = ("synthetic-"+name).encode()
                info = tarfile.TarInfo("nested/"+name+".h5")
                info.size = len(content)
                if link and i == 0:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "/outside"
                    tar.addfile(info)
                else:
                    tar.addfile(info, io.BytesIO(content))
                if duplicate and i == 0:
                    tar.addfile(info, io.BytesIO(content))
            info = tarfile.TarInfo("../../ignored")
            info.size = 4
            tar.addfile(info, io.BytesIO(b"skip"))

    def test_flat_index_subset_and_hashed_identity(self):
        from evaluator.run import data_directory
        from evaluator.transport import data_identity
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); archive=root/"data.xz"
            self.archive(archive)
            receipt=data.prepare(str(archive), root/"out")
            self.assertEqual(receipt["archive_sha256"], digest(archive.read_bytes()))
            self.assertEqual(receipt["archive_bytes"], archive.stat().st_size)
            index,_=data_directory(root/"out/cross_sections.xml")
            actual=data_identity(index, {"required_tables":[[k,t] for t,k in sorted(data.TABLES.items())]})
            self.assertEqual(actual, receipt["data"])
            self.assertFalse((root/"ignored").exists())
            expected=deepcopy(receipt);expected["archive_sha256"]="0"*64
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                data.prepare(str(archive), root/"mismatch", expected)

    def test_links_duplicates_missing_tables_and_existing_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for kind in ("link","duplicate","missing"):
                archive=root/(kind+".xz")
                self.archive(archive, **{kind:True})
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    data.prepare(str(archive), root/kind)
            with self.assertRaisesRegex(ValueError, "new data directory"):
                data.prepare(str(archive), root)
            with self.assertRaisesRegex(ValueError, "outside"):
                data.prepare(str(archive), ROOT/"forbidden-data")

    def test_stream_limit(self):
        stream=data.HashedReader(io.BytesIO(b"more"))
        stream.count=12_000_000_000
        with self.assertRaisesRegex(ValueError, "limit"):
            stream.read()


class InspectorBindingTests(unittest.TestCase):
    def test_fresh_controller_and_retained_boundary_review_bind_same_local_image(self):
        from evaluation.scientific import inspection, boundaries
        from tests.fixtures.boundary_receipts import inspector_info, model, observation
        image = binding()["export_image"]
        info = inspector_info()
        info["Image"] = image
        xml = model(material="1")
        def docker(*args):
            if args[0] == "ps":
                return ""
            if args[:2] == ("image", "inspect"):
                return json.dumps([dict(Id=image)])
            if args[0] == "inspect":
                return json.dumps([info])
            return ""
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"observer"
            with patch.object(inspection, "docker", side_effect=docker) as calls, \
                 patch.object(inspection, "bounded", return_value=dict(exit_code=0,stop_reason=None,
                              stdout=json.dumps(observation(xml)).encode(),stderr=b"")):
                result=boundaries.observe(xml,folder,image=image)
            self.assertEqual(result["status"],"inspected")
            create=[c.args for c in calls.call_args_list if c.args[0]=="create"]
            self.assertEqual(create[0][-1],image)
            self.assertEqual(boundaries.record(folder,xml,image=image)["status"],"inspected")
            with self.assertRaises(ValueError):
                boundaries.record(folder,xml)
            info["HostConfig"]["NetworkMode"]="bridge"
            with self.assertRaises(RuntimeError):
                inspection.verify(info,image)

    def test_wrong_daemon_image_stops_before_observer_dispatch(self):
        from evaluation.scientific import inspection
        from tests.fixtures.boundary_receipts import model
        def docker(*args):
            if args[0]=="ps":
                return ""
            if args[:2]==("image","inspect"):
                return json.dumps([dict(Id="sha256:"+"f"*64)])
            raise AssertionError("Container must not launch")
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(inspection,"docker",side_effect=docker), \
             patch.object(inspection,"bounded",side_effect=AssertionError("No observer dispatch")):
            result=inspection.inspect_xml(model(material="1"),[],Path(tmp)/"observer",
                                          image=binding()["export_image"])
            self.assertEqual(result["status"],"infrastructure_failure")
            self.assertIn("image mismatch",result["error"])


class BuildCommandTests(unittest.TestCase):
    def test_clean_build_pulls_public_base_and_never_prunes(self):
        from reproducibility import build_runtime
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"runtime.json"
            with patch("sys.argv", ["build", "--no-cache", "--output", str(output)]), \
                 patch.object(build_runtime.subprocess, "check_output", return_value=b"linux/arm64\n"), \
                 patch.object(build_runtime.subprocess, "run") as dispatch, \
                 patch.object(build_runtime, "bind", return_value=binding()):
                build_runtime.main()
            self.assertEqual(json.loads(output.read_bytes()), binding())
            self.assertEqual(dispatch.call_count, 2)
            for call in dispatch.call_args_list:
                argv = call.args[0]
                self.assertEqual(argv[:2], ["docker", "build"])
                self.assertIn("--pull", argv)
                self.assertIn("--no-cache", argv)
                self.assertEqual(argv[argv.index("--platform")+1], "linux/arm64")
                self.assertIs(call.kwargs["check"], True)

    def test_wrong_architecture_or_existing_output_prevents_build(self):
        from reproducibility import build_runtime
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"runtime.json"
            for existing in (False, True):
                if existing:
                    output.write_text("unchanged")
                with patch("sys.argv", ["build", "--output", str(output)]), \
                     patch.object(build_runtime.subprocess, "check_output", return_value=b"linux/amd64\n"), \
                     patch.object(build_runtime.subprocess, "run", side_effect=AssertionError("No build")), \
                     patch.object(build_runtime, "bind", side_effect=AssertionError("No probe")), \
                     self.assertRaises(SystemExit) as cm:
                    build_runtime.main()
                self.assertEqual(cm.exception.code, 2)
                if existing:
                    self.assertEqual(output.read_text(), "unchanged")

    def test_build_failure_does_not_create_success_binding(self):
        from reproducibility import build_runtime
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"runtime.json"
            with patch("sys.argv", ["build", "--output", str(output)]), \
                 patch.object(build_runtime.subprocess, "check_output", return_value=b"linux/arm64\n"), \
                 patch.object(build_runtime.subprocess, "run",
                              side_effect=build_runtime.subprocess.CalledProcessError(1, ["docker", "build"])) as calls, \
                 patch.object(build_runtime, "bind", side_effect=AssertionError("No probe")), \
                 self.assertRaises(build_runtime.subprocess.CalledProcessError):
                build_runtime.main()
            self.assertEqual(calls.call_count, 1)
            self.assertFalse(output.exists())
