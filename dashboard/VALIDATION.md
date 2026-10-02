# Dashboard validation — 2026-10-02

Branch: `feat/local-run-dashboard`, based on `b4780ab097efba286fcaa85c8e90d93dbb020f03`.
The dashboard/campaign implementation through the A16 demonstration was committed
as `d81fa2f`. Subsequent observation-contract consolidation and interrupted-report
display corrections are described below. Scratch evidence stays local and ignored. This is an
observation and integration demonstration, not a new A/B efficacy study.

## Observation-contract consolidation

On 2026-10-02, after the preceding commit:

- **355 portable Python tests passed**, including 16 new evolution controls.
  Coverage includes D, a new tool/domain/criterion, distinct score scales,
  definition and report binding, missing criteria, invalid/unsupported formats,
  frozen historical readers, new tool budget conflicts, prepared-plan consistency,
  evaluator metadata/review production with a synthetic admission failure, and
  consistency between the current catalogue and runtime permissions/tool versions.
- JavaScript syntax and all three template suites passed. English/French views
  display D, the thermal probe, the new criterion, a score on 10 and a 75 pcm
  margin without adding configuration-specific columns. Unknown/malformed reports
  retain an escaped original report and a visible reader diagnostic.
- Local HTTP returned 200 for all five static resources, inventory, four session
  states and campaign data. Original report/review objects matched the retained
  files exactly. All four projections had zero file-read warnings.
- The three completed historical evaluations remain supported and review coherent:
  scores 100, 96.42857142857143 and 100. The historical cylinder admission failure
  remains unscored; its absent rubric identity is explicitly unsupported by the
  historical reader, with the original report still accessible.
- `git diff --check` passed. No new provider request, agent run or native transport
  was launched for this consolidation. No fresh rendered-browser review was made;
  template checks are not visual/ergonomic acceptance.

Disposable fixtures and HTTP checks: `scratch/dashboard-consolidation/`.
Reproducible synthetic fixture commands are in [CONTRACTS.md](CONTRACTS.md).
The loopback server was restarted with the same four retained sessions.

## Checks actually executed

### Follow-up: historical interrupted assessment display

The cylinder admission failure now appears as **Assessment interrupted: required
references unavailable**, with its recorded stage/error and absent score. The
historical missing-rubric warning is secondary. Overview and evaluation no longer
present this terminal report as waiting for assessment. `assessment_state()` in
`dashboard/contracts.py` supplies execution metadata independently of rubric
validation; `assessmentNotice()` and `unavailableText()` in `static/app.js` render
it in English/French. No historical report or scientific verdict was changed.

Verified: **357 portable Python tests passed**; interrupted-assessment templates
passed in both languages on synthetic files and the actual cylinder HTTP response.
Existing individual, evolution and campaign template suites passed. HTTP state
and campaign checks confirmed identical original report/review objects, null score
and unknown aggregate outcome. `git diff --check` passed. Server restarted at
`127.0.0.1:8765`; reload the page to load the updated JavaScript. No new agent/native
run or rendered-browser validation was performed. Local check fixture:
`scratch/dashboard-stop-fix/actual-cylinder-state.json`.

| Check | Result | Scope |
|---|---|---|
| Documented full Python suite | 325 tests passed | Includes 12 dashboard controls and existing harness regressions |
| JavaScript syntax and pure template tests | Passed | All five views, absent versus zero, failure/unknown, feedback delivery, replay/filter, text escaping, chart labels |
| Templates using the actual scratch-run API response | Passed | The 1 K / 10 K defect, exact diagnostic score and both feedback delivery references appear |
| Local HTTP HTML/CSS/JS, run inventory, state endpoint | All HTTP 200 | Loopback `127.0.0.1:8765`, expected MIME types |
| Exposed evidence downloads | 25 byte-identical files | Compared endpoint bytes and SHA-256 with original files |
| Observation during the live run | Passed | 11 changed HTTP snapshots; authoring, assessment, OpenMC start and final results observed |
| Final UI data versus native report/review | Exact equality | 60 detailed assertions, 800 generations, no projection warnings |
| Container/volume cleanup | Confirmed | No remaining `neutronics-v5-` containers or volumes |
| Rendered Chrome / visual usability | **Not executed by the assistant** | Computer Use permission was denied; the owner explicitly chose to inspect the visual rendering personally |

