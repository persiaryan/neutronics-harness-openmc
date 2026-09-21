"""Small versioned execution profiles. No reference answers or task-specific checks."""
from copy import deepcopy
from evaluator.contracts import FACTORY

FACTORY_PROFILE = 'factory-serial-v1'
BOUNDARY_PROTOCOL = 'factory-assessment-boundaries-v4'
PROFILE = dict(id=FACTORY_PROFILE, delivery_contract=FACTORY,
    budgets=dict(export=60, inspection=120, transport=1800, automatic_retries=0),
    observer_completion_grace=10, export_prerequisite_seconds=30, retrieval_seconds=30,
    export_cpus=2, export_memory_bytes=2147483648, native_threads=1,
    export_image='sha256:bb4e5420624725c5c1f6899ed766a50a1e3addc30daa04a0eb1d03f9838f7930',
    transport_image='sha256:08dc044b81f87eb3762c1adeb11ad422d8dfc8a2847d04a1d1e2de2d0817c835')


def execution_profile(identifier, contract):
    if identifier != FACTORY_PROFILE or contract != FACTORY:
        raise ValueError('Execution profile and delivery contract do not match')
    return deepcopy(PROFILE)


def assessment_route(contract, profile, protocol):
    value = execution_profile(profile, contract)
    if protocol != BOUNDARY_PROTOCOL:
        raise ValueError('Unsupported evaluator protocol for factory execution')
    return dict(delivery_contract=contract, execution_profile=value, evaluator_protocol=protocol)
