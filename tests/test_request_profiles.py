"""P5 request profiles and retained submissions, with local process doubles only."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from builder import boundary_tool, context, route, run as builder, smoke_tool
from builder.submission import submission
from evaluator import run as exporter
from experiments import run as experiment
from prompts.prepare import prepare, CASE_FILES, build_prompt
from tests import test_isolated_builder as doubles

PROFILE = 'authoring-requests-16-v1'
ARMS = ('guided_construction', 'guided_boundaries', 'guided_boundaries_smoke')


def read(path):
    return json.loads(path.read_bytes())


def synthetic_body():
    body = doubles.request()
    body.update(tool_choice='auto', parallel_tool_calls=False,
                reasoning={'effort': 'medium'}, include=['reasoning.encrypted_content'],
                text={'verbosity': 'low'}, instructions='SYNTHETIC ADAPTER INSTRUCTIONS')
    body['tools'] = [{'type': 'function', 'name': 'local_python', 'parameters': {'type': 'object'}}]
    body['input'].insert(0, {'type': 'additional_tools', 'id': 'session-one',
        'tools': [{'type': 'custom', 'name': 'local_shell', 'description': 'Synthetic local tool'}]})
    return body


def launch(test, *, cap=8, profile=None, count=1, assistance='guided_construction',
           constrain_setup=False, mutate=None, complete=True):
    fixture = doubles.BuilderDouble(); fixture.setUp(); test.addCleanup(fixture.doCleanups)
    public = fixture.output.parent/'public'; prepare('reflective_pin_cell', public)
    prompt = route.condition_prompt((public/'prompt.txt').read_text(), assistance, request_budget=profile)
    body = synthetic_body(); body['input'][-1]['content'][0]['text'] = prompt
    expected = context.request_setup(body)
    source = 'def build_model():\n    return None\n'
    process = fixture.fake_process(body, source)
    ready, _, done = [json.loads(line) for line in process.stdout.getvalue().splitlines()]
    frames = [ready]
    for n in range(1, count+1):
        current = copy.deepcopy(body)
        if mutate is not None:
            mutate(n, current)
        frames.append(dict(type='request', id=n, body=current))
    if complete:
        frames.append(done)
    process.stdout = io.BytesIO(b''.join(json.dumps(f).encode()+b'\n' for f in frames))
    responder = Mock(return_value=b'SYNTHETIC LOCAL RESPONSE')
    index = fixture.output.parent/'cross_sections.xml'; index.write_text('<cross_sections/>')
    smoke_adapter = Mock(); smoke_adapter.session.cleanup_confirmed = True
    kwargs = dict(smoke_data_index=index) if assistance == 'guided_boundaries_smoke' else {}
    with patch.object(builder.subprocess, 'Popen', return_value=process), \
         patch.object(boundary_tool, 'AttachedSession') as boundary, \
         patch.object(smoke_tool, 'AttachedSession', return_value=smoke_adapter) as smoke, \
         patch.object(exporter, 'data_directory', return_value=(index, {})), \
         patch.object(builder, 'load_auth', side_effect=AssertionError('No credentials')), \
         patch.object(builder, 'forward', side_effect=AssertionError('No provider calls')):
        result = builder.run(fixture.output, case='reflective_pin_cell', prepared_input=public,
            assistance=assistance, model='test-model', mode='mock', responder=responder,
            max_requests=cap, request_budget=profile,
            request_setup=expected if constrain_setup else None, **kwargs)
    return fixture.output, result, responder, expected, (boundary.call_count, smoke.call_count)


class ProfileContract(unittest.TestCase):
    def test_eight_default_sixteen_explicit_and_unknown_profiles_rejected(self):
        self.assertEqual(route.EXTENDED_REQUEST_BUDGET, PROFILE)
        self.assertEqual(route.request_limit(), 8)
        self.assertEqual(route.request_limit(PROFILE), 16)
        for value in ('', 'arbitrary', 16, True, {}, []):
            with self.assertRaises(ValueError):
                route.request_limit(value)

    def test_prompt_change_is_only_guidance_budget_not_public_task(self):
        for case in CASE_FILES:
            public = build_prompt(case)+'\nPublic literal eight-request and 8-request remain unchanged.\n'
            for arm in route.CONDITIONS:
                original = route.condition_prompt(public, arm)
                extended = route.condition_prompt(public, arm, request_budget=PROFILE)
                expected = public+original[len(public):].replace('eight-request','sixteen-request').replace('8-request','16-request')
                self.assertEqual(extended, expected)
                self.assertTrue(extended.startswith(public))

    def test_authoring_wall_tools_export_and_retry_budgets_are_unchanged(self):
        for arm in ARMS:
            old = experiment.budgets(arm)
            new = experiment.budgets(arm, PROFILE)
            self.assertEqual(old['model_requests'], 8)
            self.assertEqual(new.pop('model_requests'), 16)
            self.assertEqual(new, {k:v for k,v in old.items() if k != 'model_requests'})
            self.assertEqual(new['authoring_seconds'], 600)
            self.assertEqual(new['boundary_calls'], 2)
            self.assertEqual(new['boundary_seconds'], 120)
            self.assertEqual(new['automatic_retries'], 0)
        c = experiment.budgets(ARMS[2], PROFILE)
        self.assertEqual((c['smoke_calls'],c['smoke_native_seconds']), (2,60))

    def test_undeclared_or_over_limit_or_noninteger_budget_stops_before_auth(self):
        for cap, profile in ((16,None),(17,PROFILE),(0,None),(8.5,PROFILE),(True,None),(8,'unknown')):
            with patch.object(builder, 'load_auth') as auth, patch.object(builder, 'docker') as docker:
                with self.assertRaises(ValueError):
                    builder.run(Path('unused'),case=None,prepared_input=None,
                                max_requests=cap,request_budget=profile)
            auth.assert_not_called(); docker.assert_not_called()


class RequestSetup(unittest.TestCase):
    def test_profile_excludes_task_history_and_only_top_level_tool_ids(self):
        one = synthetic_body(); two = copy.deepcopy(one)
        two['input'][0]['id'] = 'another-session'
        two['input'][-1]['content'][0]['text'] = 'Different public task'
        two['input'].append(dict(type='function_call_output',call_id='one',output='Synthetic history'))
        self.assertEqual(context.request_setup(one), context.request_setup(two))
        self.assertEqual(set(context.request_setup(one)), {'request_configuration',
            'generic_tools_sha256','instruction_messages','top_level_instructions_sha256'})
        self.assertNotIn('Different public task', json.dumps(context.request_setup(two)))

    def test_configuration_tools_and_instruction_changes_are_semantic(self):
        expected = context.request_setup(synthetic_body())
        mutations = [
            lambda b:b.update(reasoning={'effort':'low'}),
            lambda b:b.update(parallel_tool_calls=True),
            lambda b:b.update(instructions='Changed synthetic instructions'),
            lambda b:b['tools'][0].update(description='Changed schema'),
            lambda b:b['input'][0]['tools'][0].update(id='semantic-nested-id'),
            lambda b:b['input'].insert(0,dict(type='message',role='developer',
                content=[dict(type='input_text',text='Synthetic development policy')]))]
        for mutate in mutations:
            body = synthetic_body(); mutate(body)
            self.assertNotEqual(context.request_setup(body), expected)

    def test_profile_contains_hashes_not_tool_schemas_or_authentication(self):
        body = synthetic_body()
        body.update(authorization='SYNTHETIC_CREDENTIAL',access_token='SYNTHETIC_CREDENTIAL')
        setup = context.request_setup(body)
        self.assertEqual(len(setup['generic_tools_sha256']),64)
        self.assertNotIn('SYNTHETIC_CREDENTIAL',json.dumps(setup))
        self.assertNotIn('Synthetic local tool',json.dumps(setup))


class PreparedProfiles(unittest.TestCase):
    def prepare(self, root, arm, profile):
        index=root/'cross_sections.xml';index.write_text('<cross_sections/>')
        kwargs = dict(smoke_data_index=index) if arm==ARMS[2] else {}
        with patch.object(exporter,'data_directory',return_value=(index,{})):
            return experiment.prepare(root/'plan',assistance=arm,request_budget=profile,**kwargs)

    def test_each_arm_records_profile_totals_and_prompt_binding_without_dispatch(self):
        for arm in ARMS:
            for profile,cap in ((None,8),(PROFILE,16)):
                with tempfile.TemporaryDirectory() as tmp, patch.object(experiment.agent,'run') as dispatch:
                    root=Path(tmp);plan=self.prepare(root,arm,profile)
                    self.assertEqual(plan.get('request_budget_profile'),profile)
                    self.assertEqual(plan['budgets']['model_requests'],cap)
                    self.assertEqual(plan['maximum_model_requests'],2*cap)
                    for case in plan['cases']:
                        expected=route.condition_prompt((root/'plan/inputs'/case/'prompt.txt').read_text(),arm,
                                                        request_budget=profile)
                        self.assertEqual(plan['authoring_prompt_sha256'][case],context.sha256(expected.encode()))
                    self.assertEqual('smoke' in plan,arm==ARMS[2])
                    if arm==ARMS[2]:
                        self.assertIn(str(cap)+'-request',plan['resource_policy'])
                    dispatch.assert_not_called()

    def test_profile_total_budget_and_prompt_tampering_stop_before_dispatch(self):
        for change in ('profile','absent_profile','count','total','prompt'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);plan=self.prepare(root,ARMS[0],PROFILE)
                if change=='profile':plan['request_budget_profile']='unknown'
                if change=='absent_profile':del plan['request_budget_profile']
                if change=='count':plan['budgets']['model_requests']=17
                if change=='total':plan['maximum_model_requests']=999
                if change=='prompt':plan['authoring_prompt_sha256'][plan['cases'][0]]='changed'
                exporter.write_json(root/'plan/plan.json',plan)
                with patch.object(experiment.agent,'run') as dispatch, self.assertRaises(ValueError):
                    experiment.execute(root/'plan')
                dispatch.assert_not_called()
                self.assertFalse((root/'plan/runs').exists())

    def test_same_declared_setup_reaches_all_arms_with_same_request_wall_caps(self):
        expected=context.request_setup(synthetic_body())
        for arm in ARMS:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);self.prepare(root,arm,PROFILE)
                with patch.object(experiment.agent,'run',return_value=dict(status='failed',
                        cleanup_confirmed=True,request_count=1)) as dispatch, \
                     patch.object(experiment,'assess',side_effect=AssertionError('No assessment')):
                    experiment.execute(root/'plan',responder=lambda n,b:b'local',request_setup=expected)
                self.assertEqual(dispatch.call_count,2)
                for call in dispatch.call_args_list:
                    self.assertEqual(call.kwargs['request_setup'],expected)
                    self.assertEqual(call.kwargs['request_budget'],PROFILE)
                    self.assertEqual((call.kwargs['max_requests'],call.kwargs['wall_seconds']),(16,600))
                    self.assertEqual('smoke_data_index' in call.kwargs,arm==ARMS[2])

    def test_prepare_cli_exposes_opt_in_profile_and_rejects_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=['experiments.run','prepare','--assistance',ARMS[0],'--output',str(Path(tmp)/'new'),
                  '--request-budget',PROFILE]
            with patch('sys.argv',args),patch('sys.stdout',new_callable=io.StringIO):
                experiment.main()
            self.assertEqual(read(Path(tmp)/'new/plan.json')['budgets']['model_requests'],16)
            args[-1]='unknown'
            with patch('sys.argv',args),patch('sys.stderr',new_callable=io.StringIO),self.assertRaises(SystemExit):
                experiment.main()

    def test_builder_cli_keeps_eight_default_or_accepts_explicit_sixteen(self):
        for extras,expected in (([],8),(['--request-budget',PROFILE,'--max-requests','16'],16)):
            args=['builder.run','--case','reflective_pin_cell','--prepared-input','unused',
                  '--assistance',ARMS[0],'--output','unused']+extras
            with patch('sys.argv',args),patch('sys.stdout',new_callable=io.StringIO), \
                 patch.object(builder,'run',return_value={'status':'completed'}) as dispatch:
                self.assertEqual(builder.main(),0)
            self.assertEqual(dispatch.call_args.kwargs['max_requests'],expected)


class DispatchBudgets(unittest.TestCase):
    def test_actual_controller_rejects_ninth_or_seventeenth_before_forwarding(self):
        for cap,profile in ((8,None),(16,PROFILE)):
            folder,result,responder,_,_=launch(self,cap=cap,profile=profile,count=cap+1,complete=False)
            self.assertEqual(responder.call_count,cap)
            self.assertEqual(result['request_count'],cap)
            self.assertEqual(result['status'],'failed')
            self.assertIn('Model-request budget',result['error'])
            self.assertTrue(result['cleanup_confirmed'])
            self.assertEqual(len(list(folder.glob('request-*.json'))),cap)
            self.assertFalse((folder/f'request-{cap+1:02d}.json').exists())

    def test_completed_default_and_sixteen_runs_verify_as_retained_submissions(self):
        for cap,profile in ((8,None),(16,PROFILE)):
            folder,result,responder,_,_=launch(self,cap=cap,profile=profile,count=cap)
            self.assertEqual(result['status'],'completed',result)
            self.assertEqual(responder.call_count,cap)
            before={p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
            source,provenance=submission(folder,'reflective_pin_cell')
            self.assertTrue(source.startswith(b'def build_model'))
            self.assertEqual(provenance['actor'],'local_test_double')
            self.assertEqual(before,{p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()})

    def test_configured_lower_cap_is_enforced_inside_sixteen_profile(self):
        _,result,responder,_,_=launch(self,cap=3,profile=PROFILE,count=4)
        self.assertEqual(responder.call_count,3)
        self.assertEqual(result['request_count'],3)
        self.assertEqual(result['status'],'failed')

    def test_first_setup_mismatch_is_recorded_without_a_model_call(self):
        def change(n,body):body['reasoning']['effort']='low'
        folder,result,responder,_,_=launch(self,profile=PROFILE,cap=16,constrain_setup=True,mutate=change)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['request_count'],1)  # Received, retained, never forwarded.
        responder.assert_not_called()
        self.assertFalse(read(folder/'setup-01.json')['matched'])
        self.assertFalse((folder/'response-01.sse').exists())
        self.assertIn('request not forwarded',result['error'])

    def test_later_setup_mismatch_stops_at_that_request_without_retry(self):
        def change(n,body):
            if n==2:body['tools'][0]['description']='changed'
        folder,result,responder,_,_=launch(self,count=3,cap=16,profile=PROFILE,
                                          constrain_setup=True,mutate=change)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(responder.call_count,1)
        self.assertFalse(read(folder/'setup-02.json')['matched'])
        self.assertFalse((folder/'request-03.json').exists())

    def test_all_arms_preserve_matched_generic_setup_and_declared_tool_access(self):
        setups=[]
        for arm,tools in zip(ARMS,((0,0),(1,0),(1,1))):
            folder,result,responder,expected,attached=launch(self,cap=16,profile=PROFILE,
                assistance=arm,constrain_setup=True)
            self.assertEqual(result['status'],'completed',result)
            self.assertEqual(attached,tools)
            self.assertEqual(responder.call_count,1)
            self.assertTrue(read(folder/'setup-01.json')['matched'])
            self.assertEqual(read(folder/'manifest.json')['required_request_setup'],expected)
            source,_=submission(folder,'reflective_pin_cell')
            self.assertTrue(source)
            setups.append(expected)
        self.assertEqual(setups,[setups[0]]*3)

    def test_nonsemantic_session_tool_id_changes_are_accepted(self):
        def change(n,body):body['input'][0]['id']='session-'+str(n)
        folder,result,_,_,_=launch(self,cap=16,profile=PROFILE,count=2,constrain_setup=True,mutate=change)
        self.assertEqual(result['status'],'completed',result)
        submission(folder,'reflective_pin_cell')

    def test_existing_run_cannot_be_overwritten_or_automatically_retried(self):
        folder,result,_,_,_=launch(self,profile=PROFILE,cap=16)
        with patch.object(builder,'load_auth') as auth,patch.object(builder,'docker') as docker, \
             self.assertRaises(FileExistsError):
            builder.run(folder,case=None,prepared_input=None,request_budget=PROFILE,max_requests=16)
        auth.assert_not_called();docker.assert_not_called()


class SubmissionBudgets(unittest.TestCase):
    def setUp(self):
        self.folder,self.result,_,self.setup,_=launch(self,cap=16,profile=PROFILE,count=2,
                                                     assistance=ARMS[2],constrain_setup=True)
        self.assertEqual(self.result['status'],'completed',self.result)

    def reject(self, name, mutate, message):
        path=self.folder/name;old=path.read_bytes()
        value=json.loads(old);mutate(value);exporter.write_json(path,value)
        try:
            with self.assertRaisesRegex(ValueError,message):submission(self.folder,'reflective_pin_cell')
        finally:path.write_bytes(old)

    def test_inconsistent_unknown_or_missing_profile_is_rejected(self):
        for change in (lambda v:v.update(request_budget_profile='unknown'),
                       lambda v:v.pop('request_budget_profile')):
            self.reject('manifest.json',change,'profile|prompt changed')

    def test_cap_cannot_exceed_profile_or_be_noninteger(self):
        for cap in (17,0,True,8.5):
            self.reject('manifest.json',lambda v:v.update(max_requests=cap),'request budget')
        self.reject('manifest.json',lambda v:v.update(max_requests=1),'request count')

    def test_count_must_be_a_positive_integer_within_the_declared_cap(self):
        for count in (17,0,True,2.5):
            self.reject('result.json',lambda v:v.update(request_count=count),'request count')

    def test_request_files_cannot_be_hidden_by_reducing_the_recorded_count(self):
        self.reject('result.json',lambda v:v.update(request_count=1),'evidence/count')
        path=self.folder/'request-03.json';path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'evidence/count'):submission(self.folder,'reflective_pin_cell')

    def test_wall_budget_must_remain_bounded(self):
        self.reject('manifest.json',lambda v:v.update(wall_seconds=601),'wall budget')

    def test_setup_receipts_and_declaration_cannot_be_removed_or_forged(self):
        self.reject('setup-01.json',lambda v:v.update(matched=False),'validation receipt')
        self.reject('setup-01.json',lambda v:v.update(expected_sha256='changed'),'validation receipt')
        self.reject('manifest.json',lambda v:v.pop('required_request_setup'),'setup declaration')
        path=self.folder/'setup-02.json';path.unlink()
        with self.assertRaisesRegex(ValueError,'setup declaration'):submission(self.folder,'reflective_pin_cell')

    def test_changed_request_config_is_rejected_even_with_rebuilt_inventory(self):
        path=self.folder/'request-02.json';value=read(path);value['reasoning']['effort']='low'
        exporter.write_json(path,value)
        exporter.write_json(self.folder/'inventory-02.json',context.request_inventory(value))
        with self.assertRaisesRegex(ValueError,'Prepared request setup'):submission(self.folder,'reflective_pin_cell')

    def test_changed_requested_model_is_rejected(self):
        self.reject('request-02.json',lambda v:v.update(model='another-model'),'Requested model')

    def test_changed_smoke_availability_or_adapter_is_rejected(self):
        self.reject('manifest.json',lambda v:v.pop('smoke_tool'),'Smoke availability')
        self.reject('manifest.json',lambda v:v['smoke_tool'].update(version='changed'),'Smoke adapter')

    def test_no_source_or_scientific_credit_from_failed_or_unclean_run(self):
        self.reject('result.json',lambda v:v.update(status='failed'),'failed or cleanup')
        self.reject('result.json',lambda v:v.update(cleanup_confirmed=False),'failed or cleanup')


if __name__ == '__main__':
    unittest.main()
