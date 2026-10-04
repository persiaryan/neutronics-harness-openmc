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

## Campaign, task and run

- **Task / Tâche**: the problem specification, independent of its executions.
- **Run / Exécution**: one independent attempt on one task, with a model, an
  assistance configuration and a budget, followed by assessment or interruption.
- **Campaign / Campagne**: the planned inventory of runs and their recorded
  operational progress. Repeats are separate attempts, not tool calls or retries.
- **Batch / Lot**: a legacy directory containing several task executions.

Navigate **Campaign → Model → Configuration → Task → Run (repeat)**. A legacy
multi-task directory contributes one selectable execution per task; the evidence
files are not moved or rewritten. The implementation's numeric `run` API parameter
still addresses its selected directory; it is a routing index, not a durable ID.
New plans record UUID execution IDs. New campaign manifests record a UUID campaign
ID, execution IDs, relative paths and plan hashes. The retained v1 campaign adapter
derives IDs from the unchanged manifest and row identity. Unassigned legacy
directories use explicitly labeled location-derived IDs, not global identities.

To load a declared campaign, select its manifest directly, or use:

```json
{"campaigns": ["dashboard-pilot-6-01/manifest.json"]}
```

Only explicitly selected campaign manifests introduce directories. Their expected
rows remain in the inventory even when a run directory or plan is missing. The
dashboard reads adjacent `progress.json` for the recorded campaign state and stop
reason; completion counts come from run evidence. Separate campaigns never share
comparison groups. The old `{"runs": [...]}` selection is supported, but explicitly
labeled **No declared campaign**: its expected size and completeness are unknown.

The comparison view includes a grouped bar chart by model and configuration,
filtered by the selected campaign, model and task. The SVG includes a visible
model/color legend and a hatched unresolved-outcome key. Model colors remain
stable when filters change. See [legend validation and synthetic screenshots](../docs/validation/dashboard-model-legends/README.md). Comparable groups use the
existing equal-task-weight success rates, with hatched unresolved-outcome bounds
(not confidence intervals). If any displayed group has unavailable rates or the
displayed groups have different assessment, budget or task identities, all
bars show retained success counts and unresolved counts instead; no comparison
gate is bypassed. The accompanying table retains failures and denominators.
English and French labels follow the dashboard language selector.

Planned reference scope comes from the campaign manifest. Observed reference scope
comes from assessment evidence; absence of evidence means unknown, never private
by default. Declared scope, observed scope and membership conflicts are exposed
separately. The campaign groups stay stable by campaign/model during execution.
Conflicting observed protocols, runtimes, rubrics or membership block comparison
rates. Incomplete explicit groups retain verdict counts but withhold percentages
until the required identities are known; pending runs never become scientific
failures or fabricated assessments. Compatible groups in an unassigned legacy
selection remain descriptive and do not establish common campaign membership.

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

## Import a retained historical study

`python3 -B -m dashboard.import_study --locations /path/to/campaign-locations.json
--output scratch/history` imports the completed Request-16 archive identified by
the recovered location inventory. This is a specific archive adapter, not a
generic study importer. It requires the original sealed archive and a fresh
output directory; neither is bundled with the public release.

The importer checks the seal, analysis and copied evidence hashes, preserves the
selected historical assessments, and records every copy in `import-receipt.json`.
It checks the resulting six success counts against the retained study. It makes
no model calls and does not execute archived code. Native binary outputs are not
copied. Start the server with `--campaign scratch/history/campaign.json`.

The page identifies imported historical evidence. A bound study context keeps
the unscored provider incident in its intended comparison denominator; it never
supplies missing verdicts. Historical reviews remain retained reviews, not fresh
verification by the current evaluator. File hashes establish consistency with
the local archive, not independent authentication of its origin.

## Explicit serial pilot and prospective campaign

`experiments.dashboard_campaign` prepares and executes fresh sessions, using the
current implementation. The pilot has six sessions: two model setups × A/B/C on
the public pin-cell demonstration. The prospective development study has 150:
two setups × A/B/C × five tasks × five repeats, in a fixed shuffled order.
Both use 16 requests/600 authoring seconds, with zero automatic retries.

Preparation does not execute models:

```sh
python3 -B -m experiments.dashboard_campaign prepare --pilot \
  --output scratch/pilot-6 --setups /path/to/reviewed-setups.json \
  --runtime /path/to/public-runtime.json --data-index /path/to/public/cross_sections.xml
python3 -B -m dashboard.server --campaign scratch/pilot-6/dashboard-campaign.json
```

The setups JSON must map `gpt-5.6-luna` and `gpt-5.6-sol` to their reviewed request
setup descriptors. Preparation freezes source hashes, setup descriptors, data
index identity and budgets in `manifest.json`. For a private study, omit
`--pilot` and `--runtime`, select a new output, and provide the data index matching
the installed private frozen suite. Verify reference/data/runtime compatibility
before launch. Public and private references can require different data indices.

This separate command **makes live model calls and native OpenMC runs**:

