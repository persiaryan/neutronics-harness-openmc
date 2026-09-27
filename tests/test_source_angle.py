"""Literal isotropy expectations: dOmega=dmu*dphi, never derived from observer."""
from copy import deepcopy
import math
import unittest
import xml.etree.ElementTree as ET

from evaluation.scientific import source_angle
from evaluator.profiles import assessment_route, BOUNDARY_PROTOCOL
from tests.test_source_space import TASKS, model, checked, replace_space, cartesian


def polar(mu='-1 1', phi=None):
    angle = ET.Element('angle', type='mu-phi', reference_uvw='0 0 1', reference_vwu='1 0 0')
    ET.SubElement(angle, 'mu', type='uniform', parameters=mu)
    ET.SubElement(angle, 'phi', type='uniform', parameters=phi or f'0 {2*math.pi}')
    return angle


def replace_angle(root, angle):
    source = root.find('settings/source')
    for node in source.findall('angle'): source.remove(node)
    if angle is not None: source.append(angle)


class AngularSemantics(unittest.TestCase):
    def test_equivalence_all_tasks_both_spatial_encodings(self):
        for case,bounds in TASKS.items():
            for space in ('box','cartesian'):
                for angle in (None, ET.Element('angle',type='isotropic'), polar()):
                    root,sampling=model(case)
                    if space=='cartesian': replace_space(root,cartesian(bounds))
                    replace_angle(root,angle); before=ET.tostring(root)
                    self.assertIs(checked(case,root,sampling)[1],True,(case,space,angle))
                    self.assertEqual(before,ET.tostring(root))

    def test_rotated_frame_order_and_full_turn_offset(self):
        angle=polar(phi=f'{-math.pi} {math.pi}')
        angle.set('reference_uvw','0 1 0'); angle.set('reference_vwu','0 0 -1')
        angle[:]=list(reversed(list(angle)))
        self.assertTrue(all(c['passed'] is True for c in source_angle.compare(source_angle.observe(angle))))
        angle.attrib.pop('reference_uvw');angle.attrib.pop('reference_vwu')
        self.assertTrue(all(c['passed'] is True for c in source_angle.compare(source_angle.observe(angle))))

    def test_known_defects_all_tasks_both_encodings(self):
        variants=[polar(mu='0 1'),polar(mu=f'0 {math.pi}'),polar(mu='-1 .99'),
                  polar(phi=f'0 {math.pi}'),polar(phi='1 0')]
        nonuniform=polar(); nonuniform.find('mu').set('type','discrete')
        nonuniform.find('mu').attrib.pop('parameters')
        ET.SubElement(nonuniform.find('mu'),'parameters').text='-1 1 .5 .5';variants.append(nonuniform)
        for case,bounds in TASKS.items():
            for space in ('box','cartesian'):
                for angle in variants:
                    root,sampling=model(case)
                    if space=='cartesian':replace_space(root,cartesian(bounds))
                    replace_angle(root,deepcopy(angle))
                    result,value=checked(case,root,sampling)
                    self.assertIs(value,False,(case,space,angle))
                    self.assertTrue(any(c['field']=='source_angle' and c['passed'] is False for c in result['checks']))

    def test_missing_invalid_unsupported_or_correlated_never_pass(self):
        variants=[ET.Element('angle',type='correlated'),ET.Element('angle',type='mixture')]
        for mode in ('missing','nan','malformed','nonunit','parallel','correlated','tabular','multiple_turns'):
            angle=polar()
            if mode=='missing':angle.remove(angle.find('mu'))
            if mode=='nan':angle.find('mu').set('parameters','nan 1')
            if mode=='malformed':angle.find('mu').set('parameters','-1')
            if mode=='nonunit':angle.set('reference_uvw','0 0 2')
            if mode=='parallel':angle.set('reference_vwu','0 0 1')
            if mode=='correlated':angle.set('correlation','1')
            if mode=='tabular':angle.find('mu').set('type','tabular')
            if mode=='multiple_turns':angle.find('phi').set('parameters',f'0 {4*math.pi}')
            variants.append(angle)
        for angle in variants:
            root,sampling=model('reflective_pin_cell');replace_angle(root,angle)
            self.assertIsNone(checked('reflective_pin_cell',root,sampling)[1], ET.tostring(angle))

    def test_known_wrong_mu_visible_beside_unknown_phi(self):
        angle=polar(mu='0 1');angle.find('phi').set('type','correlated')
        root,sampling=model('reflective_pin_cell');replace_angle(root,angle)
        result,value=checked('reflective_pin_cell',root,sampling)
        self.assertIsNone(value)
        self.assertTrue(any(c.get('component')=='mu' and c['passed'] is False for c in result['checks']))
        self.assertTrue(any(c.get('component')=='phi' and c['passed'] is None for c in result['checks']))

    def test_duplicates_unresolved_and_existing_tolerance(self):
        root,sampling=model('reflective_pin_cell');replace_angle(root,polar(mu='-1 .999999999999'))
        self.assertIs(checked('reflective_pin_cell',root,sampling)[1],True)
        root.find('settings/source').append(polar())
        self.assertIsNone(checked('reflective_pin_cell',root,sampling)[1])

    def test_previous_protocol_not_relabelled(self):
        self.assertEqual(BOUNDARY_PROTOCOL,'factory-assessment-boundaries-v4-temperature-source-v1')
        with self.assertRaises(ValueError):
            assessment_route('openmc-model-factory-v1','factory-serial-v1','factory-assessment-boundaries-v5')


    def test_duplicate_marginals_and_missing_frame_components_do_not_pass(self):
        for name in ('mu','phi'):
            angle=polar();angle.append(deepcopy(angle.find(name)))
            root,sampling=model('reflective_pin_cell');replace_angle(root,angle)
            self.assertIsNone(checked('reflective_pin_cell',root,sampling)[1])
        for frame in ('nan 0 1','0 1','0 0 0'):
            angle=polar();angle.set('reference_uvw',frame)
            root,sampling=model('reflective_pin_cell');replace_angle(root,angle)
            self.assertIsNone(checked('reflective_pin_cell',root,sampling)[1])

    def test_malformed_atomic_marginals_are_unknown_not_demonstrated_defects(self):
        for parameters in ('', '-1 0 1', '-1 1 0 0', '-1 1 -.5 1.5', '-1 1 nan .5'):
            angle=polar();node=angle.find('mu');node.attrib={'type':'discrete'}
            ET.SubElement(node,'parameters').text=parameters
            root,sampling=model('reflective_pin_cell');replace_angle(root,angle)
            self.assertIsNone(checked('reflective_pin_cell',root,sampling)[1],parameters)

    def test_monodirectional_and_atomic_phi_demonstrate_nonisotropy(self):
        atomic=polar();node=atomic.find('phi');node.attrib={'type':'discrete'}
        ET.SubElement(node,'parameters').text='0 1 .5 .5'
        for angle in (ET.Element('angle',type='monodirectional',reference_uvw='0 0 1'),atomic):
            root,sampling=model('reflective_pin_cell');replace_angle(root,angle)
            result,value=checked('reflective_pin_cell',root,sampling)
            self.assertIs(value,False)
            self.assertEqual(result['status'],'discrepancy')

    def test_unsupported_structure_on_isotropy_does_not_get_credit(self):
        for mode in ('attribute','child'):
            angle=ET.Element('angle',type='isotropic')
            if mode=='attribute':angle.set('extra','1')
            else:ET.SubElement(angle,'mu',type='uniform',parameters='-1 1')
            root,sampling=model('reflective_pin_cell');replace_angle(root,angle)
            result,value=checked('reflective_pin_cell',root,sampling)
            self.assertIsNone(value)
            self.assertEqual(result['status'],'inconclusive')

    def test_unknown_frame_does_not_erase_a_demonstrated_marginal_mismatch(self):
        angle=polar(mu='0 1');angle.set('reference_uvw','0 0 2')
        root,sampling=model('reflective_pin_cell');replace_angle(root,angle)
        result,value=checked('reflective_pin_cell',root,sampling)
        self.assertEqual(result['status'],'discrepancy')
        self.assertIsNone(value)
        self.assertTrue(any(c.get('component')=='mu' and c['passed'] is False for c in result['checks']))



if __name__=='__main__':unittest.main()
