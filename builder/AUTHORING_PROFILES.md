# Authoring request profiles

P5 ports the optional `authoring-requests-16-v1` profile and request-setup
comparison from experimental continuation
`1c2e805edf1303c0ebf0cfb84b2e226bf1917976`. The default remains eight requests.
This is an authoring configuration, not a new scientific assessment protocol.

## Prepare an explicit profile

This command only prepares public inputs and a plan:

```sh
python3 -B -m experiments.run prepare \
  --assistance guided_construction \
  --request-budget authoring-requests-16-v1 \
  --output scratch/condition-A-request16
```

Use the same flag for B (`guided_boundaries`) and C
(`guided_boundaries_smoke`). C also requires
`--smoke-data-index "$DATA_INDEX"`; see [smoke preparation](SMOKE.md).
Omitting the profile preserves eight requests; unknown profiles are rejected.
Always use a new output directory. Existing plans and historical receipts are
not relabelled.

Preparation binds the profile, per-task and total request budgets, and condition
prompt hashes. Execution rejects inconsistent declarations before dispatch.
Sixteen requests still share **600 authoring seconds**. Boundary limits remain
two 120-second calls; C retains two 60-second native smoke attempts with a
180-second admission reserve. Tool access and zero automatic retries are
unchanged. Only existing budget wording in appended guidance changes; public
task text is preserved.

The lower-level `builder.run` CLI requires both
`--request-budget authoring-requests-16-v1 --max-requests 16` to select the
full allowance. Its `--max-requests` default remains eight even with the
profile flag. A smaller explicit cap is allowed. The controller rejects the
ninth default or seventeenth extended request before forwarding.

## Check matched request configuration

For an A/B/C comparison, select the same request profile and generic provider
configuration within each agent setup. Condition guidance and specialist tool
access still differ intentionally. Different model setups need not match one
another.

The Python API accepts an optional reviewed expected setup:

```python
from builder.context import request_setup

# retained_body is an operator-reviewed request, not a new health probe.
expected = request_setup(retained_body)
# For a separately authorized live run:
# experiments.run.execute(output, request_setup=expected)
# or builder.run.run(..., request_setup=expected)
```

This descriptor contains the selected request configuration fields, a hash of
generic tool declarations, adapter instruction inventory and instruction hashes.
It excludes task/history content and only the session-generated top-level
`additional_tools` IDs. Semantic tool changes, including nested IDs, remain
visible. Model identity is checked separately. It does not copy authentication
fields or raw tool schemas.

The API caller must provide the expected descriptor explicitly; it is not
learned from the first dispatched request. It is bound in the builder manifest,
not yet in a prospective study manifest or CLI setup file. Omitting it makes no
matched-configuration claim. Do not adopt an unreviewed request merely to bypass
a mismatch.

Every request is compared before forwarding. A first or later mismatch retains
the request and a failed `setup-NN.json` receipt, stops the session and makes
no provider call for that request. `request_count` counts received request
events within the cap; it does not necessarily count forwarded or billed requests.

`builder.submission.submission()` rechecks the profile/prompt, integer cap,
request count and files, model identity, declared setup and validation receipts,
and C adapter availability/identity. Failed or unclean runs do not qualify as
submissions. These checks do not assign scientific credit or alter scores.
Hashes detect inconsistent records; they cannot protect against an operator
rewriting all bindings.

## Verification and limits

```sh
python3 -B -m unittest tests.test_request_profiles -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

The controls use synthetic requests and local process doubles. They check
defaults, opt-in, cap enforcement, configuration mismatch, retained-evidence
tampering, A/B/C routing and unchanged resource limits without credentials,
model calls or native OpenMC execution. Mock inference alone does not disable
native tools; those are separately doubled in these tests.

No live client/provider qualification, new study, trajectory reconstruction or
study-manifest framework is included. The scientific route remains
`factory-assessment-boundaries-v4-temperature-source-v1`; historical results
are unchanged and full experimental v7 parity is not claimed.
