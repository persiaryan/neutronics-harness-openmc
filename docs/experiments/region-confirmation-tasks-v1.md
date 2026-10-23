# Twelve candidate tasks for region-procedure confirmation

Created on 2026-10-18 at the owner's request. The initial specification release
was unqualified. A [versioned implementation and qualification workflow](region-confirmation-implementation-v1.md)
now connects the new suite to native controls, private references and independent
end-to-end assessment. Actual readiness comes from selected qualification evidence,
not from this release-time description.
No agent generation or confirmation campaign has been run on this suite.
These tasks are candidates for a future frozen study, not an already qualified
held-out benchmark. The existing six-task catalog, frozen references, development
pilot protocol and skill bytes are unchanged.

## Research question and selection

Primary question: does providing the fixed region-ownership procedure improve
complete protocol success on new tasks? Secondary question: does it reduce
demonstrable damaging mutations of shared region objects?

The twelve tasks vary geometric organization rather than only dimensions of
the old lattices. The groups are prospective coverage hypotheses; task membership
does not assert that an agent will share objects, make the target error, or be
unaffected by D. The public statements prescribe physics and permit alternative
correct representations. They do not prescribe Python operators or skill use.

| Group | Task ID | New construction or control |
|---|---|---|
| Reuse | offset_plate_bank | Finite clad plates, open side/axial ends and asymmetric outer water |
| Reuse | staggered_seven_pin_cluster | Explicit non-Cartesian centers and finite pin envelopes |
| Reuse | three_annular_fuel_channels | Water inside and outside annular fuel rods |
| Reuse | separated_twin_bundles | Disconnected fuel groups with different compositions |
| Transfer | cross_shaped_mixture | Intersecting prisms describing one union volume |
| Transfer | perforated_mixture_block | Several water holes removed from a finite body |
| Transfer | stepped_axial_mixture | Different transverse footprints in touching axial sections |
| Transfer | wrapped_eight_pin_channel | Pin envelopes, a central tube and a square wrapper shell |
| Control | mixed_boundary_fuel_slab | Different boundary types on different axes |
| Control | cylindrical_void_sleeve | Version 2: finite void sleeve in a rectangular water exterior |
| Control | dual_temperature_pin_pair | Same composition at two effective fuel temperatures |
| Control | restricted_source_nine_pin | Initial source support different from entropy-mesh support |

This deliberately structured set is not a representative random sample of
OpenMC applications. Results must be reported per task and family. Publishing
specifications does not reserve them from all future model training or establish
contamination freedom. Development/tuning on their generation outcomes would
remove their status as unused confirmation candidates.

## Public artifacts and preparation

[The manifest](../../prompts/confirmation_v1/manifest.json) binds each standalone
statement and the existing factory template by SHA-256. It records source/entropy
boxes, group membership and explicit unqualified states. It contains no reference
implementation, expected eigenvalue, private path or grading answer.
The renderer reads only allowlisted public files. The historical CASE_FILES
catalog remains the original six tasks. The new IDs are admitted through the
explicit confirmation protocol; a mismatched historical protocol is rejected
before authoring dispatch.

~~~sh
python3 -B -m prompts.confirmation --check
python3 -B -m prompts.confirmation --case cross_shaped_mixture \
  --output scratch/confirmation-cross-prompt
python3 -B -m unittest tests.test_confirmation_tasks -v
~~~

Preparation creates prompt.txt, messages.json and manifest.json in a fresh
directory. The prompt contains the existing factory contract and one complete
task statement. Family labels, planned arms and qualification notes stay outside
the agent message. No provider, Docker, OpenMC or private reference is accessed.

At the initial release checkpoint on 2026-10-18, the 12 specification/template bindings passed the inventory
check; all 12 prompt bundles pass the targeted tests, including changed-byte,
private-path, symlink and overwrite rejection. All 441 portable tests pass.
No native check had run at that initial checkpoint. Native qualification is now a separate recorded workflow; consult its retained status before claiming readiness.

The original cylindrical-exterior statement is retained in
`prompts/confirmation_v1/archive/cylindrical_void_sleeve-v1.md`. Its replacement
was made before evaluated-agent generations; no curved-boundary extension is claimed.

