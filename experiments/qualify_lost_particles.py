"""Qualify a lost-particle diagnostic with retained evidence and two native controls."""
import argparse
from pathlib import Path

from builder.context import write_json
from evaluation.candidates import lost_particles, receipts
from evaluation.candidates.phase_evidence import export_outcome
from evaluation.confirmation import references
from evaluation.scientific.records import require
from evaluator import run as exporter, transport
from evaluator.profiles import PROFILE
from evaluator.transport_input import read_regular


def fixture(missing_middle):
    """Independent slab partition: removing its middle leaves a real geometry gap."""
    return """import os
import openmc

def build_model():
    material = openmc.Material(temperature=293.6)
    material.set_density('g/cm3', 18.8)
    material.add_nuclide('U235', 0.04)
    material.add_nuclide('U238', 0.96)
    materials = openmc.Materials([material])
    materials.cross_sections = os.environ['OPENMC_CROSS_SECTIONS']
    xmin = openmc.XPlane(x0=-3, boundary_type='reflective')
    xmax = openmc.XPlane(x0=3, boundary_type='reflective')
    ymin = openmc.YPlane(y0=-3, boundary_type='reflective')
    ymax = openmc.YPlane(y0=3, boundary_type='reflective')
    zmin = openmc.ZPlane(z0=-3, boundary_type='reflective')
    zmax = openmc.ZPlane(z0=3, boundary_type='reflective')
    a = openmc.XPlane(x0=0)
    b = openmc.XPlane(x0=0.2)
    side = +ymin & -ymax & +zmin & -zmax
    left = openmc.Cell(fill=material, region=+xmin & -a & side)
    middle = openmc.Cell(fill=material, region=+a & -b & side)
    right = openmc.Cell(fill=material, region=+b & -xmax & side)
    cells = """ + ("[left, right]" if missing_middle else "[left, middle, right]") + """
    settings = openmc.Settings()
    settings.run_mode = 'eigenvalue'
    settings.particles = 1000
    settings.batches = 8
    settings.inactive = 2
    settings.generations_per_batch = 1
    settings.seed = 1
    settings.temperature = {'method': 'nearest', 'tolerance': 1.0}
    settings.source = openmc.IndependentSource(
        space=openmc.stats.Box((-2,-1,-1),(-1,1,1)),
        angle=openmc.stats.Isotropic(), energy=openmc.stats.Watt())
    settings.statepoint = {'batches': [8]}
    return openmc.Model(openmc.Geometry(cells), materials, settings)
"""


def inventory(directory):
    return {str(p.relative_to(directory)): exporter.digest(read_regular(p, limit=32_000_000))
            for p in sorted(directory.rglob('*')) if p.is_file()}


def qualify(assessment, reference, index, output):
    assessment, reference, index, output = map(Path, (assessment, reference, index, output))
    require(not output.exists(), 'Qualification output must be fresh')
    require(assessment.resolve() not in output.resolve().parents, 'Output must be outside retained evidence')
    assignment = receipts.read(assessment / 'assignment.json')
    goal = references.target(assignment['case'], reference, None)
    require(assignment['frozen_index_sha256'] == goal['index']['manifest_sha256']
            and assignment['reference'] == goal['reference'], 'Original reference binding changed')
    require(assignment['source_sha256'] == exporter.digest(read_regular(assessment / 'candidate.py')),
            'Original candidate binding changed')
    before = inventory(assessment)
    output.mkdir(parents=True)
    write_json(output / 'original-evidence-sha256.json', before)
    code_paths = ('evaluation/candidates/lost_particles.py', 'evaluation/candidates/phase_evidence.py',
                  'experiments/qualify_lost_particles.py')
    report = dict(format='lost-particle-policy-qualification-v1', policy=lost_particles.POLICY,
                  status='running', provider_calls=0, maximum_new_native_transports=2,
                  automatic_retries=0, campaign_resumed=False, historical_reports_modified=False,
                  reference_manifest_sha256=goal['index']['manifest_sha256'],
                  implementation={p: exporter.digest(Path(p).read_bytes()) for p in code_paths}, controls=[])
    write_json(output / 'report.json', report)
    try:
        report['retained_trial'] = lost_particles.review(assessment, goal, index)
        write_json(output / 'retained-trial-review.json', report['retained_trial'])
        for name, missing in (('missing_middle', True), ('complete_partition', False)):
            folder = output / name
            folder.mkdir()
            source = folder / 'candidate.py'
            source.write_text(fixture(missing))
            exported = exporter.evaluate(source, folder / 'export', index=index, image=PROFILE['export_image'])
            require(exported['status'] == 'exported', 'Native control export failed')
            source_hash = exporter.digest(source.read_bytes())
            require(export_outcome(folder / 'export', PROFILE['export_image'], index, source_hash)
                    == dict(cause=None, reason=None), 'Control export evidence failed')
            value = transport.transport(folder / 'export', folder / 'transport', index=index,
                                        image=PROFILE['transport_image'], wall_seconds=120)
            if missing:
                evidence = lost_particles.review(folder, goal, index)
            else:
                require(not lost_particles.diagnostic(value, folder / 'transport'),
                        'Correct control falsely classified')
                record = receipts.transport_record(folder, source_hash, PROFILE['transport_image'], index)
                require(record['runtime'] == goal['runtime']
                        and record['data']['index_sha256'] == goal['data']['index_sha256']
                        and all(goal['data']['files'].get(n) == v for n,v in record['data']['files'].items()),
                        'Correct control runtime/data mismatch')
                evidence = dict(evidence_status='coherent', transport_completed=True,
                                lost_particle_attribution=False, scope='execution control, not reference agreement')
            report['controls'].append(dict(control=name, status='passed', evidence=evidence))
            write_json(output / 'report.json', report)
            print(name + ': passed', flush=True)
        require(inventory(assessment) == before, 'Original assessment evidence changed')
        report.update(status='passed', original_evidence_unchanged=True)
    except Exception as exc:
        report.update(status='failed', reason=str(exc), error_type=type(exc).__name__,
                      original_evidence_unchanged=inventory(assessment) == before)
        raise
    finally:
        write_json(output / 'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('assessment', 'reference', 'data-index', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = qualify(args.assessment, args.reference, args.data_index.resolve(strict=True), args.output)
    print(result['status'])


if __name__ == '__main__':
    main()
