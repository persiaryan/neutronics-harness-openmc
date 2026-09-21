"""Trusted XML loader and statepoint reader. Never imports submitted Python."""
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
import openmc


def write_json(name, value):
    Path(name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_xml():
    model = openmc.Model.from_model_xml('/work/model.xml')
    # Loading is an independent check; this Python object is never re-exported.
    s = model.settings
    settings_xml = ET.parse('/work/model.xml').getroot().find('settings')
    defaults = {'inactive': 0, 'generations_per_batch': 1, 'seed': 1}
    sampling = {name: int(settings_xml.findtext(name, str(defaults.get(name, ''))))
                for name in ('particles', 'batches', 'inactive', 'generations_per_batch', 'seed')}
    for name, expected in sampling.items():
        value = getattr(s, name)
        if value is not None and value != expected:
            raise ValueError('Loaded settings disagree with submitted XML: ' + name)
    checks = {
        'only_model_input': sorted(p.name for p in Path('/input').iterdir()) == ['model.xml'],
        'no_candidate_python': not Path('/input/candidate.py').exists(),
        'no_old_harness': not Path('/opt/nh').exists(),
        'no_operator_home': not Path('/Users').exists(),
        'no_reference_directory': not Path('/evaluation').exists(),
        'identical_staged_xml': file_hash('/input/model.xml') == file_hash('model.xml'),
    }
    if not all(checks.values()):
        raise RuntimeError('XML worker boundary checks failed')
    write_json('xml-load.json', {
        'status': 'loaded', 'openmc_version': openmc.__version__,
        'model_xml_sha256': file_hash('model.xml'), 'sampling': sampling,
        'entropy_requested': s.entropy_mesh is not None,
        'material_count': len(model.materials),
        'cell_count': len(model.geometry.get_all_cells()),
        'scientific_inputs_changed': False,
        'boundary_checks': checks})


def extract():
    loaded = json.loads(Path('xml-load.json').read_text())
    expected = loaded['sampling']
    statepoint = Path(f"statepoint.{expected['batches']}.h5")
    with openmc.StatePoint(statepoint, autolink=False) as sp:
        actual = {'particles': int(sp.n_particles), 'batches': int(sp.n_batches),
                  'inactive': int(sp.n_inactive), 'generations_per_batch': int(sp.generations_per_batch),
                  'seed': int(sp.seed)}
        if (actual != expected or sp.run_mode != 'eigenvalue' or tuple(sp.version) != (0, 15, 3)
                or sp.current_batch != expected['batches']
                or sp.n_realizations != expected['batches'] - expected['inactive']):
            raise ValueError('Statepoint identity or sampling mismatch')
        mean, sigma = float(sp.keff.n), float(sp.keff.s)
        generations = np.asarray(sp.k_generation)
        n = expected['batches'] * expected['generations_per_batch']
        if (not math.isfinite(mean) or not math.isfinite(sigma) or mean <= 0 or sigma <= 0
                or generations.shape != (n,) or not np.isfinite(generations).all()):
            raise ValueError('Invalid eigenvalue or generation history')
        entropy = np.asarray(sp.entropy) if loaded['entropy_requested'] else None
        if entropy is not None and (entropy.shape != (n,) or not np.isfinite(entropy).all()):
            raise ValueError('Missing or invalid requested entropy history')
        runtimes = {name: float(value) for name, value in sp.runtime.items()}
        version = [int(value) for value in sp.version]
    inactive_generations = expected['inactive'] * expected['generations_per_batch']
    with Path('convergence.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['generation', 'active', 'k_generation', 'entropy_bits'])
        for i, k in enumerate(generations, start=1):
            writer.writerow([i, i > inactive_generations, float(k),
                             '' if entropy is None else float(entropy[i - 1])])
    write_json('calculation.json', {
        'status': 'calculated_unreviewed', 'model_xml_sha256': file_hash('model.xml'),
        'statepoint': {'name': statepoint.name, 'sha256': file_hash(statepoint),
                       'bytes': statepoint.stat().st_size},
        'openmc_version': version, 'sampling': actual,
        'keff': {'mean': mean, 'std_dev': sigma, 'uncertainty': 'one sigma'},
        'generation_count': n, 'entropy': 'recorded' if entropy is not None else 'not_requested',
        'openmc_runtime_seconds': runtimes, 'convergence_assessment': 'not_performed',
        'scientific_fidelity': 'not_checked', 'reference_comparison': 'not_run'})


if __name__ == '__main__':
    try:
        if sys.argv[1] == 'probe':
            print(json.dumps({'worker_sha256': file_hash(__file__),
                              'solver_files': {str(p): file_hash(p) for p in
                                  [Path('/opt/openmc/bin/openmc'), *sorted(Path('/opt/openmc/lib').glob('*.so*'))]
                                  if p.is_file()}}))
        elif sys.argv[1] == 'load':
            load_xml()
        elif sys.argv[1] == 'extract':
            extract()
        else:
            raise ValueError('Unknown trusted worker phase')
    except Exception as error:
        write_json('worker-error.json', {'phase': sys.argv[1], 'error_type': type(error).__name__,
                                         'error': str(error)[:2000]})
        raise
