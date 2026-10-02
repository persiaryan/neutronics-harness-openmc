# Local operator dashboard

Read-only bilingual interface for a prepared, running or retained experiment. No
external services, JavaScript libraries, database, LLM judge or runtime dependency
beyond host Python 3.12+ and a browser. Source/feedback/logs are rendered as text.

English is the default. The **Language** selector switches all five views to
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
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
# Optional template checks, with an installed Node.js; no npm packages required.
node tests/test_dashboard_templates.cjs
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
