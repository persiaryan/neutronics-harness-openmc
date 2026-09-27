"""Literal source expectations; no source observer is used to define targets."""
from copy import deepcopy
import unittest
import xml.etree.ElementTree as ET

from evaluation.scientific import source_space
from evaluation.benchmark_suite.suite_checks import settings_checks
from evaluation.benchmark_suite import scoring
from evaluation.candidates.assessment import fidelity_checks
from evaluator.profiles import assessment_route, BOUNDARY_PROTOCOL

TASKS = {
    'reflective_pin_cell': [-.63,-.63,-.63,.63,.63,.63],
    'reflected_7x7': [-4.41,-4.41,-30.,4.41,4.41,30.],
    'two_composition_5x5': [-3.15,-3.15,-25.,3.15,3.15,25.],
    'axially_zoned_5x5': [-3.15,-3.15,-30.,3.15,3.15,30.],
    'asymmetric_5x5': [-3.15,-3.15,-30.,3.15,3.15,30.],
}


def model(case):
    """Synthetic admitted XML from literal public bounds; no retained reference XML."""
    bounds = TASKS[case]
    meshes = {'reflective_pin_cell': [10, 10, 1], 'reflected_7x7': [7, 7, 12],
              'two_composition_5x5': [5, 5, 10], 'axially_zoned_5x5': [5, 5, 12],
              'asymmetric_5x5': [5, 5, 12]}
    sampling = dict(particles=10000, batches=300 if case == 'reflected_7x7' else 400,
                    inactive=100, generations_per_batch=2, seed=1, source='uniform')
    root = ET.fromstring('<model><materials><material id="1"><density units="sum"/>'
                        '<nuclide name="H1" ao="0.02"/></material></materials>'
                        '<geometry><cell id="1" material="1" universe="1"/></geometry>'
                        '<settings/></model>')
    settings = root.find('settings')
    for name in ('particles', 'batches', 'inactive', 'generations_per_batch', 'seed'):
        ET.SubElement(settings, name).text = str(sampling[name])
    ET.SubElement(settings, 'temperature_tolerance').text = '1'
    source = ET.SubElement(settings, 'source', type='independent', particle='neutron')
    space = ET.SubElement(source, 'space', type='box')
    ET.SubElement(space, 'parameters').text = ' '.join(map(str, bounds))
    ET.SubElement(source, 'angle', type='isotropic')
    ET.SubElement(source, 'energy', type='watt', parameters='988000 2.249e-6')
    constraints = ET.SubElement(source, 'constraints')
    ET.SubElement(constraints, 'fissionable').text = 'true'
    ET.SubElement(constraints, 'rejection_strategy').text = 'resample'
    mesh = ET.SubElement(settings, 'mesh', id='1', type='regular')
    for name, values in [('dimension', meshes[case]), ('lower_left', bounds[:3]),
                         ('upper_right', bounds[3:])]:
        ET.SubElement(mesh, name).text = ' '.join(map(str, values))
    ET.SubElement(settings, 'entropy_mesh').text = '1'
    return root, sampling


def cartesian(bounds):
    space = ET.Element('space', type='cartesian')
    for i,axis in enumerate('xyz'):
        ET.SubElement(space,axis,type='uniform',parameters=f'{bounds[i]} {bounds[i+3]}')
    return space


def replace_space(root, space):
    source = root.find('settings/source')
    source.remove(source.find('space'))
    source.insert(0, space)


def checked(case, root, sampling):
    result = settings_checks(case,root,sampling)
    return result, fidelity_checks(case,dict(settings=result))['physics_settings']['source']


