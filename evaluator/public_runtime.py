"""Explicit operator-owned binding for a locally built public ARM64 runtime.

Semantic recipe identity and local image/binary identities are separate.
A binding is not a signature or remote image attestation.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RECIPE_FILES = (
    "reproducibility/runtime/Dockerfile", "reproducibility/runtime/requirements.txt",
    "evaluator/runtime/idle.py", "evaluator/runtime/probe.py",
    "evaluator/runtime/transport_worker.py",
)
SEMANTIC = dict(id="public-openmc-0.15.3-arm64-v1", openmc="0.15.3",
                platform="linux/arm64", openmc_commit="27e38e894697bb32a1dac7848d2618818b6b8daf",
                native_threads=1, mpi=False)


def semantic():
    return dict(SEMANTIC, recipe_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                                        for p in RECIPE_FILES})


def validate(value):
    if not isinstance(value, dict) or set(value) != {"format", "semantic", "export_image", "transport_image", "native_identity"}:
        raise ValueError("Malformed public runtime binding")
    if value["format"] != "public-runtime-binding-v1" or value["semantic"] != semantic():
        raise ValueError("Public runtime recipe/version identity changed")
    for role in ("export_image", "transport_image"):
        if not isinstance(value[role], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value[role]):
            raise ValueError("Runtime requires immutable image IDs")
    identity = value["native_identity"]
    expected_worker = semantic()["recipe_sha256"]["evaluator/runtime/transport_worker.py"]
    if (not isinstance(identity, dict) or set(identity) != {"worker_sha256", "solver_files"}
            or identity["worker_sha256"] != expected_worker or not identity["solver_files"]
            or "/opt/openmc/bin/openmc" not in identity["solver_files"]
            or any(not re.fullmatch(r"/opt/openmc/(bin/openmc|lib/[A-Za-z0-9_.-]+)", p)
                   or not re.fullmatch(r"[0-9a-f]{64}", h) for p, h in identity["solver_files"].items())):
        raise ValueError("Malformed native binary/worker identity")
    return value


def load(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 64000:
        raise ValueError("Invalid runtime binding file")
    return validate(json.loads(path.read_bytes()))


def bind(export, transport):
    values = {}
    for role, tag in (("export_image", export), ("transport_image", transport)):
        info = json.loads(subprocess.check_output(["docker", "image", "inspect", tag]))[0]
        if (info["Os"], info["Architecture"]) != ("linux", "arm64"):
            raise ValueError("Only native Linux ARM64 images are supported")
        values[role] = info["Id"]
    identity = json.loads(subprocess.check_output([
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
        "--entrypoint", "python", values["transport_image"], "-I", "-B",
        "/opt/evaluator/transport_worker.py", "probe"]))
    return validate(dict(format="public-runtime-binding-v1", semantic=semantic(),
                         native_identity=identity, **values))
