"""Fixed integration-control plan and independent expected outcomes."""
from pathlib import Path
import tempfile
import unittest

from evaluation.representation import development


class DevelopmentPlan(unittest.TestCase):
    def test_fixed_matrix_modifies_only_the_declared_fixture_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'pin';w=root/'wrapper';p.mkdir();w.mkdir()
            pin="settings.particles = 10000\nconstraints={'fissionable':True}\n"
            wrapper='before\n    # Equivalent explicit water partition:\nold water\n    # Clip every region\nafter\n'
            (p/'reference.py').write_text(pin);(w/'reference.py').write_text(wrapper)
            rows=development.controls(dict(indc107_reflective_pin=str(p),wrapped_eight_pin_channel=str(w)))
            self.assertEqual([r['expected'] for r in rows],['conforming_within_protocol']*2+['nonconforming','indeterminate'])
            self.assertEqual(rows[0]['source'],'before\n    add(domain&~openmc.Union(occupied),water)\n    # Clip every region\nafter\n')
            self.assertEqual(rows[1]['source'],"settings.particles = 10000\nconstraints={'domains':[cells[0]]}\n")
            self.assertEqual(rows[2]['source'],"settings.particles = 5000\nconstraints={'fissionable':True}\n")
            self.assertIn("'energy_bounds':[0.,1.e9]",rows[3]['source'])

    def test_declared_verdict_alone_cannot_pass_integration(self):
        control=dict(id='wrong-particle-count',case='indc107_reflective_pin',expected='nonconforming')
        report=dict(status='assessed',conclusion=dict(conformance='nonconforming',known_mismatches=[],unassessed_checks=[]),
                    diagnostic_score=dict(score=90,strict_correct=False))
        self.assertFalse(development.row_result(control,report,dict(evidence_status='coherent'),{})['passed'])
        report['conclusion']['known_mismatches']=['physics_settings.sampling']
        self.assertTrue(development.row_result(control,report,dict(evidence_status='coherent'),{})['passed'])
        self.assertFalse(development.row_result(control,report,dict(evidence_status='contradictory'),{})['passed'])

    def test_unknown_requires_a_null_score_and_the_expected_unassessed_check(self):
        control=dict(id='unsupported-energy-restriction',case='indc107_reflective_pin',expected='indeterminate')
        report=dict(status='assessed',conclusion=dict(conformance='indeterminate',known_mismatches=[],unassessed_checks=['physics_settings.source']),
                    diagnostic_score=dict(score=None,strict_correct=False))
        self.assertTrue(development.row_result(control,report,dict(evidence_status='coherent'),{})['passed'])
        report['diagnostic_score']['score']=100
        self.assertFalse(development.row_result(control,report,dict(evidence_status='coherent'),{})['passed'])


if __name__=='__main__':unittest.main()