class SourceSemantics(unittest.TestCase):
    def test_box_and_cartesian_all_five_tasks_same_verdict_without_rewriting(self):
        for case,bounds in TASKS.items():
            with self.subTest(case=case):
                root,sampling=model(case)
                before=ET.tostring(root)
                baseline,old=checked(case,root,sampling)
                self.assertIs(old,True)
                self.assertEqual(before,ET.tostring(root))
                replace_space(root,cartesian(bounds))
                before=ET.tostring(root)
                alternative,new=checked(case,root,sampling)
                self.assertIs(new,True)
                self.assertEqual(baseline['checks'],alternative['checks'])
                self.assertEqual(alternative['spatial_source']['comparison_version'],source_space.VERSION)
                self.assertEqual(before,ET.tostring(root))

    def test_serialization_order_numbers_and_mesh_ids_do_not_select_source_role(self):
        for case,bounds in TASKS.items():
            root,sampling=model(case);space=cartesian(bounds)
            space[:]=list(reversed(list(space)))
            for node in space:
                node.set('parameters','  '.join(f'{float(n):.12e}' for n in node.get('parameters').split()))
            replace_space(root,space)
            mesh=root.find('settings/mesh');mesh.set('id','9999');root.find('settings/entropy_mesh').text='9999'
            self.assertIs(checked(case,root,sampling)[1],True)

    def test_wrong_x_lower_y_upper_and_z_interval_all_tasks_fail(self):
        for case,bounds in TASKS.items():
            for axis,index in (('x',0),('y',1),('z',0)):
                root,sampling=model(case);space=cartesian(bounds)
                values=[float(n) for n in space.find(axis).get('parameters').split()]
                values[index]+=.1
                space.find(axis).set('parameters',' '.join(map(str,values)))
                replace_space(root,space)
                result,verdict=checked(case,root,sampling)
                self.assertIs(verdict,False,(case,axis))
                self.assertTrue(any(c.get('axis')==axis and c['passed'] is False for c in result['checks']))

    def test_existing_numeric_policy_applies_to_both_encodings(self):
        for encoding in ('box','cartesian'):
            root,sampling=model('reflective_pin_cell');bounds=TASKS['reflective_pin_cell'][:]
            bounds[0]+=1e-12
            if encoding=='cartesian':replace_space(root,cartesian(bounds))
            else:root.find('settings/source/space/parameters').text=' '.join(map(str,bounds))
            self.assertIs(checked('reflective_pin_cell',root,sampling)[1],True)

    def test_unsupported_nonuniform_correlated_mixture_or_incomplete_never_pass(self):
        variants=[
            '<space type="cartesian"><x type="discrete" parameters="-0.63 0.63 0.5 0.5"/><y type="uniform" parameters="-.63 .63"/><z type="uniform" parameters="-.63 .63"/></space>',
            '<space type="correlated"><parameters>-.63 -.63 -.63 .63 .63 .63</parameters></space>',
            '<space type="mixture"><parameters>-.63 -.63 -.63 .63 .63 .63</parameters></space>',
            '<space type="cartesian"><x type="uniform" parameters="-.63 .63"/></space>',
            '<space type="box"><parameters>-.63 .63</parameters></space>',
            '<space type="cartesian" correlation="1"><x type="uniform" parameters="-.63 .63"/><y type="uniform" parameters="-.63 .63"/><z type="uniform" parameters="-.63 .63"/></space>',
        ]
        for xml in variants:
            root,sampling=model('reflective_pin_cell');replace_space(root,ET.fromstring(xml))
            result,value=checked('reflective_pin_cell',root,sampling)
            self.assertIsNone(value)
            self.assertTrue(result['spatial_source']['observation']['limitations'])

    def test_wrong_property_survives_another_axis_unknown(self):
        root,sampling=model('reflective_pin_cell');space=cartesian(TASKS['reflective_pin_cell'])
        space.find('x').set('parameters','-.5 .63');space.find('y').set('type','tabular')
        replace_space(root,space);result,value=checked('reflective_pin_cell',root,sampling)
        self.assertIsNone(value)  # Unknowns are not normalized out of the score.
        self.assertEqual(result['status'],'discrepancy')
        self.assertTrue(any(c.get('axis')=='x' and c['passed'] is False for c in result['checks']))
        self.assertTrue(any(c.get('axis')=='y' and c['passed'] is None for c in result['checks']))

    def test_missing_multiple_sources_and_duplicate_spaces_do_not_pass(self):
        for mode in ('missing','multiple','duplicate_space'):
            root,sampling=model('reflective_pin_cell');settings=root.find('settings');source=settings.find('source')
            if mode=='missing':settings.remove(source)
            elif mode=='multiple':settings.append(deepcopy(source))
            else:source.append(deepcopy(source.find('space')))
            self.assertIs(checked('reflective_pin_cell',root,sampling)[1],None if mode=='duplicate_space' else False)

    def test_invalid_uniform_parameters_never_pass(self):
        for text in ('nan .63','-inf .63','wrong .63','.63 -.63','0 0','-.63 .63 extra'):
            root,sampling=model('reflective_pin_cell');space=cartesian(TASKS['reflective_pin_cell'])
            space.find('x').set('parameters',text);replace_space(root,space)
            self.assertIsNot(checked('reflective_pin_cell',root,sampling)[1],True)

    def test_other_source_properties_preserved(self):
        for encoding in ('box','cartesian'):
            for field,value in (('particle','photon'),('angle','monodirectional'),('energy','maxwell'),
                                ('fissionable','false'),('rejection_strategy','kill')):
                root,sampling=model('reflective_pin_cell')
                if encoding=='cartesian':replace_space(root,cartesian(TASKS['reflective_pin_cell']))
                source=root.find('settings/source')
                if field=='particle':source.set(field,value)
                elif field in ('angle','energy'):source.find(field).set('type',value)
                else:
                    parent=source.find('constraints');node=parent.find(field)
                    if node is None:node=ET.SubElement(parent,field)
                    node.text=value
                self.assertIs(checked('reflective_pin_cell',root,sampling)[1],False,(encoding,field))
        root,sampling=model('reflective_pin_cell')
        ET.SubElement(root.find('settings/source'),'time',type='uniform',parameters='0 1')
        self.assertIsNone(checked('reflective_pin_cell',root,sampling)[1])

    def test_diagnostic_score_changes_no_weights_and_unknowns_stay_null(self):
        gates={k:dict(passed=True,cause=None) for k in scoring.RUBRIC['hard_gates']}
        for value,expected in ((True,100.),(False,96.42857142857143),(None,None)):
            checks={k:{c:True for c in v['checks']} for k,v in scoring.RUBRIC['categories'].items()}
            checks['physics_settings']['source']=value
            score=scoring.score(gates,checks)
            self.assertEqual(score['score'],expected)
            self.assertIs(score['strict_correct'],value is True)

    def test_protocol_rejects_v4_without_relabelling_history(self):
        self.assertEqual(BOUNDARY_PROTOCOL,'factory-assessment-boundaries-v4-temperature-source-v1')
        with self.assertRaisesRegex(ValueError,'Unsupported evaluator protocol'):
            assessment_route('openmc-model-factory-v1','factory-serial-v1','factory-assessment-boundaries-v4')


    def test_duplicate_axes_and_unknown_structure_stay_unresolved(self):
        for mode in ('duplicate', 'missing', 'attribute', 'child', 'box_attribute', 'box_child'):
            root,sampling=model('reflective_pin_cell')
            space=cartesian(TASKS['reflective_pin_cell'])
            if mode=='duplicate':space.append(deepcopy(space.find('x')))
            elif mode=='missing':space.remove(space.find('z'))
            elif mode=='attribute':space.find('x').set('extra','value')
            elif mode=='child':ET.SubElement(space.find('x'),'extra')
            else:
                space=deepcopy(root.find('settings/source/space'))
                if mode=='box_attribute':space.find('parameters').set('extra','value')
                else:ET.SubElement(space,'extra')
            replace_space(root,space)
            result,value=checked('reflective_pin_cell',root,sampling)
            self.assertIsNone(value,mode)
            self.assertEqual(result['status'],'inconclusive')

    def test_fission_encoding_preserves_separate_fissionable_constraint(self):
        root,sampling=model('reflective_pin_cell')
        root.find('settings/source/space').set('type','fission')
        root.find('settings/source/constraints/fissionable').text='false'
        self.assertIs(checked('reflective_pin_cell',root,sampling)[1],True)
        root.find('settings/source/space').set('type','box')
        self.assertIs(checked('reflective_pin_cell',root,sampling)[1],False)

    def test_existing_point_source_path_is_unchanged(self):
        root,sampling=model('reflective_pin_cell');sampling['source']='point'
        space=ET.fromstring('<space type="point"><parameters>.15 0 0</parameters></space>')
        replace_space(root,space)
        result,value=checked('reflective_pin_cell',root,sampling)
        self.assertIs(value,True)
        self.assertIsNone(result['spatial_source']['observation'])
        space.find('parameters').text='.16 0 0'
        self.assertIs(checked('reflective_pin_cell',root,sampling)[1],False)

    def test_source_multiplicity_type_and_watt_parameters_still_fail(self):
        for mode in ('source_type','watt_parameters','nonfinite_watt'):
            root,sampling=model('reflective_pin_cell')
            source=root.find('settings/source')
            if mode=='source_type':source.set('type','file')
            else:source.find('energy').set('parameters','1 2.249e-6' if mode=='watt_parameters' else 'nan 2.249e-6')
            self.assertIs(checked('reflective_pin_cell',root,sampling)[1],False,mode)

    def test_settings_entry_uses_existing_bounded_xml_admission(self):
        from evaluation.scientific.inspection import admit
        root,sampling=model('reflective_pin_cell')
        valid=ET.tostring(root)
        self.assertIs(checked('reflective_pin_cell',admit(valid),sampling)[1],True)
        malformed=[valid[:-8], b'<!DOCTYPE model><model/>',
                   b'<!ENTITY x "value"><model/>', valid.replace(b'<model>',b'<model xmlns="urn:control">',1)]
        for data in malformed:
            with self.assertRaises((ValueError,ET.ParseError)):
                admit(data)



if __name__=='__main__':unittest.main()
