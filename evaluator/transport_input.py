"""Data-only admission for the first continuous-energy transport stage."""
import json
from pathlib import Path

from evaluator.inspect import inspect_model, parse_xml
from evaluator.run import MAX_ARTIFACT, digest
from evaluator.evidence import InsufficientEvidence
from evaluator.contracts import export_contract


def read_regular(path, limit=MAX_ARTIFACT):
    if not path.exists() and not path.is_symlink():
        raise InsufficientEvidence('Missing evidence file: ' + str(path))
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected regular evidence file: ' + path.name)
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Evidence file exceeds byte limit')
    return data


def accepted_export(directory):
    """Read an operator-owned receipt, never candidate Python or extra artifacts.

    Hashes bind these local records; they are not signatures against an operator
    who can rewrite the records and XML together.
    """
    if directory.is_symlink() or (directory / 'artifacts').is_symlink():
        raise ValueError('Export directories must not be symlinks')
    records = {name: read_regular(directory / name) for name in
               ('result.json', 'manifest.json', 'artifacts.json', 'lifecycle.json')}
    result, manifest, artifacts, lifecycle = (json.loads(records[name]) for name in records)
    export_contract(manifest)
    if (result.get('status') != 'exported' or result.get('xml_validation') != 'passed'
            or result.get('cleanup_confirmed') is not True or lifecycle.get('state') != 'removed'):
        raise ValueError('Transport requires a successful export with confirmed cleanup')
    xml = read_regular(directory / 'artifacts/model.xml')
    if artifacts.get('model.xml') != {'bytes': len(xml), 'sha256': digest(xml)}:
        raise ValueError('Export model.xml does not match its recorded artifact identity')
    inspect_model(xml)
    return xml, {'export_directory': str(directory),
                 'candidate_sha256': manifest.get('candidate_sha256'),
                 'model_xml_sha256': digest(xml),
                 'receipt_sha256': {name: digest(raw) for name, raw in records.items()}}


def transport_profile(xml, index_name):
    """Reject unsupported inputs, never normalize/re-export candidate settings."""
    inspect_model(xml)
    root = parse_xml(xml)
    for section in ('plots', 'tallies'):
        node = root.find(section)
        if node is not None and (len(node) or node.attrib):
            raise ValueError('Nonempty ' + section + ' are outside the S05 profile')
    geometry = root.find('geometry')
    if any(child.tag not in {'cell', 'surface', 'lattice', 'hex_lattice'} for child in geometry):
        raise ValueError('Only inline constructive solid geometry is supported')
    materials = root.find('materials')
    if any(child.tag not in {'material', 'cross_sections'} for child in materials):
        raise ValueError('Unsupported material section')
    indexes = materials.findall('cross_sections')
    if len(indexes) > 1 or (indexes and (indexes[0].text or '').strip() != '/data/' + index_name):
        raise ValueError('Explicit nuclear-data index must match the admitted /data index')
    # No file-backed data or executable extension may be introduced through XML.
    for node in root.iter():
        if (node.tag in {'file', 'library', 'path', 'filename', 'directory', 'dagmc_universe',
                         'macroscopic'} or
                set(node.attrib) & {'file', 'library', 'path', 'filename', 'directory'}):
            # A local output path is the sole supported path option.
            if node.tag != 'path' or node not in root.findall('settings/output/path') or node.text != '.':
                raise ValueError('External paths and compiled/file-backed inputs are unsupported')
    settings = root.find('settings')
    allowed = {'run_mode', 'energy_mode', 'particles', 'batches', 'inactive',
               'generations_per_batch', 'seed', 'source', 'temperature_default',
               'temperature_method', 'temperature_tolerance', 'temperature_multipole',
               'temperature_range', 'mesh',
               'entropy_mesh', 'output', 'state_point', 'source_point', 'verbosity'}
    unsupported = sorted({child.tag for child in settings} - allowed)
    if unsupported:
        raise ValueError('Unsupported S05 settings options: ' + ', '.join(unsupported))
    for tag in allowed - {'source', 'mesh'}:
        if len(settings.findall(tag)) > 1:
            raise ValueError('Duplicate settings option: ' + tag)
    if settings.findtext('run_mode', 'eigenvalue').strip() != 'eigenvalue':
        raise ValueError('Only eigenvalue mode is supported')
    if settings.findtext('energy_mode', 'continuous-energy').strip() != 'continuous-energy':
        raise ValueError('Only continuous-energy mode is supported')
    for source in settings.findall('source'):
        if source.get('type', 'independent') != 'independent':
            raise ValueError('Only inline independent sources are supported')
        if source.get('particle', 'neutron') != 'neutron':
            raise ValueError('Only neutron sources are supported')
    for mesh in settings.findall('mesh'):
        if mesh.get('type', 'regular') != 'regular':
            raise ValueError('Only inline regular meshes are supported')
        dimensions = [int(v) for v in mesh.findtext('dimension', '').split()]
        cells = 1
        for dimension in dimensions:
            if dimension < 1:
                raise ValueError('Invalid mesh dimensions')
            cells *= dimension
        if not 1 <= len(dimensions) <= 3 or cells > 1_000_000:
            raise ValueError('Mesh exceeds supported size')
    sampling = {}
    for tag, default in (('particles', ''), ('batches', ''), ('inactive', '0'),
                         ('generations_per_batch', '1'), ('seed', '1')):
        sampling[tag] = int(settings.findtext(tag, default))
    p, b, i, g, seed = (sampling[k] for k in
                        ('particles', 'batches', 'inactive', 'generations_per_batch', 'seed'))
    if not (1 <= p <= 1_000_000 and 2 <= b <= 10_000 and 0 <= i < b - 1
            and 1 <= g <= 100 and 1 <= seed < 2**63 and p * b * g <= 50_000_000):
        raise ValueError('Sampling exceeds supported budgets or has insufficient active batches')
    for section, fields in (('output', {'summary', 'tallies', 'path'}),
                            ('state_point', {'batches'}),
                            ('source_point', {'batches', 'separate', 'write', 'overwrite'})):
        node = settings.find(section)
        if node is not None and (node.attrib or any(c.tag not in fields for c in node)):
            raise ValueError('Unsupported ' + section + ' option')
    statepoint = settings.find('state_point')
    if statepoint is not None and b not in [int(n) for n in statepoint.findtext('batches', '').split()]:
        raise ValueError('A final-batch statepoint is required; settings are not repaired')
    required = set()
    for material in materials.findall('material'):
        if any(c.tag not in {'density', 'nuclide', 'sab', 'isotropic', 'temperature', 'volume'}
               for c in material):
            raise ValueError('Only explicit nuclide materials are supported')
        required.update(('neutron', n.get('name', '')) for n in material.findall('nuclide'))
        required.update(('thermal', n.get('name', '')) for n in material.findall('sab'))
    if not required or any(not name for _, name in required):
        raise ValueError('Materials must name their nuclear data')
    return {'sampling': sampling, 'entropy_requested': settings.find('entropy_mesh') is not None,
            'required_tables': [list(item) for item in sorted(required)],
            'scientific_inputs_changed': False, 'scope': 'bounded_ce_eigenvalue_inline_csg'}
