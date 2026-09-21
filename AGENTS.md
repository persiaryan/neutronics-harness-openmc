# AGENTS.md

## Project purpose
Neutronic Harness evaluates LLM-driven neutronics modeling.
Read DESIGN.md for the scientific objective and accepted boundaries.

The owner knows Python and nuclear engineering.
Keep critical execution paths understandable to the owner.

## Read before working
- README.md: implemented behavior and verified commands.
- DESIGN.md: accepted contracts and unresolved decisions.
- The user's current task, scope, and acceptance criteria.
- Relevant source files and tests.

Do not assume that previous chat discussions are available.
Do not treat proposed decisions as accepted requirements.

## Working modes
For design or critique requests:
- Inspect relevant material and propose a small design.
- Explain consequential alternatives and assumptions.
- Do not modify code unless implementation is explicitly requested.

For an explicitly authorized implementation:
- Complete the current task, including its required verification.
- Make routine implementation decisions within the agreed contract.
- Stop before expanding scope or changing an accepted contract.
- Do not proceed automatically to the next task.

## Scope and simplicity
Prefer direct functions and explicit data flow.
Introduce abstractions only for a concrete current requirement.
Do not add frameworks, dependencies, or generic extension systems
without explaining why the current task requires them.

Do not refactor unrelated code.
Do not import v4 components wholesale without review.
Do not modify these instructions to bypass a task constraint.

## Scientific integrity
Preserve the boundaries documented in DESIGN.md.
Do not silently add physical assumptions or repair candidate models.
Do not expose private grading references to the evaluated LLM.
Do not weaken acceptance criteria to make an implementation pass.

## Verification
Use the commands documented in README.md.
Test specified behavior, including relevant failure cases.
Do not derive every expected result from the implementation under test.
Distinguish passed, failed, skipped, and unexecuted checks.
If the required environment is unavailable, report that limitation.

## Handoff
Report:
- What changed and why.
- The critical execution path, with file/function references.
- Checks actually run and their results.
- Remaining limitations and decisions requiring owner review.

Do not claim the task is accepted on the owner's behalf.
Do not commit, push, or publish unless explicitly requested.
