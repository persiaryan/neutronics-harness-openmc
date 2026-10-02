# Dashboard validation — 2026-10-02

Branch: `feat/local-run-dashboard`, based on `b4780ab097efba286fcaa85c8e90d93dbb020f03`.
Implementation and evidence remain local and uncommitted. This is an observation
and integration demonstration, not a new A/B efficacy study.

## Checks actually executed

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
