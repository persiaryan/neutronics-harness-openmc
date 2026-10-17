# Selective native region skill: condition E

## Current status — 2026-10-17

E makes the existing region procedure available through the **native skill
catalog of Codex CLI 0.153.4**. Its initial task prompt is byte-for-byte A's prompt.
Only the skill name, description and path enter the initial catalog. The builder
can choose to read SKILL.md using its existing coding tools; the controller does
not issue that read on its behalf. D remains the complete preloaded procedure.

This implements the progressive-disclosure mechanism described in the
[official skills documentation](https://learn.chatgpt.com/docs/build-skills).
Compatibility here is checked against the actual pinned CLI, rather than
inferred from the current documentation.

Verified on 2026-10-17: 426 portable tests passed; six native CLI controls
passed across the Luna and Sol request configurations (eight synthetic protocol
requests total). All six containers were cleaned up. No model inference or
neutron transport ran.

| Question | Evidence/status |
|---|---|
| Does the pinned CLI discover only the allowlisted skill metadata? | Checked offline with the real CLI |
| Can the session complete without reading the body? | Checked with a scripted no-read response |
| Can a full read reach a subsequent request and completed response? | Checked with a scripted read response |
| Does an LLM spontaneously select this skill when writing shared regions? | **Not tested** |
| Does the LLM apply it correctly and reduce region failures? | **Not tested** |
| Does it improve independent scientific assessment? | **Not tested** |

The native controls use real containers, filesystem reads and CLI requests but
**scripted provider responses**. They make no external model calls and run no
neutron transport. They are plumbing evidence, not automatic-selection or
efficacy results. The earlier
[dated D checkpoint](region-ownership-skill-v1.md#evidence-boundary-recorded-on-2026-10-17)
remains a historical record.

## Implementation and trust boundary

1. `builder.region_skill.material(E)` reads the same bounded, non-linked skill
   source as D. Its identity adds the native delivery mode, container path,
   catalog digest and staging-program digest.
2. `experiments.run.prepare` freezes both the skill body and exact expected
   catalog alongside the ordinary prompt hash. `execute` verifies these before
   dispatch and passes the expected identity to the builder.
3. After the existing container boundary/package probes and before starting the
   CLI session, `builder.region_skill.stage` writes that one allowlisted file
   under `/work/.agents/skills/openmc-region-ownership/SKILL.md`. An empty
   `/work/.git` directory marks the native discovery root. It contains no host
   repository or history. Home, state and workspace remain fresh.
4. The existing image, entrypoint, network isolation and host-mount exclusions
   remain. The system skills stay disabled. No evaluator, private reference,
   detector, repair tool, nuclear data or new candidate tool is installed.
5. `initial_context` requires the exact single native catalog in E, A's exact
   user prompt, and no preloaded body or memory block. A/B/C/D continue to reject
   catalogs. A changed catalog fails before forwarding the first request.
6. `builder.submission.submission` checks the frozen skill/catalog, staging
   receipt, first context and existing source/provenance evidence.
7. `builder.trajectory.summarize` adds the operator-only `region_skill` record
   using `builder.skill_exposure.summarize`. Final assessment remains independent.

The skill file is mode 0444 to discourage accidental edits. The candidate owns
its temporary filesystem and can change its contents or permissions: this is
**not** a tamper-proof file service. Exposure recognition therefore requires
the exact original bytes in both execution and delivery evidence. Hashes also
do not protect against an operator rewriting all evidence.

## What the trace can establish

Catalog presence and catalog delivery are separate fields. Delivery requires a
retained completed response for the initial request.

The conservative body recognizer joins a uniquely bound literal
`cat /work/.agents/skills/openmc-region-ownership/SKILL.md` command, successful
runtime completion with the exact full file, the corresponding call ID/output
in a later request, and a completed response for that later request. Both
invocation and delivery responses must be complete and pass any declared setup
check. Partial output, wrong call IDs, failed commands, missing runtime events,
ambiguous wrappers or missing completion cannot produce a positive observation.

Other reading commands can work for the agent, but remain
`body_loading=not_demonstrated` until manually reviewed. This field does **not**
mean the skill was never read. `application=not_inferred`: neither full exposure,
a statement by the builder nor the presence of `&` instead of `&=` demonstrates
correct reasoning or globally valid geometry.

The existing shareable trajectory projection does not yet export this new
operator field. Raw requests and command transcripts stay local. The
[allowlisted native-control report](region-skill-native-controls-v1.json)
contains only control outcomes, counts and identities.

## Offline commands

Portable preparation does not invoke Docker, a provider or transport:

~~~sh
python3 -B -m experiments.run prepare \
  --assistance guided_construction_region_skill_selective \
  --request-budget authoring-requests-16-v1 \
  --cases two_composition_5x5 axially_zoned_5x5 reflective_pin_cell \
  --output scratch/region-skill-E
~~~

The explicit native qualification requires the existing local pinned authoring
image. It prepares A, E without a read, then E with a scripted read, serially.
Run each configuration separately in a fresh directory:

~~~sh
python3 -B -m builder.region_skill_qualification \
  --model gpt-5.6-luna --output scratch/native-skill-luna
python3 -B -m builder.region_skill_qualification \
  --model gpt-5.6-sol --output scratch/native-skill-sol
~~~

The recorded controls use four synthetic requests per configuration. These are local
protocol requests, not billed inference. It records the requested model's CLI
configuration; it does not qualify actual provider behavior.

Portable regression checks:

~~~sh
python3 -B -m unittest tests.test_selective_region_skill -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
~~~

## Preparing the A/D/E development comparison

`region-ownership-ade-v1` is a new opt-in comparison, leaving the earlier
36-slot A/D and historical A/B/C preparations unchanged. It prepares
**54 pending assignments**: two model configurations × A/D/E × three reused
tasks × three repeats. Budgets are 16 requests and 600 seconds per assignment,
zero retries: at most **864 model requests** if later executed. The skill read
uses the ordinary session budget; E gets no extra allowance. Shuffle seed is
20261016.

The three arms address different practical questions:

| Comparison | Question |
|---|---|
| A versus D | Does providing the full targeted procedure improve outcomes? |
| A versus E | Does offering it as a native selectable skill improve outcomes? |
| D versus E | What changes when discovery and reading become the agent's responsibility? |

This design estimates intervention effects only after actual randomized runs,
with appropriate uncertainty. Observed loading is a post-assignment behavior;
comparing loaders with non-loaders alone is not a causal estimate of skill use.
Three repeats and reused tasks do not establish power or holdout generalization.

A/D share the reviewed baseline request setup. E must use the same tools,
reasoning and remaining instructions plus exactly the qualified catalog part.
The setup JSON has this structure, with complete reviewed setup objects:

~~~json
{
  "gpt-5.6-luna": {"A": {}, "D": {}, "E": {}},
  "gpt-5.6-sol": {"A": {}, "D": {}, "E": {}}
}
~~~

The empty objects above are illustrative and rejected by validation. Native
qualification reports contain candidate setup objects for operator review.
Do not reuse a Luna setup for Sol or treat mock responses as provider
qualification. Review effective settings before a live study.

~~~sh
python3 -B -m experiments.dashboard_campaign prepare \
  --comparison region-ownership-ade-v1 \
  --data-index "$DATA_INDEX" --setups "$REVIEWED_ADE_SETUPS" \
  --output scratch/region-skill-ade-54
~~~

Preparation dispatches nothing. The separate `run` action makes live calls and
independent native assessments, consumes slots, and pauses on incidents. No live
campaign is authorized by the offline commands. Final assessment of these three
tasks still requires the corresponding private references and data.

Before execution, freeze a mechanism-annotation protocol and denominators:
all assigned slots, scored model failures, unscored incidents, catalog/body
exposure evidence, alias defects demonstrable from source, other geometry or
settings failures, requests, available tokens and time. Correct attribution
requires source/XML review; missing observations remain unresolved. To support
a confirmatory paper, add a sample-size justification and held-out geometry
variants without tuning on their outcomes.
