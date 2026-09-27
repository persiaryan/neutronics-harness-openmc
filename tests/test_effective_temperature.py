"""Ported v7 temperature controls; synthetic receipts, no OpenMC/model/transport.

The extraction and comparison expectations originate in the qualified v7 tests.
Extra local controls cover precedence, score propagation and prospective versions.
"""
import ast
import json
import math
from numbers import Real
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from evaluation.scientific import inspection, records
from evaluation.benchmark_suite import scoring, suite_checks
from evaluation.benchmark_suite.suite_cases import probes
from evaluation.candidates import assessment, verify as assessment_verifier
from evaluator.contracts import FACTORY
from evaluator.profiles import BOUNDARY_PROTOCOL, FACTORY_PROFILE, PROFILE, assessment_route
from evaluator.run import write_json


CASE = 'reflective_pin_cell'
XML = (b'<model><materials><material id="1"><density units="sum"/>'
       b'<nuclide name="H1" ao="0.02"/></material></materials>'
       b'<geometry><cell id="1" material="1" universe="1"/></geometry>'
       b'<settings/></model>')
NEW_PROTOCOL = 'factory-assessment-boundaries-v4-temperature-v1'

# As in the v7 control, exercise the actual trusted worker functions without
# importing OpenMC or executing candidate Python on the host.
tree = ast.parse(inspection.WORKER.read_text())
functions = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name in {'scalar_temperature', 'inspect'}]
namespace = {'math': math, 'Real': Real, 'ET': ET}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(inspection.WORKER), 'exec'), namespace)
scalar = namespace['scalar_temperature']


def observe(cell_temperature, material_temperature=None, default=None):
    """Feed loaded-value doubles to the real traversal, not a second precedence rule."""
    class Material:
        id = 1
        nuclides = ['H1']
        isotropic = []
        temperature = material_temperature

        def get_nuclide_atom_densities(self):
            return {'H1': 0.02}

        def get_mass_density(self):
            return 1.0

    class Cell:
        id = 1
        fill_type = 'material'
        fill = Material()
        region = None
        temperature = cell_temperature

        def __contains__(self, point):
            return True

    class Universe:
        cells = {1: Cell()}

    fake_openmc = SimpleNamespace(
        __version__='0.15.3', Universe=Universe, RectLattice=type('RectLattice', (), {}),
        Materials=SimpleNamespace(from_xml_element=lambda _: [Cell.fill]),
        Geometry=SimpleNamespace(from_xml_element=lambda *_: SimpleNamespace(root_universe=Universe())))
    xml = XML if default is None else XML.replace(
        b'<settings/>', f'<settings><temperature_default>{default}</temperature_default></settings>'.encode())
    with patch.dict(namespace, openmc=fake_openmc, np=SimpleNamespace(asarray=lambda p: p)):
        return namespace['inspect']({'xml': xml.decode(), 'points': [[0, 0, 0]]})


def comparison(temperatures):
    # Hold unrelated material/settings behavior fixed, as in the v7 unit control.
    count = len(probes(CASE)[0])
    observations = [['ok', [[1, 293.6]]] for _ in range(count)]
    observations[:len(temperatures)] = [['ok', [[1, value]]] for value in temperatures]
    observation = dict(status='inspected', cleanup_confirmed=True, materials=[], observations=observations)
    with patch.object(suite_checks, 'check_materials', return_value=({'1': 'fuel'}, [])), \
         patch.object(suite_checks, 'settings_checks', return_value=dict(
             status='passed_checks', checks=[], unassessed_options=[])):
        fidelity = suite_checks.assess(CASE, None, observation, {},
                                       boundary_result=dict(status='passed_checks'))
    return fidelity, assessment.fidelity_checks(CASE, fidelity, observation)


