Additional guided inspection policy: guided-working-export-boundaries-v3.
This is instructed use, not spontaneous use or a runtime guarantee. It earns no
scientific points.

After a successful working export, you MUST execute:
python3 /work/inspect_boundaries.py model.xml
Read the returned observations AND limitations in a subsequent decision turn
before final submission. Print the complete compact JSON (at most 16,000 bytes).
The command saves the full JSON at full_result.path. Read that saved file with
ordinary Python for additional fields or recovery; do not rerun inspection merely
to recover output. If feedback_complete is false, read the explicitly omitted
sections before interpreting them. A complete presentation may still report
unresolved observations; it does not establish conformity.
Compare effective behavior with the PUBLIC task. Do not invent private expected
values. Unsupported observations are indeterminate, not proof of compliance or
invalid physics. Never replace the requested geometry or physics merely to fit
the observer's supported scope. The command provides no score or automatic repair.

Allow at most one observation-driven correction pass, justified by the public
task and actual feedback; a scientific correction is not always needed or possible.
Re-export after any model change. Re-inspect changed boundaries if the remaining
two-call allowance and time permit. Otherwise disclose, in an authoring message
and a brief final-source comment, that the changed artifact was not re-inspected.
An export error or an indeterminate/refused inspection must be reported honestly,
not silently treated as a completed or passing check.

Use the existing eight-request / 600-second session ceiling. Aim to start the
first inspection within 300 seconds and leave at least two model requests for
reading feedback and possible correction. No inspection starts with less than
180 seconds remaining; each worker has 120 seconds and the session has two
inspection attempts total. These are limits, not permission to exceed the
launcher's configured budget. There are no extra requests or automatic retries.
If resources prevent the required sequence, disclose which steps remain undone.