The historical pilot's 94 frozen implementation files match commit
`72a9895` exactly. Adding this suite changes the current campaign source
inventory, so use that commit and the original local evidence for historical
pilot verification. Do not reseal the old manifest against the new checkout.

## Qualification work required before a campaign

For every task: review the physical statement, independently author and inspect a
private reference, qualify data at every required temperature, export and test
the geometry, and run convergence/uncertainty diagnostics before fixing numerical
criteria. Review finite observer coverage and its false-negative limits. Demonstrate
that correct implementations pass and appropriate deliberately incorrect controls
fail. No expected k-effective or acceptance tolerance is invented here.

Specific independent geometric or semantic checks to include:

| Task | Qualification checks, not results already obtained |
|---|---|
| offset_plate_bank | Five separated plates; fuel volume 720 cm3; gap volume 57.6 cm3; cladding volume 144 cm3; side/end water and uncovered outer box |
| staggered_seven_pin_cluster | Seven distinct centers; no envelope overlap; fuel/gap/clad radial witnesses at each center and beyond axial ends |
| three_annular_fuel_channels | Three water bores; fuel volume 3*pi*(0.55^2-0.18^2)*32 cm3; separate bore/gap/clad/exterior witnesses |
| separated_twin_bundles | Four A and four B pins; water between bundles and above/below them |
| cross_shaped_mixture | Cross-section area 36 cm2 and volume 1080 cm3; center counted once; water in all four corners |
| perforated_mixture_block | Mixture volume 2400-3*pi*0.60^2*30 cm3; all three bores connected to axial water |
| stepped_axial_mixture | Mixture volume 1128 cm3; water on both exposed steps; no artificial separating gaps |
| wrapped_eight_pin_channel | Eight fuel pins; water central bore; wrapper volume 74.6496 cm3; water above/below open ends |
| mixed_boundary_fuel_slab | Fuel volume 12 cm3; vacuum only on x; reflective on y,z |
| cylindrical_void_sleeve | Mixture volume 384*pi cm3; void volume 39.36*pi cm3; end square sections completely water |
| dual_temperature_pin_pair | Effective left/right fuel 293.6/600 K; unchanged recipe/density; water/clad 293.6 K; required tables available at 1 K tolerance |
| restricted_source_nine_pin | Source volume 0.4 cm3, entirely inside central fuel; source limits distinct from full entropy mesh |

These formulas are design-review aids. They are not native geometry observations
or proof that the existing evaluator can assess these tasks. In particular the
nonrectangular internal bodies, material partitions, temperature and source
semantics need explicit observer qualification. Missing coverage must remain
unresolved; do not weaken acceptance criteria to admit these cases.

## Proposed experiment and decision gates

The proposed inventory is 12 tasks x 2 model configurations x A/D x 5 repeats =
240 assignments. At 16 requests per assignment the ceiling is 3840 requests,
plus separately budgeted qualification and final assessments. The sample size
is a proposal, not a power justification or executable campaign manifest.
Keep the 600-second authoring allowance matched within each model setup.

Before launching, decide the smallest relevant improvement, analysis of variation
between tasks, incident policy, stopping rules, masked source-review procedure,
and whether a procedural placebo is needed for the intended claim. A/D estimates
the effect of the complete additional procedure, including extra context; it does
not isolate domain content from generic extra instruction.

Freeze reviewed statements/references, evaluator coverage, skill, provider setups,
data/runtime identities, assignments and randomized execution order before calls.
Retain every consumed assignment and report full success, targeted mechanisms,
other failures, incidents and resource consumption. E's spontaneous skill selection
remains a separate hypothesis and is not tested by this candidate suite.

See [the confirmation design](region-ad-confirmation-plan-v1.md).

## Owner-selected public replacement

The current renderer uses confirmation_v2/manifest.json, suite
region-confirmation-candidates-v3. Its sixth task is indc107_reflective_pin
(external_control) instead of perforated_mixture_block. This document's original
twelve-task table describes the retained release. The replacement and its
changed coverage are described in [the frozen-source record](indc107-replacement-v1.md).