The template controls exercise presentation logic without a real DOM. They do
not establish screenshot quality, layout at all viewport sizes, assistive-device
behavior or actual click/keyboard usability. Responsive CSS, visible focus,
semantic controls, chart labels and a glossary are implemented; visual acceptance
belongs to the owner's browser review.

The actual retained run caught two presentation issues during development:
boundary and smoke projection records use different evidence/delivery field
shapes, and boundary coverage is a structured object rather than a string. Both
were corrected and covered by regression tests before handoff. The recorded
temperature mismatch is now surfaced on the overview, alongside the high score.

## Fresh scratch run

`scratch/dashboard-live-01`, GPT-5.6 Luna, guided boundaries + smoke, public
reflective-pin-cell reference, OpenMC 0.15.3 Linux ARM64. Fresh directory, eight
request ceiling, 600 authoring seconds, zero retries. The agent used **five
requests**, approximately **99.2 seconds**, one boundary inspection and one smoke.
Both feedback payloads were demonstrated in later requests (4 and 5 respectively).

The independent final assessment completed, as did retained-evidence review.
All six hard gates passed. **Diagnostic score: 96.42857142857143/100;
strict correctness: false; evidence: coherent.** Official grading remains disabled.

The final model omits an explicit temperature lookup tolerance. The evaluator
observed OpenMC's effective tolerance of **10 K**, while the task required **1 K**.
The physics check failed even though the smoke completed and final k-effective
was in numerical agreement with the public reference. The dashboard displays
this mismatch prominently and keeps the original result; no candidate repair or
second authoring attempt was made. The demo command exits 1 for this real
scientific non-success; this is distinct from dashboard availability failure.

Candidate k-effective: `1.4481972350919354 ± 0.0003414972628200393` (one sigma).
Delta: `-69.53103112952164` pcm; approximate 95% interval
`[-143.59326403836076, 4.531201779317485]` pcm. This public computational
demonstration does not qualify a hidden reference or establish model correctness.

Private local validation records are in `scratch/dashboard-validation/`:
`http-observations.jsonl`, `native-comparison.json`, `http-final.json`,
`final-state.json`, and the monitoring/comparison scripts. Run implementation
identities are recorded in `dashboard-run.json`; original builder/evaluator
snapshots and receipts remain in the run. Later presentation-only refinements
do not relabel its scientific outcomes.

## Owner browser review

### One authorized configuration A run with the 16-request profile

On 2026-10-02, `scratch/dashboard-A16-pin-01` ran `reflective_pin_cell`
with `gpt-5.6-luna`, configuration A and `authoring-requests-16-v1`.
Both plan and builder manifest recorded 16 maximum requests and 600 seconds.
The agent completed in 151.033 seconds using five requests, with no boundary or
smoke calls. This checks the extended allowance, not execution of all 16 slots.

The independent public-reference assessment completed in 321.283 seconds:
100/100, all six hard gates passed, all implemented required checks passed,
review coherent and strict correctness true. Native output contains 800 generations;
k-effective is `1.4481972350919354 ± 0.0003414972628200393` (one sigma).
This is the public computational demonstration within its declared coverage.

Live HTTP observations captured authoring, export/inspection, native transport and
the final score. Served candidate, final XML, report and review matched the files
exactly. The campaign kept this observation separate from the eight-request
groups. EN/FR templates and campaign navigation passed on this retained fixture.
Cleanup was confirmed, with no remaining project containers or volumes.
Evidence and verification scripts are retained in `scratch/dashboard-A16-pin-01`,
`scratch/dashboard-A16-pin-run.py` and `scratch/dashboard-A16-verify.py`.

### Campaign comparison view

The previous configuration/banner work was committed as `b9baace` before this
view was implemented. No new live session or native calculation was launched.
The comparison reader consumes compact retained plan/result/report/review files.

Validation passed: 26 targeted Python tests (14 aggregation tests and 12 dashboard
tests), existing bilingual run-view checks, and campaign template/event checks
in English and French using both retained observations and a synthetic 150-record
fixture. The synthetic fixture creates files only, with process execution blocked:
two model identities, three conditions, five tasks and five observations per cell.
Checks cover equal task weights, unknown denominators, zero versus absent scores,
missing tasks, incompatible versions/budgets, corrupt/symlink evidence, session
drilldown, escaping, empty results and stale-data errors. HTTP returned 200 for
the page, campaign script, translation script, run list and campaign endpoint.

