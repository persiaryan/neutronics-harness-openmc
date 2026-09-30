"""Build both public runtime stages and record their local immutable identities."""
import argparse
import json
from pathlib import Path
import subprocess
from evaluator.public_runtime import ROOT, bind


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-cache", action="store_true", help="Negative preloaded-image control")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new runtime binding file")
    server = subprocess.check_output(["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"]).decode().strip()
    if server not in ("linux/aarch64", "linux/arm64"):
        parser.error("A native Linux ARM64 Docker engine is required")
    tags = {stage: "nh-public-repro-" + stage + ":v1" for stage in ("export", "transport")}
    for stage, tag in tags.items():
        subprocess.run(["docker", "build", "--platform", "linux/arm64", "--pull",
                        *(["--no-cache"] if args.no_cache else []),
                        "--target", stage, "-f", "reproducibility/runtime/Dockerfile",
                        "-t", tag, "."], cwd=ROOT, check=True)
    binding = bind(tags["export"], tags["transport"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