```sh
python3 -u -B -m experiments.dashboard_campaign run --output scratch/pilot-6
```

Each session follows builder → frozen submission → independent evaluation →
evidence review. A coherent scientific failure is retained and execution
continues; provider, infrastructure or unscored evaluation incidents stop further
dispatch. Source changes and less than 10 GiB free space also stop dispatch.
`progress.json` records campaign status; each run has its own status and evidence.
A launch is consumed once: the command refuses automatic restart or retry.
Preserve partial campaigns for diagnosis; do not rerun slots to improve scores.

The completed October campaign used the following explicitly authorized controller
to process its remaining pending slots:

```sh
python3 -u -B -m experiments.continue_campaign --output scratch/my-campaign
```

This is a recorded operational policy amendment, not a restart of consumed slots.
It preserves the original manifest, launch seal, results and source hashes, allowing
only the additional continuation controller, whose hash and prior progress are
recorded in `continuations.jsonl`. Finished and incident slots are skipped. A
retained unscored outcome can be followed by another independent slot, without
rescoring it or changing the evaluator. Environmental prerequisites are rechecked
every 30 minutes while blocked. Changed source/plan identities, unconfirmed cleanup,
unexpected controller errors and unreconciled active slots require operator review.
A file lock prevents concurrent continuation controllers. Completed inventory can
include incidents; it does not mean every attempt received a scientific score.

This is the retained controller used by that campaign, not a general recovery
command for arbitrary manifests. It requires the original source snapshot plus
this controller and assumes the 16-request profile. In particular, confirmed
cleanup after a builder failure permits the next slot even when that failure is
an initialization timeout. It has no repeated-incident circuit breaker. The
October campaign consequently retained seven builder initialization incidents
with zero model requests. Review this policy before using it for another campaign;
do not silently retry those attempts or treat them as model failures. See the
[campaign closeout](../docs/experiments/campaign-150-rerun-01.md).

The dashboard can show historical, pilot and prospective directories together,
but separates incompatible protocols and reference scopes. This launcher does
not establish scientific qualification or historical v7 equivalence.

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

An observation is one execution of one task. Models, evaluator protocols, runtime
profiles, authoring request/time/retry budgets, rubric identities, builder images,
declared request setup identities and public/private reference scopes form
compatibility checks. Explicit campaign membership is an additional boundary.
Different task prompt/reference/sampling identities and varying
tool budgets within the same condition suppress aggregate rates and comparisons.
Missing identities suppress comparisons. Unrecorded provider settings cannot be
checked; compatible recorded fields do not establish experimental equivalence.

Rates use only recognized retained configurations and supported rubric checks with a
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
Configuration differences use the same task inventory and show corresponding bounds.
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

Configuration/tool descriptions and evaluation definitions now drive the display.
New descriptions are frozen with their run; explicit historical readers preserve
old meaning. Unknown formats and invalid definitions remain visible without
producing successful aggregate verdicts. See [contracts and evolution checks](CONTRACTS.md).

```sh
python3 -B -m unittest tests.test_dashboard -v
python3 -B -m unittest tests.test_dashboard_campaign -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
# Optional template checks, with an installed Node.js; no npm packages required.
node tests/test_dashboard_templates.cjs
node tests/test_dashboard_chart.cjs
# Optional campaign template/event checks against a saved /api/campaign JSON:
node tests/test_dashboard_campaign_templates.cjs /path/to/campaign-response.json
```

Portable tests cover pending/zero/unknown results, original verdict preservation,
incomplete writes, emitted summaries versus hidden reasoning, XML identity,
invalid evidence, nonfinite histories, symlinks, telemetry failure, HTTP origin,
path/method restrictions and inert artifact delivery. They do not qualify a live
provider or native solver. Browser/native validation for this implementation is
reported separately in `VALIDATION.md`.

Optional rendered-browser checks use an already installed Playwright and Chromium
or Chrome. They require no production dependency or provider credentials. Create
a fresh synthetic selection and start its server in one terminal:

```sh
python3 -B -m tests.dashboard_browser_fixture --output scratch/dashboard-browser-fixture
python3 -B -m dashboard.server --campaign scratch/dashboard-browser-fixture/selection.json --port 8767
```

In another terminal, with `playwright` available to Node:

```sh
node tests/test_dashboard_browser.cjs http://127.0.0.1:8767 scratch/dashboard-browser-results
```

Alternatively set `DASHBOARD_PLAYWRIGHT_MODULE` to an existing Playwright module
directory and `DASHBOARD_BROWSER_EXECUTABLE` to an installed browser executable.
The checks exercise all six views in EN/FR, cascading and rapid navigation,
campaign boundaries, legacy batches, matrix drilldown, network failures, inert
text, keyboard focus and mobile overflow. Results and screenshots go to the
specified output directory. Stop the fixture server with Ctrl-C when finished.

Telemetry adds small synchronous local writes. No claim is made that its timing
overhead has zero effect on bounded authoring. Compare matched instrumented
conditions before making efficacy claims.