def scored_temperature(value):
    # Other checks are explicitly true to isolate this one rubric obligation.
    checks = {category: {name: True for name in group}
              for category, group in assessment.blank_checks().items()}
    checks['materials']['temperature'] = value
    gates = {name: dict(passed=True, cause=None) for name in assessment.blank_gates()}
    return scoring.score(gates, checks)


class EffectiveTemperature(unittest.TestCase):
    def test_correct_finite_scalars_and_singletons(self):
        for value in (293.6, [293.6], (293.6,)):
            with self.subTest(value=value):
                self.assertEqual(scalar(value), (293.6, None))
        self.assertEqual(scalar(293), (293.0, None))

    def test_wrong_finite_scalar_and_singletons_are_not_repaired(self):
        for value in (600.0, [600.0], (600.0,)):
            with self.subTest(value=value):
                self.assertEqual(scalar(value), (600.0, None))

    def test_missing_empty_and_distributed_values(self):
        self.assertEqual(scalar(None), (None, 'missing_effective_temperature'))
        for value in ([], (), [293.6, 293.6], (293.6, 293.6), [293.6, 600.0]):
            with self.subTest(value=value):
                self.assertEqual(scalar(value), (None, 'distributed_or_empty_temperature'))

    def test_nonfinite_values_remain_unknown(self):
        for value in (math.nan, math.inf, -math.inf):
            for wrapped in (value, [value], (value,)):
                with self.subTest(value=wrapped):
                    self.assertEqual(scalar(wrapped), (None, 'nonfinite_temperature'))

    def test_unsupported_values_are_not_coerced(self):
        class CoercionTrap:
            def __float__(self):
                raise AssertionError('Arbitrary coercion is forbidden')

            def __array__(self):
                raise AssertionError('Arbitrary array coercion is forbidden')

        for value in ('293.6', True, False, [[293.6]], ((293.6,),),
                      [True], [False], ['293.6'], {'temperature': 293.6},
                      {293.6}, iter([293.6]), CoercionTrap()):
            with self.subTest(value=type(value).__name__):
                self.assertEqual(scalar(value), (None, 'unsupported_temperature_type'))

    def test_correct_singletons_produce_identical_observations(self):
        baseline = observe(293.6)
        self.assertEqual(baseline['observations'], [('ok', [[1, 293.6]])])
        self.assertEqual(baseline['temperature_limitations'], [])
        for value in ([293.6], (293.6,)):
            self.assertEqual(observe(value), baseline)

    def test_existing_cell_material_default_precedence(self):
        controls = [
            (600.0, 293.6, 300.0, 600.0),
            ([600.0], 293.6, 300.0, 600.0),
            (None, 600.0, 293.6, 600.0),
            (None, None, 600.0, 600.0),
            (None, None, None, 293.6),
        ]
        for cell, material, default, expected in controls:
            with self.subTest(cell=cell, material=material, default=default):
                result = observe(cell, material, default)
                self.assertEqual(result['observations'], [('ok', [[1, expected]])])
                self.assertEqual(result['temperature_limitations'], [])

    def test_unsupported_cell_does_not_fall_back_to_correct_material(self):
        result = observe([], 293.6, 293.6)
        self.assertEqual(result['observations'], [('ok', [[1, None]])])
        self.assertEqual(result['temperature_limitations'], [
            dict(cell_id=1, cause='distributed_or_empty_temperature')])

    def test_correct_value_passes_temperature_requirement_and_scoring(self):
        for value in (293.6, [293.6], (293.6,)):
            _, checks = comparison([scalar(value)[0]])
            self.assertIs(checks['materials']['temperature'], True)
            score = scored_temperature(checks['materials']['temperature'])
            self.assertEqual(score['score'], 100.0)
            self.assertTrue(score['strict_correct'])

    def test_wrong_value_fails_requirement_and_keeps_numeric_score(self):
        for value in (600.0, [600.0], (600.0,)):
            fidelity, checks = comparison([scalar(value)[0]])
            self.assertEqual(fidelity['materials']['temperature_failures'], 1)
            self.assertIs(checks['materials']['temperature'], False)
            score = scored_temperature(checks['materials']['temperature'])
            # Literal rubric: one of four 15-point material checks is false.
            self.assertEqual(score['earned_points'], 66.25)
            self.assertAlmostEqual(score['score'], 100 * 66.25 / 70)
            self.assertFalse(score['strict_correct'])

    def test_only_unknown_temperature_evidence_is_unscored(self):
        count = len(probes(CASE)[0])
        fidelity, checks = comparison([None] * count)
        self.assertEqual(fidelity['materials']['temperature_failures'], 0)
        self.assertEqual(fidelity['materials']['temperature_unresolved'], count)
        self.assertEqual(fidelity['materials']['status'], 'inconclusive')
        self.assertIsNone(checks['materials']['temperature'])
        score = scored_temperature(checks['materials']['temperature'])
        self.assertEqual(score['status'], 'unscored')
        self.assertIsNone(score['score'])
        self.assertFalse(score['strict_correct'])

    def test_correct_plus_unknown_does_not_pass(self):
        fidelity, checks = comparison([293.6, None])
        self.assertEqual(fidelity['materials']['temperature_unresolved'], 1)
        self.assertIsNone(checks['materials']['temperature'])
        self.assertIsNone(scored_temperature(checks['materials']['temperature'])['score'])

    def test_wrong_plus_unknown_preserves_failure_in_either_order(self):
        for temperatures in ([600.0, None], [None, 600.0]):
            fidelity, checks = comparison(temperatures)
            self.assertEqual(fidelity['materials']['temperature_failures'], 1)
            self.assertEqual(fidelity['materials']['temperature_unresolved'], 1)
            self.assertEqual(fidelity['materials']['status'], 'discrepancy')
            self.assertIs(checks['materials']['temperature'], False)
            self.assertEqual(scored_temperature(checks['materials']['temperature'])['earned_points'], 66.25)


class TemperatureEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'inspection'

    def retain(self, *, unknown=False, capability='legacy'):
        observation = observe([] if unknown else [293.6])
        observation['observations'] *= len(probes(CASE)[0])
        info = dict(Image=inspection.IMAGE, Mounts=[], Config=dict(
            User='1000:1000', Entrypoint=['python', '-I', '-B', '/opt/evaluator/idle.py']),
            HostConfig=dict(NetworkMode='none', ReadonlyRootfs=True, Privileged=False,
                CapDrop=['ALL'], SecurityOpt=['no-new-privileges=true'], PidMode='', IpcMode='private',
                Memory=1024**3, NanoCpus=2_000_000_000, PidsLimit=128, Tmpfs=inspection.TMPFS,
                LogConfig=dict(Type='none')))

        def docker(*args):
            if args[0] == 'ps':
                return ''
            if args[:2] == ('image', 'inspect'):
                return json.dumps([dict(Id=inspection.IMAGE)])
            if args[0] == 'inspect':
                return json.dumps([info])
            return ''

        # The actual controller writes the receipts; only external execution is doubled.
        with patch.object(inspection, 'docker', side_effect=docker), \
             patch.object(inspection, 'bounded', return_value=dict(
                 exit_code=0, stop_reason=None, stdout=json.dumps(observation).encode(), stderr=b'')):
            result = inspection.inspect_xml(
                XML, probes(CASE)[0] if capability == 'legacy' else [], self.directory, capability=capability)
        self.assertEqual(result['status'], 'inspected')
        self.assertTrue(result['cleanup_confirmed'])
        return result

    def review(self):
        return records.inspection_record(CASE, self.directory, XML, inspection.WORKER.read_bytes())

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.directory.iterdir() if p.is_file()}

    def test_new_receipt_verifies_correct_temperature(self):
        self.retain()
        manifest = json.loads((self.directory / 'manifest.json').read_bytes())
        self.assertEqual(manifest['format'], 'private-scientific-inspection-v3')
        self.assertEqual(self.review()['observations'][0], ['ok', [[1, 293.6]]])

    def test_verified_unknown_stays_null_through_assessment_and_score(self):
        self.retain(unknown=True)
        observation = self.review()
        fidelity, checks = comparison([entry[1][0][1] for entry in observation['observations']])
        self.assertGreater(fidelity['materials']['temperature_unresolved'], 0)
        self.assertIsNone(checks['materials']['temperature'])
        self.assertIsNone(scored_temperature(checks['materials']['temperature'])['score'])

    def test_historical_or_unknown_receipt_versions_are_rejected_without_rewrite(self):
        self.retain()
        path = self.directory / 'manifest.json'
        manifest = json.loads(path.read_bytes())
        for version in ('private-scientific-inspection-v2', 'private-scientific-inspection-v99'):
            manifest['format'] = version
            write_json(path, manifest)
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, 'XML/version'):
                self.review()
            self.assertEqual(self.snapshot(), before)

    def test_worker_tampering_is_rejected(self):
        self.retain()
        path = self.directory / 'worker.py'
        path.write_bytes(path.read_bytes() + b'\n# changed\n')
        with self.assertRaisesRegex(ValueError, 'worker changed'):
            self.review()

    def test_unknown_observation_cannot_be_relabelled_as_correct(self):
        self.retain(unknown=True)
        path = self.directory / 'result.json'
        result = json.loads(path.read_bytes())
        result['observations'][0][1][0][1] = 293.6
        write_json(path, result)
        with self.assertRaisesRegex(ValueError, 'result changed'):
            self.review()

    def test_boundary_receipt_identity_is_unchanged(self):
        self.retain(capability='effective-boundary-v2')
        self.assertEqual(json.loads((self.directory / 'manifest.json').read_bytes())['format'],
                         'private-boundary-inspection-v2')

    def test_public_route_is_explicit_temperature_only(self):
        self.assertEqual(BOUNDARY_PROTOCOL, NEW_PROTOCOL)
        self.assertEqual(assessment_route(FACTORY, FACTORY_PROFILE, NEW_PROTOCOL)['evaluator_protocol'],
                         NEW_PROTOCOL)
        for old in ('factory-assessment-boundaries-v4', 'factory-assessment-boundaries-v7'):
            with self.assertRaisesRegex(ValueError, 'Unsupported evaluator protocol'):
                assessment_route(FACTORY, FACTORY_PROFILE, old)

    def test_old_assessment_keeps_original_score_and_cannot_be_reviewed_as_current(self):
        folder = self.root / 'historical'
        folder.mkdir()
        checks = {category: {name: True for name in group}
                  for category, group in assessment.blank_checks().items()}
        gates = {name: dict(passed=True, cause=None) for name in assessment.blank_gates()}
        assignment = dict(rubric=scoring.identity(), delivery_contract=FACTORY,
            assessment_route=dict(execution_profile=PROFILE, evaluator_protocol='factory-assessment-boundaries-v4'))
        report = dict(format='private-candidate-diagnostic-v5', phases={}, grading_enabled=False,
            builder_feedback='not_sent', candidate_repair=False, cleanup_confirmed=True,
            diagnostic_score=scoring.score(gates, checks), gates=gates, checks=checks, status='assessed')
        write_json(folder / 'assignment.json', assignment)
        write_json(folder / 'report.json', report)
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        with patch.object(assessment_verifier.run, 'target', side_effect=AssertionError('No reference lookup')):
            review = assessment_verifier.review_assessment(folder, self.root / 'unused-index.xml')
        self.assertEqual(review['evidence_status'], 'contradictory')
        self.assertEqual(review['reported_score'], 100.0)
        self.assertIsNone(review['score'])
        self.assertIn('Unsupported evaluator protocol', review['reason'])
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)


if __name__ == '__main__':
    unittest.main()
