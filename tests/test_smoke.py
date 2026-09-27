"""Smoke contract and feedback controls; no native run or model call here."""
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from builder import smoke_tool,smoke_feedback
from builder.route import condition_prompt
from evaluator import smoke
from experiments import run as experiment

from tests.test_transport import XML


class SmokeContract(unittest.TestCase):
    def test_launcher_propagates_only_declared_smoke_and_never_final_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);index=root/'cross_sections.xml';index.write_text('<cross_sections/>')
            for mode in ('guided_construction','guided_boundaries','guided_boundaries_smoke'):
                folder=root/mode
                kwargs={'smoke_data_index':index} if mode=='guided_boundaries_smoke' else {}
                with patch.object(experiment.exporter,'data_directory',return_value=(index,{})):
                    plan=experiment.prepare(folder,assistance=mode,cases=['reflective_pin_cell'],**kwargs)
                result=dict(status='completed',cleanup_confirmed=True,request_count=1)
                with patch.object(experiment.agent,'run',return_value=result) as launch,patch.object(
                        experiment,'submission',return_value=(b'def build_model(): pass',{})),patch.object(
                        experiment.exporter,'evaluate') as final_export:
                    summary=experiment.execute(folder,responder=lambda n,b:b'local only')
                self.assertEqual(launch.call_args.kwargs.get('smoke_data_index'),kwargs.get('smoke_data_index'))
                for key in ('model','assistance','evaluator_protocol'):
                    self.assertEqual(launch.call_args.kwargs[key],plan[key])
                self.assertEqual(summary['transport'],'not_run')
                final_export.assert_not_called()

    def test_smoke_entry_rejects_unbound_xml_before_native_execution(self):
        with patch.object(smoke.transport,'_transport') as execute:
            for provenance in ({},{'kind':'candidate-session-smoke-v1','model_xml_sha256':'different'}):
                with self.assertRaises(ValueError):
                    smoke.transport.smoke_xml(XML,Path('/unused'),index=Path('/unused'),provenance=provenance)
            execute.assert_not_called()

    def test_diagnostic_overrides_are_explicit_and_preserve_physics(self):
        original=ET.fromstring(XML);derived,changes=smoke.prepare_xml(XML,'cross_sections.xml')
        other=ET.fromstring(derived)
        self.assertEqual(ET.tostring(original.find('geometry')),ET.tostring(other.find('geometry')))
        for material,changed in zip(original.findall('materials/material'),other.findall('materials/material')):
            self.assertEqual(ET.tostring(material),ET.tostring(changed))
        for field in ('source','temperature_method','temperature_tolerance','entropy_mesh','mesh'):
            self.assertEqual([ET.tostring(n) for n in original.findall('settings/'+field)],
                             [ET.tostring(n) for n in other.findall('settings/'+field)])
        self.assertEqual(other.findtext('settings/particles'),'1000')
        self.assertEqual(other.findtext('settings/batches'),'8')
        self.assertEqual(other.findtext('settings/inactive'),'2')
        self.assertEqual(other.findtext('settings/state_point/batches'),'8')
        self.assertEqual(len(changes),8)
        self.assertEqual(ET.tostring(original),ET.tostring(ET.fromstring(XML)))

    def test_no_external_source_or_unknown_mode_is_repaired(self):
        for mutation in ('file','mode','duplicate'):
            root=ET.fromstring(XML)
            if mutation=='file':root.find('settings/source').set('file','/private/source.h5')
            elif mutation=='mode':root.find('settings/run_mode').text='fixed source'
            else:ET.SubElement(root.find('settings'),'particles').text='99'
            with self.assertRaises(ValueError):smoke.prepare_xml(ET.tostring(root),'cross_sections.xml')

    def test_new_condition_only_and_same_final_evaluator(self):
        prompt=condition_prompt('public task','guided_boundaries_smoke')
        self.assertIn('python3 /work/smoke_openmc.py model.xml',prompt)
        self.assertNotIn('Never run native transport.',prompt)
        self.assertNotIn('Tool availability does not require tool use.',prompt)
        self.assertIn('Never run native transport.',condition_prompt('public task','guided_boundaries'))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);index=root/'cross_sections.xml';index.write_text('<cross_sections/>')
            with patch.object(experiment.exporter,'data_directory',return_value=(index,{})):
                c=experiment.prepare(root/'new',assistance='guided_boundaries_smoke',smoke_data_index=index)
            b=experiment.prepare(root/'old',assistance='guided_boundaries')
            for key in ('model','delivery_contract','evaluator_protocol','execution_profile'):
                self.assertEqual(c[key],b[key])
            self.assertEqual(c['budgets']['authoring_seconds'],600)
            self.assertEqual(c['budgets']['model_requests'],8)
            self.assertEqual(c['budgets']['smoke_calls'],2)
            self.assertNotIn('smoke',b)
            with self.assertRaises(ValueError):experiment.prepare(root/'bad',assistance='guided_boundaries_smoke')

    def test_unauthorized_paths_ids_budgets_and_nonuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=smoke_tool.Session(Path(tmp)/'session',{},'/operator/index.xml')
            self.assertEqual(json.loads((session.output/'usage.json').read_bytes())['attempted_calls'],0)
            with patch.object(smoke,'execute') as execute:
                a=session.invoke(dict(tool='smoke_openmc',path='/host/private.xml'),remaining_seconds=600)
                b=session.invoke(dict(tool='smoke_openmc',xml=XML.decode()),remaining_seconds=1)
                c=session.invoke(dict(tool='smoke_openmc',xml=XML.decode()),remaining_seconds=600)
                self.assertEqual([r['cause'] for r in (a,b,c)],['invalid_request','insufficient_remaining_session_budget','tool_call_budget_exhausted'])
                with self.assertRaises(ValueError):session.invoke({},remaining_seconds=600)
            execute.assert_not_called()

    def test_host_failure_sanitized_and_cleanup_uncertainty_stops_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=smoke_tool.Session(Path(tmp)/'session',{},'/operator/index.xml')
            with patch.object(smoke,'execute',side_effect=OSError('/private/secret')):
                reply=session.invoke(dict(tool='smoke_openmc',xml=XML.decode()),remaining_seconds=600)
            self.assertFalse(session.cleanup_confirmed)
            self.assertNotIn('/private',json.dumps(reply))


