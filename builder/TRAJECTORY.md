# Retained trajectory projection

P6 extends the existing read-only authoring projector with smoke-call reconstruction
from experimental continuation `1c2e805edf1303c0ebf0cfb84b2e226bf1917976`.
Public adaptations add strict delivery matching, explicit coverage and a separate
allowlisted metadata view. No study-specific source reconstruction or handwritten
mechanistic labels are imported.

## Read retained evidence

```python
import json
from pathlib import Path
from builder.trajectory import summarize
from builder.trajectory_public import public_view

builder_dir = Path("scratch/retained-session/builder")
result = json.loads((builder_dir / "result.json").read_bytes())
private_summary = summarize(builder_dir, result)
metadata = public_view(private_summary)
```

These functions read existing files and return dictionaries. They do not modify
evidence, call a model, execute candidate code, run native OpenMC, assess a model
or publish anything. The existing experiment launcher already calls `summarize`
after authoring; that launcher's `execute` command is still a live operation.

The operator summary is versioned `codex-trajectory-v3`. It consumes private
request JSON, response SSE, runtime events and tool receipts. Keep it private:
existing structured completion/edit records and error text can contain commands,
source, logs or local paths. Malformed JSON/SSE raises an error; it is not replaced
with invented evidence.

## Completion and delivery are different observations

Each smoke record preserves its call number, request turn, relative evidence
path, working/diagnostic XML hashes, recorded status and native outcome.

| Field | Meaning |
|---|---|
| `native_outcome` | Recorded native process result; exit completion alone does not establish validated smoke completion |
| `status` | Recorded tool outcome, including incomplete validation or refusal |
| `feedback_delivery` | Whether the retained compact feedback appeared in a later request under a uniquely matched invocation/output |
| `subsequent_actions/responses` | Observable events at or after the delivery request; no claim about interpretation |
| `scientific_score_effect` | Always `none` |

Delivery requires a known runtime smoke-call turn, a unique matching smoke
evidence reference, and the exact decoded feedback JSON in a subsequent tool
output. The invocation's type, name, call ID and arguments must match the
retained response. Object key order and JSON whitespace are irrelevant; value
types are preserved, so `true` cannot match `1`. A long-running command may
return its feedback through a later `write_stdin` invocation, which is bound
to its own call ID.

One uniquely matched, complete compact payload establishes `complete`
delivery. An exactly matched payload marked incomplete is
`incomplete_presentation`. Missing, modified, truncated, duplicated or
ambiguously attributed payloads remain `not_demonstrated`. Repeated history
in later requests is counted once at the first demonstrated delivery.
Missing or duplicate runtime bindings cannot establish boundary delivery either.

This is a trace projection, not independent execution-receipt verification.
It describes retained records and cannot prove that an operator has not rewritten
them. Delivered compact feedback does not establish that full logs were read,
that feedback was understood, or that a subsequent change was caused by it.
Existing working-export recognition remains limited to the literal documented
recipe and unambiguous recorded command completion.

## Effort and missingness

`smoke_requests_observed` and `smoke_native_completions_observed` count only
retained observations. The corresponding total fields are null unless the
usage count agrees with a complete contiguous call inventory and, when retained,
runtime request events. Native completion totals also require a known outcome
for every call. An explicit, consistent empty usage record establishes zero;
a missing tool directory does not. Refusals count as requests, with no native
completion. `smoke_feedback_deliveries_observed` counts demonstrated complete
deliveries, never presumed receipt.

`token_usage` sums only available nonnegative integer usage records from
unambiguous completed responses. `token_usage_response_count` is the
denominator. `token_usage_complete` additionally requires exact request,
response and usage turn inventories matching the declared request count.
Absent usage stays null; explicit zero usage stays zero. These are recorded
token counts, not a billing audit. Other tool/inspection counts describe retained
events, not proof that an incomplete trace contains no additional actions.

## Allowlisted metadata

`public_view` returns `public-trajectory-v1`: fixed count/coverage fields,
finite elapsed time, hashes, enumerated outcomes and restricted relative
evidence references. Tool names and call IDs are hashed. Raw commands, source,
transcripts, instruction content, log text, error messages, arbitrary host paths,
process dictionaries and unknown extension fields are excluded.

This is a limited shareable view, not a replacement for private originals.
Hashes are identifiers, not encryption or authenticity proofs; review whether
the remaining results/metadata are appropriate to publish. The function rejects
older summary formats rather than relabelling them. Historical stored summaries,
results and source artifacts are unchanged; any explicitly requested new
projection should be retained separately.

## Portable controls

```sh
python3 -B -m unittest tests.test_trajectory_projection -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

Synthetic records cover exact/delayed/missing/ambiguous feedback, call binding,
truncation, JSON types, refusals, null versus zero, token coverage, unchanged
working-export observations, read-only behavior and metadata allowlisting.
Dispatch tripwires forbid model or native process calls. No historical private
trace is copied into the public tests, and no live client/native qualification
is claimed. Final scientific assessment, prompts, conditions, tools and budgets
are unchanged. This slice does not add the prospective study manifest or runner
and does not establish full experimental v7 parity.
