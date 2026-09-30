# Fresh GitHub checkout: executed commands

Validated source commit: `908f34210672c2ff846bb3383ff1c949f85b3f70`.
The checkout was an anonymous HTTPS clone of the public feature branch, with
no prior scratch directory and a clean tracked tree. The final evidence commit
only adds documentation/evidence to that tested implementation.

Below are the executed tool invocations. Machine-specific temporary directory
names are represented by `$VALIDATION_ROOT` and `$DATA_DIR`; log redirections
are omitted. No project code was changed in the fresh checkout. The temporary
checkout root was created with Python's `tempfile.mkdtemp`, prefix
`nh-repro-fresh-v1-`, under `/private/tmp`.

```sh
git -c credential.helper= clone --branch feat/reproducibility-v1 \
  https://github.com/persiaryan/neutronics-harness-openmc.git "$VALIDATION_ROOT/checkout"
cd "$VALIDATION_ROOT/checkout"
git rev-parse HEAD
git status --short

python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B -m prompts.prepare --case reflective_pin_cell --output scratch/public-prompt

python3 -B -m reproducibility.build_runtime --no-cache --output scratch/public-runtime.json
```

The build helper passed `--no-cache --pull --platform linux/arm64` to both
Docker build stages. The Dockerfile's only base is the pinned public Python
image; the newly built export and transport image IDs differ from the
development build. Native binary identities, semantic recipe and the installed
package inventory match. Existing project images therefore did not supply the
runtime for this native assessment.

First data acquisition (exit 1; HTTP response body read timeout; retained):

```sh
export TMPDIR=/private/tmp
DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/nh-public-data.XXXXXX")/tables"
python3 -B -m reproducibility.data --source download --output "$DATA_DIR" \
  --expected examples/reflective_pin_cell/reference/data-acquisition.json \
  --receipt scratch/public-data-receipt.json
```

The public download endpoint remained available (HTTP 302 followed by 200,
content length 9,661,406,540). The root cause of the failed read was not
established. No success receipt or data tables existed for that attempt.

Explicit retry into a different new directory (exit 0):

```sh
export TMPDIR=/private/tmp
DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/nh-public-data.XXXXXX")/tables"
printf '%s\n' "$DATA_DIR" > ../data-directory-02.txt
caffeinate -dimsu python3 -B -m reproducibility.data \
  --source download --output "$DATA_DIR" \
  --expected examples/reflective_pin_cell/reference/data-acquisition.json \
  --receipt scratch/public-data-receipt-02.json
```

The complete archive, selected ten tables and index matched the published
receipt. `caffeinate` is the macOS sleep-prevention wrapper; the acquisition
code, timeouts and expected hashes were unchanged. There is no automatic retry.

Native assessment:

```sh
unset OPENMC_CROSS_SECTIONS OPENMC_CHAIN_FILE OPENAI_API_KEY OPENAI_BASE_URL CODEX_HOME PYTHONPATH PYTHONHOME
DATA_DIR="$(cat ../data-directory-02.txt)"
DATA_INDEX="$DATA_DIR/cross_sections.xml"
caffeinate -dimsu python3 -B -m examples.reproduce_reflective_pin_cell \
  --runtime scratch/public-runtime.json \
  --data-index "$DATA_INDEX" --output scratch/public-example
```

This invokes factory export, scientific inspection, boundary observation and
native transport, then the existing independent verifier. It does not invoke an
LLM or regenerate the public reference.

The clone shares the host's Docker daemon; it is not a clean-machine VM.
The source-only no-cache builds, fresh public acquisition, explicit new runtime
bindings and phase receipts provide the negative control against preloaded
project images and private references. Linux ARM64 is the only declared
runtime architecture. Cross-machine and x86_64 equivalence were not tested.