The three existing local observations form two comparison groups. A/cylinder is
unknown; the two C/pin-cell observations contain one failure and one success.
They are not presented as a matched A/C experiment. HTTP and template fixtures
are retained under `scratch/dashboard-validation/campaign-*.json`.
The new view has not had a rendered-browser visual review. The owner can open
**Compare A/B/C**, choose a group/task, click a domain or check cell, and open its
original session evaluation. Percentage bounds describe missing outcomes; they
are not confidence intervals or evidence of causality.

### Configuration A on a different task

On 2026-10-02, a fresh live `gpt-5.6-luna` run used `moderated_cylinder`
with `guided_construction` (A), eight requests / 600 seconds maximum, no retries.
The builder completed in 75.411 seconds using five model requests and four
generic tool calls. Working export succeeded; no boundary or smoke calls were
recorded. Builder cleanup was confirmed and no project containers/volumes remained.

The independent evaluator stopped at admission: the private frozen reference
package is absent from this public checkout (`Package root must be a real
directory`). Assessment is `incomplete`, review evidence is `insufficient`,
and the score is null. No final evaluation XML or native transport was produced.
This run validates display of an evaluator limitation, not scientific correctness.

Live HTTP observations captured progression from authoring to the final state.
API candidate/report/review contents matched the retained files exactly, with no
projection warnings. All five templates rendered in English and French with A,
the correct task, and an absent score rather than a fabricated zero.
Evidence: `scratch/dashboard-A-cylinder-01/{http-observations.jsonl,dashboard-state.json,dashboard-validation.json}`.

### Bilingual interface update

English is now the default, with a persistent English / Français selector.
The 12 dashboard Python tests passed again, including serving the locale script
and the English HTML shell. Node template checks passed in both languages on
synthetic data and the retained live-run fixture: locale formatting, default and
saved language, unavailable storage, replay/filter behavior, and unchanged raw
evidence and scores. This presentation update does not require another native run.
Rendered-browser usability remains for owner review.

Open http://127.0.0.1:8765/ and select `dashboard-live-01`.

Switch to Français and back to English; reload to check the saved choice.

1. Overview: see **96.4/100** together with the **1 K expected / 10 K observed**
   defect, the public-demo label and the non-success explanation.
2. Agent & tools: expand one command and both feedback cards; confirm delivery
   references 4 and 5. Try chronological replay and the event filter.
3. Evaluation: inspect the failed physics check, its temperature assertion,
   numerical comparison, k/entropy curves and native warnings.
4. Model & evidence: inspect Python/XML, XML identities and open an evidence file.
5. Check keyboard focus, expanded-detail persistence during refresh, narrow-window
   layout and readability. The guide explains pending, failed and unknown states.

The dashboard is read-only. Refreshes and replay never execute the agent, native
transport or grader. Detailed feedback delivery is established only after complete
authoring evidence is available; a later action is not proof of causal learning.

## Historical archive import and new pilot (2026-10-02)

Imported the completed `abc-temperature-amendment-v1/study-01` archive from the
separate local research checkout into `scratch/request16-dashboard-history-01`.
The importer checked the source seal and selected analyses. All 30,468 copied
text files subsequently matched their retained copy hashes. It preserved the
original authoring and selected v7 assessments; the first 38 inherited reviews
were copied byte-for-byte from `verification.json` to the dashboard's
`review.json` location. No archived code or native binary was executed.

HTTP and comparison checks reproduced 150 terminal observations and 149 scored
assessments. Equal-task success rates were Luna A/B/C 72/68/56 percent and Sol
A/B/C 92/100/84 percent. The single Sol/C provider incident remained unknown in
the denominator, with an interrupted-authoring notice and no scientific score.

Portable verification: 363 Python tests passed. EN/FR run templates and campaign
navigation passed for both the 150-record archive and a mixed 156-assignment
selection containing the six newly prepared pilot slots. Regression controls
cover evidence binding, imported incident denominators, conflicting declared
identities, fixed pilot budgets, changed source refusal and consumed launches.
This is HTTP/template verification, not a rendered-browser review.

