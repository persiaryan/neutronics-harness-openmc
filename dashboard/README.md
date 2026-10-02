# Local operator dashboard

Read-only bilingual interface for a prepared, running or retained experiment. No
external services, JavaScript libraries, database, LLM judge or runtime dependency
beyond host Python 3.12+ and a browser. Source/feedback/logs are rendered as text.

English is the default. The **Language** selector switches all six views to
English or French and remembers the choice in browser local storage. If storage
is unavailable, switching still works for the current page. Numbers and times
follow the selected locale. Original instructions, emitted messages, feedback,
source, XML, logs and evidence receipts retain their original language and values.
Translations are a static local catalog; no model or translation service is called.

From the repository root:

```sh
python3 -B -m dashboard.server --run scratch/my-run --port 8765
```

Open **http://127.0.0.1:8765/**. The selected directory may not yet exist. Repeat
`--run` to select between runs. Stop the server with Ctrl+C. Existing
`experiments.run prepare`, `execute` and `assess` workflows remain usable.

The server binds only loopback, checks Host/Origin, exposes a fixed artifact
inventory and refuses path traversal, symlinks and mutations. No credentials,
raw request bodies, hidden/encrypted reasoning or private-reference directory
are served. It is an operator interface: run results, emitted messages, source,
feedback and logs can be sensitive. It is not intended to be exposed through a
reverse proxy or to untrusted users on the same machine. Never make its endpoint
or evidence directory reachable from the evaluated builder. Current builder
containers retain network=none and have no host mount.

## Explicit one-session public demonstration

This command **makes live model calls and native OpenMC runs**, at most eight
model requests, 600 authoring seconds, two boundary calls and two smoke calls,
without automatic retries. It requires the existing qualified authoring image,
host subscription credentials, data and a public-runtime binding (see the main
README). It uses a public pin-cell reference, unsuitable for hidden grading.

Start the dashboard pointing to a fresh output directory, then in another terminal:

```sh
python3 -B -m dashboard.demo --output scratch/my-run \
  --runtime scratch/public-runtime.json --data-index /path/to/tables/cross_sections.xml
```

The launcher prepares C, executes the real builder, validates submission provenance,
performs the independent public-demo assessment, runs its evidence verifier and
records `review.json` and a final summary. Existing output is refused. Failures
remain in the consumed run directory. A failed scientific outcome can be a valid
dashboard demonstration: do not retry to obtain a higher score.

## Reading the page

Every view shows the recorded A/B/C configuration, model, selected task and
authoring budgets. A permits guided coding; B adds boundary inspection; C adds
OpenMC smoke assistance. Declared tool access and observed scientific call records
are shown separately. Exact plan identities determine the letter; missing,
unrecognized or conflicting identities remain unknown, including legacy conditions.

- **Overview**: actual instruction, configuration/budgets, recorded progress,
  diagnostic score and evidence-review status.
- **Agent & tools**: calls, completed commands, emitted messages/reasoning summaries,
  recorded edits, actual feedback, exact delivery and later observable actions.
- **Evaluation**: six gates, all named checks, available expected/observed/rule
  fields, original fidelity details, score breakdown, numerical comparison,
  k/entropy histories and native warnings.
- **Model & evidence**: final Python/XML, working-versus-final XML identities/diff,
  downloadable text evidence and hashes.
- **Guide**: vocabulary, interpretation and coverage limits.
- **Compare A/B/C**: campaign scope, compatible model/protocol groups, equal-task
  success rates, domain/check matrices, task coverage, effort and session drilldown.

## Compare recorded campaigns

Repeat `--run` for individual directories, or create a local JSON manifest:

```json
{"runs": ["../experiment-A-01", "../experiment-B-01", "../experiment-C-01"]}
```

```sh
python3 -B -m dashboard.server --campaign scratch/my-campaign.json --port 8765
```

Paths are relative to the manifest. List the actual prepared or retained run
directories; an ordinary run may contain several task assignments. Duplicate
resolved roots are refused. Loading this manifest never launches an experiment.
All selected directories appear in the individual-run selector and in comparison.
The campaign reads compact report/review/result files, without parsing raw model
responses or loading XML/histories for every session. Its aggregate cache lasts
at most 10 seconds; the individual run view retains its two-second polling.

An observation is one task in one run. Models, evaluator protocols, runtime
profiles, authoring request/time/retry budgets, rubric identities, builder images,
declared request setup identities and public/private reference scopes form
separate groups. Different task prompt/reference/sampling identities and varying
tool budgets within the same condition suppress aggregate rates and comparisons.
Missing identities suppress comparisons. Unrecorded provider settings cannot be
checked; compatible recorded fields do not establish experimental equivalence.

Rates use only recognized A/B/C configurations and supported rubric checks with a
coherent retained review. A domain passes only when all required checks pass;
a demonstrated failed check makes it fail; otherwise it remains unknown. Model
hard-gate failures are failures, while infrastructure failures and unreached
domains remain unknown. The original diagnostic score is never recomputed.

For each task, the denominator includes every loaded observation, including
unknown outcomes. Global rates are the mean of the task rates, with equal task
weights. The task inventory is the union in the selected group: a task missing
from an arm suppresses that arm's global rate. Prepared sessions can represent
pending assignments; an unlisted repeat cannot be detected. Copied session
directories are not independently authenticated and must not be listed as repeats.

Displayed bounds span all unknown outcomes failing through all unknown outcomes
passing. They are **missing-outcome bounds, not statistical confidence intervals**.
A/B/C differences use the same task inventory and show corresponding bounds.
Counts and task-level results remain visible; differences are descriptive, not
causal evidence. Effort and score means use available observations with their own
counts; incomplete token usage is excluded. Click any matrix cell, filter outcomes,
then open a session's evaluation to inspect its actual evidence.

Polling is every two seconds; complete LLM responses and native process logs are
written at completion, not token/batch streamed. Host-side `progress.jsonl`
provides live phase starts/results without changing prompts, tools, budgets or
grading. Failures in telemetry are nonfatal and warn separately. A start without
an end is not a liveness guarantee. The independent grader remains authoritative;
the dashboard reads the retained review, it does not re-run verification.

Chronology replay filters agent events only. Feedback/result panels remain the
available evidence summary, clearly labeled; there is no fabricated historical
snapshot. Historical sessions lack some host timestamps. Recorded file changes
are displayed; arbitrary shell-generated Python revisions are not reconstructed.
XML comparison uses the working XML, not the smoke copy with reduced sampling.
Exact feedback projection reuses `builder.trajectory.summarize` after authoring
finishes. Missing/ambiguous evidence stays unknown; receiving feedback does not
prove understanding, causation or correction. There is no score for tool use.

## Verification

```sh
python3 -B -m unittest tests.test_dashboard -v
python3 -B -m unittest tests.test_dashboard_campaign -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
# Optional template checks, with an installed Node.js; no npm packages required.
node tests/test_dashboard_templates.cjs
# Optional campaign template/event checks against a saved /api/campaign JSON:
node tests/test_dashboard_campaign_templates.cjs /path/to/campaign-response.json
```

Portable tests cover pending/zero/unknown results, original verdict preservation,
incomplete writes, emitted summaries versus hidden reasoning, XML identity,
invalid evidence, nonfinite histories, symlinks, telemetry failure, HTTP origin,
path/method restrictions and inert artifact delivery. They do not qualify a live
provider or native solver. Browser/native validation for this implementation is
reported separately in `VALIDATION.md`.

Telemetry adds small synchronous local writes. No claim is made that its timing
overhead has zero effect on bounded authoring. Compare matched instrumented
conditions before making efficacy claims.
