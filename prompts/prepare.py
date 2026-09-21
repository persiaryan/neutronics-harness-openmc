"""Prepare builder input from an explicit list of public text files only.

This module does not send requests, run candidate code, or provide a sandbox.
"""

import argparse
import hashlib
import json
from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parent
CASE_FILES = {
    "reflected_7x7": "cases/reflected_7x7.md",
    "reflective_pin_cell": "cases/reflective_pin_cell.md",
    "moderated_cylinder": "cases/moderated_cylinder.md",
    "two_composition_5x5": "cases/two_composition_5x5.md",
    "axially_zoned_5x5": "cases/axially_zoned_5x5.md",
    "asymmetric_5x5": "cases/asymmetric_5x5.md",
}


def read_public_text(relative):
    """Refuse links; never discover inputs by scanning the project tree."""
    path = PROMPT_ROOT
    for component in Path(relative).parts:
        path = path / component
        if path.is_symlink():
            raise ValueError(f"Public prompt inputs must not be symlinks: {relative}")
    if not path.resolve().is_relative_to(PROMPT_ROOT):
        raise ValueError("Prompt input must remain inside the public prompt directory")
    if path.stat().st_nlink != 1:
        raise ValueError(f"Public prompt inputs must not be hard links: {relative}")
    return path.read_text(encoding="utf-8")


def build_prompt(case, *, contract='openmc-model-factory-v1'):
    """Return exactly the reviewed generic instructions plus one public task."""
    if case not in CASE_FILES:
        raise ValueError(f"Unknown case: {case!r}")
    templates = {'openmc-model-factory-v1': 'template_factory_v1.md'}
    if contract not in templates:
        raise ValueError('Unknown delivery contract')
    template = read_public_text(templates[contract])
    task = read_public_text(CASE_FILES[case])
    marker = "{{TASK_SPECIFICATION}}"
    if template.count(marker) != 1:
        raise ValueError("Template must contain exactly one task marker")
    return template.replace(marker, task.rstrip()).rstrip() + "\n"


def prepare(case, output, *, contract='openmc-model-factory-v1'):
    """Write a fresh, data-only bundle; no private paths or answers are inputs."""
    prompt = build_prompt(case, contract=contract)
    messages = [{"role": "user", "content": prompt}]
    messages_json = json.dumps(messages, indent=2, ensure_ascii=False) + "\n"
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "prompt.txt").write_text(prompt, encoding="utf-8")
    (output / "messages.json").write_text(messages_json, encoding="utf-8")
    manifest = {
        "case": case,
        "format": "builder-input-v1",
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "messages_sha256": hashlib.sha256(messages_json.encode("utf-8")).hexdigest(),
        "message_count": 1,
        "required_session": "fresh; no inherited conversation or memory",
        "required_capabilities": "contained generic coding; optional boundary inspection declared separately",
        "dispatch_implemented": False,
        "candidate_execution_implemented": False,
    }
    if contract == 'openmc-model-factory-v1':
        manifest.update(format='builder-input-v2', delivery_contract=contract)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=sorted(CASE_FILES))
    parser.add_argument("--output", type=Path, required=True,
                        help="New directory for the builder-input bundle")
    parser.add_argument('--contract', choices=('openmc-model-factory-v1',), default='openmc-model-factory-v1')
    args = parser.parse_args()
    try:
        manifest = prepare(args.case, args.output, contract=args.contract)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Prepared {args.case}: {args.output / 'prompt.txt'}")
    print(f"SHA-256: {manifest['prompt_sha256']}")
    print("No LLM request or candidate execution was performed.")


if __name__ == "__main__":
    main()