def reply():
    return dict(format='candidate-smoke-result-v1',evidence_reference='smoke-run:fixture:1',status='incomplete',
        native_outcome='failed',cause='openmc_abnormal_exit',working_xml_sha256='original',smoke_xml_sha256='derived',
        profile=smoke.PROFILE,openmc_version='0.15.3',cleanup_confirmed=True,
        processes=dict(openmc=dict(exit_code=255,stop_reason=None)),
        logs=dict(openmc_stderr=dict(text='ERROR: literal native control',complete=True,bytes=29,sha256='log')),
        limitations=['Short execution only'],coverage='not global validity')


class SmokeFeedback(unittest.TestCase):
    def test_failure_and_large_excerpts_preserve_outcomes_and_limits(self):
        r=reply();r['logs']['openmc_stdout']=dict(text='start\n'+'x'*80000+'\nend',complete=False,bytes=90000,sha256='large')
        value=smoke_feedback.compact(r)
        self.assertTrue(value['feedback_complete'])
        self.assertEqual(value['native_outcome'],'failed')
        self.assertEqual(value['processes']['openmc']['exit_code'],255)
        self.assertEqual(value['limitations'],r['limitations'])
        self.assertFalse(value['logs']['openmc_stdout']['complete'])
        self.assertLessEqual(len(smoke_feedback.encode(value)),16000)
        self.assertNotIn('score',value)
        self.assertEqual(value,smoke_feedback.compact(dict(reversed(list(r.items())))))

    def test_generated_client_reuses_safe_read_and_exclusive_publish(self):
        module=types.ModuleType('smoke_client_test');exec(smoke_tool.CLIENT,module.__dict__)
        actual_open=os.open
        with tempfile.TemporaryDirectory() as tmp:
            def workspace(path,*args,**kwargs):return actual_open(tmp if path=='/work/workspace' else path,*args,**kwargs)
            (Path(tmp)/'model.xml').write_bytes(XML)
            (Path(tmp)/'link.xml').symlink_to(Path(tmp)/'model.xml')
            with patch.object(os,'open',side_effect=workspace):
                self.assertEqual(module.read_candidate('model.xml'),XML.decode())
                for path in ('/private/reference.xml','../reference.xml','link.xml'):
                    with self.assertRaises((ValueError,OSError)):module.read_candidate(path)
                with patch('sys.stdout',new_callable=io.StringIO) as stream:module.publish(reply())
                value=json.loads(stream.getvalue());saved=Path(tmp)/value['full_result']['path']
                self.assertEqual(json.loads(saved.read_bytes()),reply())
                saved.write_text('changed')
                with self.assertRaises(ValueError):module.publish(reply())



if __name__=='__main__':unittest.main()
