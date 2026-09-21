"""The only active delivery contract."""
FACTORY='openmc-model-factory-v1'
CONTRACTS=(FACTORY,)


def export_contract(manifest):
    if manifest.get('format')!='isolated-export-evaluation-v2' or manifest.get('delivery_contract')!=FACTORY:
        raise ValueError('Unknown or contradictory export delivery contract; restore checkpoint for historical records')
    return FACTORY
