"""Selective E binding and conservative exposure, using synthetic provider traces."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from builder import context, region_skill, route, trajectory
from builder.submission import submission
from experiments import run as experiment, dashboard_campaign as campaign
from prompts.prepare import build_prompt
from tests.test_request_profiles import launch, synthetic_body
from tests.fixtures.responses import mock_response

E = region_skill.SELECTIVE


def catalog_item():
    return dict(type='message', role='developer', content=[
        dict(type='input_text', text=region_skill.catalog(region_skill.material(E)[0]))])


def reviewed():
    a = context.request_setup(synthetic_body())
    body = synthetic_body(); body['input'].insert(1, catalog_item())
    return {'A':a, 'D':copy.deepcopy(a), 'E':context.request_setup(body)}


class SelectiveRegionTests(unittest.TestCase):
    def test_e_prompt_is_a_and_native_catalog_matches_observed_fixture(self):
        raw, identity = region_skill.material(E)
        fixture = Path(__file__).parent/'fixtures/region_skill_native_catalog.txt'
        self.assertEqual(region_skill.catalog(raw), fixture.read_text())
        self.assertEqual(identity['delivery'], 'native_skill_catalog')
        for case in ('reflective_pin_cell','two_composition_5x5','axially_zoned_5x5'):
            for profile in (None, route.EXTENDED_REQUEST_BUDGET):
                self.assertEqual(route.condition_prompt(build_prompt(case), E, request_budget=profile),
                    route.condition_prompt(build_prompt(case), 'guided_construction', request_budget=profile))
        self.assertNotIn(E, route.BOUNDARY_CONDITIONS | route.SMOKE_CONDITIONS)

    def test_prepare_freezes_catalog_and_body_without_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment.agent, 'run') as dispatch:
            root = Path(tmp)/'E'
            plan = experiment.prepare(root, assistance=E)
            region_skill.verify(root, plan, E)
            self.assertEqual(plan['region_ownership_skill'], region_skill.material(E)[1])
            self.assertEqual(plan['observation_configuration']['configuration']['id'], 'E')
            self.assertEqual(plan['observation_configuration']['configuration']['tools'], ['coding'])
            dispatch.assert_not_called()

    def test_catalog_or_delivery_tampering_stops_before_dispatch(self):
        for change in ('catalog','identity','snapshot'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)/'E'; plan = experiment.prepare(root, assistance=E)
                if change == 'identity':
                    plan['region_ownership_skill']['delivery'] = 'preloaded_prompt'
                    (root/'plan.json').write_text(json.dumps(plan))
                else:
                    (root/(region_skill.CATALOG_SNAPSHOT if change == 'catalog' else region_skill.SNAPSHOT)).write_text('changed')
                with patch.object(experiment.agent, 'run') as dispatch, self.assertRaisesRegex(ValueError,'Region skill'):
                    experiment.execute(root)
                dispatch.assert_not_called(); self.assertFalse((root/'runs').exists())

    def test_first_context_rejects_missing_extra_catalog_and_preloaded_body(self):
        raw = region_skill.material(E)[0].decode()
        changes = (
            lambda b:b['input'].pop(1),
            lambda b:b['input'].insert(1, catalog_item()),
            lambda b:b['input'][1].update(role='user'),
            lambda b:b['input'][1]['content'][0].update(text=region_skill.catalog(raw.encode())+'\nextra'),
            lambda b:b['input'][1]['content'][0].update(text=region_skill.catalog(raw.encode()).replace(
                '### Available skills', '### Available skills\n- unrelated: extra skill')),
            lambda b:b.update(instructions=raw),
            lambda b:b['input'].append(dict(type='message',role='developer',
                content=[dict(type='input_text',text=raw.split('---\n',2)[2])])),
            lambda b:b['input'].append(dict(type='message',role='developer',
                content=[dict(type='input_text',text='## Memory\nUNDECLARED')]))
        )
        for mutate in changes:
            with self.subTest(mutate=changes.index(mutate)):
                _, result, responder, _, _ = launch(self, assistance=E, mutate=lambda n,b:mutate(b))
                self.assertEqual(result['status'], 'failed')
                responder.assert_not_called()

    def test_retained_e_binds_catalog_staging_and_body(self):
        folder, result, responder, _, adapters = launch(self, assistance=E, constrain_setup=True)
        self.assertEqual(result['status'], 'completed')
        _, provenance = submission(folder, 'reflective_pin_cell')
        self.assertEqual(provenance['region_ownership_skill'], region_skill.material(E)[1])
        self.assertEqual(adapters,(0,0)); self.assertEqual(responder.call_count,1)
        (folder/'region-skill-staging.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'staging receipt'):
            submission(folder,'reflective_pin_cell')

    def test_staging_changed_receipt_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'staging receipt'):
            region_skill.stage(lambda *a,**k:'{}', 'fixture', region_skill.material(E)[0], 5)

    def test_reviewed_setups_differ_only_by_catalog(self):
        region_skill.reviewed_setups(reviewed())
        for change in ('missing','D','E-tools','E-instructions','duplicate'):
            s = reviewed()
            if change == 'missing': del s['E']
            elif change == 'D': s['D']['generic_tools_sha256'] = 'changed'
            elif change == 'E-tools': s['E']['generic_tools_sha256'] = 'changed'
            elif change == 'E-instructions': s['E']['instruction_messages'].append(dict(role='developer',sha256='changed'))
            else: s['E']['instruction_messages'] *= 2
            with self.subTest(change=change), self.assertRaises(ValueError):
                region_skill.reviewed_setups(s)

    def test_prepare_54_balanced_slots_and_separate_setups_without_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); index=root/'index'; index.write_text('synthetic')
            setups=root/'setups.json'; setups.write_text(json.dumps({m:reviewed() for m in campaign.MODELS}))
            with patch.object(campaign,'execute') as dispatch, patch.object(campaign,'evaluate') as evaluate:
                manifest=campaign.prepare_campaign(root/'ade',pilot=False,data_index=index,setup_file=setups,
                                                  comparison=campaign.SELECTIVE_COMPARISON)
            self.assertEqual(manifest['sessions'],54)
            self.assertEqual(manifest['maximum_model_requests'],864)
            self.assertEqual(set(manifest['arms']),{'A','D','E'})
            self.assertEqual(len({(r['model'],r['case'],r['arm'],r['repeat']) for r in manifest['rows']}),54)
            for row in manifest['rows']:
                folder=root/'ade'/row['path']; plan=json.loads((folder/'plan.json').read_text())
                region_skill.verify(folder,plan,plan['assistance'])
                self.assertEqual(region_skill.CATALOG_SNAPSHOT in {p.name for p in folder.iterdir()},row['arm']=='E')
            dispatch.assert_not_called(); evaluate.assert_not_called()

    def test_execution_forwards_the_prepared_e_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'E';plan=experiment.prepare(root,assistance=E,cases=('reflective_pin_cell',))
            with patch.object(experiment.agent,'run',return_value=dict(status='failed',cleanup_confirmed=True)) as dispatch:
                experiment.execute(root,responder=lambda *_:b'local')
            self.assertEqual(dispatch.call_args.kwargs['expected_region_skill'],plan['region_ownership_skill'])

    def test_retained_first_catalog_cannot_be_changed_with_matching_inventory(self):
        folder,result,_,_,_=launch(self,assistance=E)
        self.assertEqual(result['status'],'completed')
        body=json.loads((folder/'request-01.json').read_text())
        body['input'][1]['content'][0]['text'] += '\nchanged'
        (folder/'request-01.json').write_text(json.dumps(body))
        (folder/'inventory-01.json').write_text(json.dumps(context.request_inventory(body)))
        with self.assertRaisesRegex(ValueError,'first-request context'):
            submission(folder,'reflective_pin_cell')

    def test_campaign_dispatch_uses_the_matching_e_setup(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);index=root/'index';index.write_text('synthetic')
            setup=root/'setups.json';setups={m:reviewed() for m in campaign.MODELS}
            setup.write_text(json.dumps(setups))
            manifest=campaign.prepare_campaign(root/'campaign',pilot=False,data_index=index,setup_file=setup,
                                                comparison=campaign.SELECTIVE_COMPARISON)
            row=next(r for r in manifest['rows'] if r['arm']=='E')
            manifest['rows']=[row]
            (root/'campaign/manifest.json').write_text(json.dumps(manifest))
            with patch.object(campaign,'execute',side_effect=RuntimeError('scripted dispatch stop')) as dispatch, \
                 patch.object(campaign.shutil,'disk_usage',return_value=SimpleNamespace(free=20*1024**3)), \
                 contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'scripted dispatch stop'):
                campaign.run_campaign(root/'campaign')
            self.assertEqual(dispatch.call_count,1)
            self.assertEqual(dispatch.call_args.kwargs['request_setup'],setups[row['model']]['E'])


class ExposureTests(unittest.TestCase):
    def trace(self, root):
        raw, identity=region_skill.material(E); text=raw.decode()
        prompt=route.condition_prompt(build_prompt('reflective_pin_cell'),E)
        body=synthetic_body();body['input'].insert(1,catalog_item())
        body['input'][-1]['content'][0]['text']=prompt
        call=dict(type='custom_tool_call',call_id='call_read',name='exec',
            input='text(await tools.exec_command('+json.dumps({'cmd':'cat '+region_skill.CONTAINER_PATH})+'));')
        def stream(items):
            return ('event: response.completed\ndata: '+json.dumps(dict(type='response.completed',
                response=dict(id='synthetic',status='completed',output=items)))+'\n\n').encode()
        second=copy.deepcopy(body)
        second['input'] += [call, dict(type='custom_tool_call_output',call_id='call_read',
            output=[dict(type='input_text',text=json.dumps(dict(exit_code=0,output=text)))])]
        command=dict(type='command_execution',command="/bin/sh -lc 'cat "+region_skill.CONTAINER_PATH+"'",
                     exit_code=0,aggregated_output=text)
        events=[dict(type='request',id=1),dict(type='stdout',text=json.dumps(
            dict(type='item.completed',item=command))),dict(type='request',id=2)]
        for name,value in (('manifest.json',dict(assistance=E,mode='mock',region_ownership_skill=identity)),
                           ('request-01.json',body),('request-02.json',second)):
            (root/name).write_text(json.dumps(value))
        (root/'prompt.txt').write_text(prompt)
        (root/region_skill.SNAPSHOT).write_bytes(raw)
        (root/region_skill.CATALOG_SNAPSHOT).write_text(region_skill.catalog(raw))
        (root/'response-01.sse').write_bytes(stream([call]))
        (root/'response-02.sse').write_bytes(stream([]))
        (root/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        return second,events

    def summarize(self,root):
        return trajectory.summarize(root,dict(status='completed',request_count=2))['region_skill']

    def test_exact_bound_read_and_completed_delivery_are_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.trace(root); result=self.summarize(root)
            self.assertEqual(result['catalog_delivery'],'complete')
            self.assertEqual(result['body_loading'],'observed')
            self.assertEqual(result['actor'],'scripted_test_double')
            self.assertEqual(result['application'],'not_inferred')
            self.assertEqual(result['reads'][0]['delivered_in'],'request-02.json')

    def test_incomplete_unbound_or_failed_evidence_is_never_positive(self):
        for change in ('missing-response','missing-invocation-response','partial','failed','wrong-call','echo',
                       'missing-runtime','runtime-partial','setup-mismatch','duplicate-call'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);body,events=self.trace(root)
                if change=='missing-response': (root/'response-02.sse').unlink()
                if change=='missing-invocation-response': (root/'response-01.sse').unlink()
                if change=='partial': body['input'][-1]['output'][0]['text']=json.dumps(dict(exit_code=0,output='partial'))
                if change=='wrong-call': body['input'][-1]['call_id']='other'
                if change=='duplicate-call': body['input'].append(body['input'][-2])
                if change=='echo':
                    body['input'][-1]=dict(type='message',role='user',content=[
                        dict(type='input_text',text=region_skill.material(E)[0].decode())])
                if change in ('failed','runtime-partial'):
                    command=json.loads(events[1]['text'])
                    command['item'].update(exit_code=1 if change=='failed' else 0,
                                           aggregated_output='partial' if change=='runtime-partial' else command['item']['aggregated_output'])
                    events[1]['text']=json.dumps(command)
                if change=='missing-runtime': events.pop(1)
                if change=='setup-mismatch': (root/'setup-02.json').write_text('{"matched":false}')
                (root/'request-02.json').write_text(json.dumps(body))
                (root/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
                self.assertEqual(self.summarize(root)['body_loading'],'not_demonstrated')
