Guided smoke execution policy: guided-smoke-v1 (new experimental condition).

After successfully exporting your working factory, invoke:
python3 /work/smoke_openmc.py model.xml

The file must be inside /work/workspace. This command passes only your XML to
a separate isolated native OpenMC 0.15.3 process. It cannot access a reference
model, expected answer or score. Print its complete default JSON response and
collect command completion if your execution tool returns a running session.
Read the process outcome, native stdout/stderr, coverage and limitations before
your next decision. Logs with complete=false are excerpts: read full_result.path
using ordinary Python for the longer retained report, without launching another run.

This is a diagnostic copy, using 1000 particles, 8 batches, 2 inactive batches,
1 generation per batch and seed 1. It writes a final-batch statepoint and suppresses
separate source output. It binds the operator-selected nuclear-data index in the
smoke container. Original and smoke XML hashes and exact overrides are retained.
Geometry, materials, boundary properties, source distributions and temperature
settings are not repaired. Keep the task's requested settings in your final factory;
do not copy reduced smoke sampling into the submission. Do not change physics
merely to satisfy an inspector limitation or to silence a diagnostic.

At most TWO attempts are available, each with a 60-second native-process limit,
within the same 8-request / 600-second authoring allowance. Setup and cleanup take
additional time within the session; a request requires at least 180 seconds left.
Use the first run early enough to interpret feedback and make one justified repair
if needed. After a change, re-export and use the second run when resources permit.
Re-inspect changed boundaries when that tool's allowance permits. No automatic
repair or retry occurs. If a run fails, is interrupted or cannot start, report the
actual blocker; do not claim success. Disclose any final revision not retested.

completed means only that this short execution and its output validation completed.
It is not evidence of convergence, global geometry validity or task conformity.
No points are awarded for tool use. Final evaluation independently rebuilds the
frozen submitted factory and uses the unchanged full assessment settings.