The six-session pilot was launched in `scratch/dashboard-pilot-6-01` using the
public pin-cell reference, 16 requests/600 seconds and reviewed request setups.
The first Luna/A builder completed using three requests. Final transport was
still running at this checkpoint. The remaining slots had not started, and the
new 150-session campaign had not been launched. See the retained `progress.json`
and per-run receipts for subsequent outcomes; this paragraph is not a completed
pilot claim. Available disk fell below the launcher's 10 GiB reserve during
that first assessment, so further dispatch requires sufficient space.

Private reference packages were installed as gitignored local copies and passed
their integrity verifier. Their matching table hashes and required Docker image
identities were checked. Scientific review remains pending; these checks do not
enable official grading or establish scientific qualification.

## Campaign and execution terminology consolidation (2026-10-02)

The dashboard selection now explicitly references the retained pilot manifest.
Its source manifest, launch receipt and scientific outputs were not rewritten.
New preparations assign UUID campaign/run identities, relative campaign paths and
per-plan hashes. The retained v1 adapter derives identities from the original
manifest; unassigned legacy directories keep labeled location-based identities.
Navigation selects one task execution even inside a legacy multi-task batch.

Local HTTP observations returned 200 for the page, navigation script, campaign
projection and individual completed/pending views. The pilot reports six planned
runs, one completed and five not started, zero missing, and the retained disk-space
stop reason. Both model groups declare public-demo references, without context
conflicts. The completed execution has an observed public-demo reference; the
pending execution's observed scope stays null. Incomplete groups withhold rates
while keeping lifecycle counts and retained scientific verdicts distinct.

Python AST parsing, JavaScript syntax checks and `git diff --check` passed during
this consolidation. The earlier regression totals above describe earlier checks;
the regression suite and rendered-browser review were not rerun for this change.
No new model calls or native runs were launched. The first pilot's final score is
100/100 with a coherent review; its five remaining slots were not dispatched.

## Final dashboard regression and browser QA (2026-10-02)

This checkpoint supersedes the previous section's unexecuted regression/browser
checks. The following checks passed on the consolidated dashboard:

- Full portable Python suite: **387 tests**, using
  `python3 -B -m unittest discover -s tests -p 'test_*.py' -q`.
  Expected CLI validation errors are emitted by negative tests; the suite exits 0.
- Node EN/FR run templates; campaign templates against both the retained pilot
  and a synthetic multi-campaign selection; future configuration/evaluator
  contracts and interrupted historical report templates.
- Real headless Chrome **154.0.8037.93**, driven by an existing Playwright install:
  cascading navigation; two task attempts inside a legacy batch; a deliberately
  delayed response during rapid navigation; all six views in English/French;
  language persistence; separate campaigns; matrix drilldown; visible stale-data
  notices after a network failure; escaped task text; keyboard focus; and no
  horizontal page overflow at 390 px in any view. No JavaScript page errors.
- Desktop and mobile screenshots inspected, plus a rendered overview of the
  retained pilot. The primary server remains available at 127.0.0.1:8765.

Regression fixes include a colliding selector event handler, stale responses
after navigation, ambiguous topbar context in the comparison view, coding-tool
counts without dedicated receipts, and unsafe comparison denominators after an
imported identity conflict. Added controls reject malformed/changed manifests,
duplicate identities, path escapes and unreadable launch receipts. A launcher
completion flag without a supported reviewed score no longer counts as a
completed assessment.

The synthetic importer test reconstructs a sealed 150-record archive, checks
retained success counts and the unresolved incident, verifies inherited reviews,
and refuses seal tampering. Serial-launcher tests cover balanced 150-slot
preparation, disk reserve, scientific failure continuation, and stopping without
retry after an unscored incident. Provider and evaluator calls are replaced by
fixtures in these tests. No new paid model calls, native solver executions or
real 150-run campaign were launched for this QA pass.

Local evidence: `scratch/dashboard-final-qa/python-tests.log`, saved API payloads,
`browser/result.json`, `browser/campaign-desktop.png` and
`browser/campaign-mobile.png`. These generated artifacts are intentionally not
published. Reproducible browser commands are in `dashboard/README.md`.
The deleted historical campaign was not restored. Browser coverage is Chromium
only and is not a full accessibility audit; it does not establish scientific
qualification, provider reliability or causal benefit from agent tools.
