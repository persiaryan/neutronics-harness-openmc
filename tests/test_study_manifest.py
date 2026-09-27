"""Prospective manifest controls with synthetic packages and no authoring/native dispatch."""
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from builder.context import request_setup, sha256
from experiments import manifest as study
from prompts.prepare import CASE_FILES


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(study.encode(value))


def read(path):
    return json.loads(path.read_bytes())


class ManifestFixture(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.output=self.root/'prepared'
        self.tasks=['reflective_pin_cell','reflected_7x7']
        self.spec=dict(study_id='synthetic-comparison', tasks=self.tasks,
            excluded_tasks={c:'outside-this-prospective-selection' for c in CASE_FILES if c not in self.tasks},
            setups=[dict(id='setup-one',model='synthetic-model',request_setup_id='client-one',request_budget=None)],
            arms=[dict(id='base',assistance='guided_construction'),
                  dict(id='assist',assistance='guided_boundaries_smoke')],
            repetitions=2,data_id='data-one',reference_ids={t:'ref-'+t for t in self.tasks},
            assignments=[
                dict(case='reflective_pin_cell',setup='setup-one',arm='assist',repeat=2),
                dict(case='reflected_7x7',setup='setup-one',arm='base',repeat=1),
                dict(case='reflective_pin_cell',setup='setup-one',arm='base',repeat=2),
                dict(case='reflected_7x7',setup='setup-one',arm='assist',repeat=2),
                dict(case='reflective_pin_cell',setup='setup-one',arm='base',repeat=1),
                dict(case='reflected_7x7',setup='setup-one',arm='assist',repeat=1),
                dict(case='reflective_pin_cell',setup='setup-one',arm='assist',repeat=1),
                dict(case='reflected_7x7',setup='setup-one',arm='base',repeat=2)],
            analysis=dict(primary_contrast=['assist','base'],secondary_contrasts=[],
                          trajectory_examples='first_verified_success_and_non_success_per_setup_arm'))
        self.data=self.root/'external-data';self.data.mkdir()
        self.index=self.data/'cross_sections.xml'
        self.index.write_text('<cross_sections><library path="H1.h5" type="neutron" materials="H1"/></cross_sections>')
        (self.data/'H1.h5').write_bytes(b'SYNTHETIC DATA BYTES, NOT QUALIFIED HDF5')
        self.bindings=dict(data={'data-one':str(self.index)},references={},request_setups={})
        for task in self.tasks:
            folder=self.root/('ref-'+task);folder.mkdir()
            (folder/'record.txt').write_text('SYNTHETIC PRIVATE REFERENCE CONTENT')
            self.seal_reference(folder,task)
            self.bindings['references']['ref-'+task]=str(folder)
        self.setup=self.root/'client.json'
        write(self.setup,request_setup(dict(input=[],tools=[],
            instructions='SYNTHETIC PRIVATE INSTRUCTION',stream=True,store=False)))
        self.bindings['request_setups']['client-one']=str(self.setup)
        self.tripwires=[]
        for target in ('builder.run.run','builder.relay.forward','builder.relay.load_auth',
                       'evaluator.run.evaluate','evaluator.transport.transport','evaluator.transport.smoke_xml',
                       'experiments.run.execute','experiments.run.assess'):
            guard=patch(target,side_effect=AssertionError('No model or native execution'))
            self.tripwires.append(guard.start());self.addCleanup(guard.stop)
        real_popen=subprocess.Popen
        def only_git(args,*a,**kw):
            if not isinstance(args,list) or args[0]!='git':
                raise AssertionError('Only read-only Git checks or local Git fixture setup permitted')
            return real_popen(args,*a,**kw)
        guard=patch('subprocess.Popen',side_effect=only_git)
        guard.start();self.addCleanup(guard.stop)

    def tearDown(self):
        for guard in self.tripwires:guard.assert_not_called()

    def seal_reference(self,folder,case):
        files=study.references.inventory(folder,exclude=('manifest.json','seal.sha256'))
        write(folder/'manifest.json',dict(format='frozen-reference-evidence-v1',case=case,
            grading_enabled=False,files=files,technical_status='synthetic_only',
            scientific_review='not_scientifically_qualified'))
        (folder/'seal.sha256').write_text(sha256((folder/'manifest.json').read_bytes())+'\n')

    def prepare(self):
        return study.prepare(self.output,spec=self.spec,bindings=self.bindings)

    def verify(self,**kwargs):
        return study.verify(self.output,bindings=self.bindings,**kwargs)

    def mutate_file(self,name,change,reseal=False):
        path=self.output/name;value=read(path);change(value);write(path,value)
        if reseal:
            (self.output/'seal.sha256').write_text(sha256(path.read_bytes())+'\n')


class Specification(ManifestFixture):
    def test_literal_order_and_counts_with_nonhistorical_labels(self):
        self.prepare();rows=read(self.output/'assignments.json')
        self.assertEqual([r['id'] for r in rows],
            ['slot-0001','slot-0002','slot-0003','slot-0004','slot-0005','slot-0006','slot-0007','slot-0008'])
        self.assertEqual([(r['case'],r['arm'],r['repeat']) for r in rows],[
            ('reflective_pin_cell','assist',2),('reflected_7x7','base',1),
            ('reflective_pin_cell','base',2),('reflected_7x7','assist',2),
            ('reflective_pin_cell','base',1),('reflected_7x7','assist',1),
            ('reflective_pin_cell','assist',1),('reflected_7x7','base',2)])
        self.assertEqual({r['model'] for r in rows},{'synthetic-model'})
        self.assertEqual(self.verify()['assignments'],8)

    def test_budget_ceiling_is_hand_counted_and_respects_access(self):
        self.prepare();m=read(self.output/'manifest.json')
        self.assertEqual(m['ceilings'],dict(sessions=8,model_requests=64,authoring_seconds=4800,
            boundary_calls=8,boundary_recorded_requests=12,smoke_calls=8,smoke_recorded_requests=12,smoke_native_seconds=480,
            independent_final_exports=8,final_native_attempts=8,final_native_seconds=14400,automatic_retries=0))
        self.assertEqual(m['budgets']['setup-one']['base']['model_requests'],8)
        self.assertEqual(m['budgets']['setup-one']['assist']['smoke_calls'],2)
        self.assertFalse(m['execution_authorized']);self.assertFalse(m['dispatch_implemented'])

    def test_per_setup_request_profile_is_matched_across_arms(self):
        second=dict(id='setup-two',model='another-synthetic-model',request_setup_id='client-one',
                    request_budget='authoring-requests-16-v1')
        self.spec['setups'].append(second)
        self.spec['assignments'] += [dict(row,setup='setup-two') for row in self.spec['assignments']]
        self.prepare();m=read(self.output/'manifest.json')
        self.assertEqual(m['assignment_count'],16)
        self.assertEqual(m['ceilings']['model_requests'],192)  # 8*8 + 8*16
        self.assertEqual([m['budgets']['setup-two'][a]['model_requests'] for a in ('base','assist')],[16,16])
        self.assertEqual(self.verify()['assignments'],16)

    def test_missing_duplicate_out_of_range_or_unknown_assignments_rejected(self):
        changes=[
            lambda s:s['assignments'].pop(),
            lambda s:s['assignments'].__setitem__(0,s['assignments'][1]),
            lambda s:s['assignments'][0].update(repeat=True),
            lambda s:s['assignments'][0].update(repeat=3),
            lambda s:s['assignments'][0].update(setup='unknown'),
            lambda s:s['assignments'][0].update(arm='C'),
            lambda s:s['assignments'][0].update(case='unknown')]
        for change in changes:
            spec=copy.deepcopy(self.spec);change(spec)
            with self.assertRaises(ValueError):study.prepare(self.output,spec=spec,bindings=self.bindings)
            self.assertFalse(self.output.exists())

    def test_unknown_duplicate_or_hidden_configuration_rejected(self):
        changes=[
            lambda s:s['arms'][0].update(assistance='unapproved'),
            lambda s:s['arms'].append(s['arms'][0]),
            lambda s:s['setups'][0].update(request_budget='unknown'),
            lambda s:s['setups'][0].update(auth='SYNTHETIC_NOT_ALLOWED'),
            lambda s:s.update(automatic_retries=1),
            lambda s:s.update(repetitions=0),
            lambda s:s.update(repetitions=True),
            lambda s:s['tasks'].append(s['tasks'][0]),
            lambda s:s['excluded_tasks'].clear(),
            lambda s:s.update(study_id='../escape')]
        for change in changes:
            spec=copy.deepcopy(self.spec);change(spec)
            with self.assertRaises((ValueError,TypeError)):study.prepare(self.output,spec=spec,bindings=self.bindings)
            self.assertFalse(self.output.exists())

    def test_analysis_definitions_are_explicit_and_bounded(self):
        self.prepare();analysis=read(self.output/'analysis.json')
        self.assertEqual(analysis['primary_contrast'],['assist','base'])
        self.assertEqual(analysis['task_weights'],'equal')
        self.assertFalse(analysis['setup_pooling'])
        self.assertEqual(analysis['null_scores'],'preserve_null')
        self.assertEqual(analysis['incomplete_inventory'],'withhold_balanced_contrasts')
        self.assertEqual(analysis['success_denominator'],'all_started_assignments')
        self.assertEqual(analysis['score_denominator'],'available_scores_only')

    def test_invalid_or_duplicate_contrasts_and_policy_overrides_rejected(self):
        changes=[
            lambda a:a.update(primary_contrast=['base','base']),
            lambda a:a.update(primary_contrast=['C','A']),
            lambda a:a.update(secondary_contrasts=[['assist','base']]),
            lambda a:a.update(trajectory_examples='retrospective_best'),
            lambda a:a.update(task_weights='pooled')]
        for change in changes:
            spec=copy.deepcopy(self.spec);change(spec['analysis'])
            with self.assertRaises(ValueError):study.validate_spec(spec)

    def test_json_duplicate_keys_nonfinite_and_oversize_are_rejected(self):
        path=self.root/'invalid.json'
        for data in ('{"id":1,"id":2}','{"value":NaN}','{"value":Infinity}','{"value":1e999}'):
            path.write_text(data)
            with self.assertRaises(ValueError):study.read_json(path)
        path.write_bytes(b' '*(study.MAX_JSON_BYTES+1))
        with self.assertRaises(ValueError):study.read_json(path)


class BindingVerification(ManifestFixture):
    def test_prepare_and_verify_use_no_dispatch_and_do_not_change_dependencies(self):
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=self.prepare();snapshot={p.name:p.read_bytes() for p in self.output.iterdir()}
        self.verify(expected_sha256=result['manifest_sha256'])
        self.assertEqual(snapshot,{p.name:p.read_bytes() for p in self.output.iterdir()})
        for path,raw in before.items():self.assertEqual((self.root/path).read_bytes(),raw)
        self.assertEqual(set(snapshot),set(study.FILES))
        self.assertEqual(result['model_calls'],0);self.assertEqual(result['native_runs'],0)

    def test_manifest_has_ids_and_hashes_without_paths_or_private_content(self):
        self.prepare()
        serialized=b''.join(p.read_bytes() for p in self.output.iterdir()).decode()
        for forbidden in (str(self.root),'SYNTHETIC PRIVATE INSTRUCTION','SYNTHETIC PRIVATE REFERENCE CONTENT',
                          'SYNTHETIC DATA BYTES'):
            self.assertNotIn(forbidden,serialized)
        m=read(self.output/'manifest.json')
        self.assertEqual(m['resources']['data']['data-one']['files'],2)
        self.assertEqual(m['resources']['data']['data-one']['qualification'],'not_run')
        self.assertEqual(m['resources']['references']['ref-reflective_pin_cell']['qualification'],
                         'sealed_bytes_only_not_scientific_approval')

    def test_data_bytes_change_is_detected_even_if_index_is_unchanged(self):
        self.prepare();(self.data/'H1.h5').write_bytes(b'CHANGED SYNTHETIC BYTES')
        with self.assertRaisesRegex(ValueError,'dependency changed'):self.verify()

    def test_data_index_change_missing_file_and_extra_file_rejected(self):
        self.prepare();original=self.index.read_bytes()
        self.index.write_text(original.decode().replace('materials="H1"','materials="H2"'))
        with self.assertRaises(ValueError):self.verify()
        self.index.write_bytes(original)
        (self.data/'unexpected.txt').write_text('extra')
        with self.assertRaises(ValueError):self.verify()
        (self.data/'unexpected.txt').unlink();(self.data/'H1.h5').unlink()
        with self.assertRaises(ValueError):self.verify()

    def test_sealed_reference_change_rejected_even_after_new_valid_seal(self):
        self.prepare();folder=Path(self.bindings['references']['ref-reflective_pin_cell'])
        (folder/'record.txt').write_text('CHANGED SYNTHETIC REFERENCE')
        with self.assertRaises(ValueError):self.verify()
        self.seal_reference(folder,'reflective_pin_cell')
        with self.assertRaisesRegex(ValueError,'dependency changed'):self.verify()

    def test_reference_for_wrong_task_and_unsealed_reference_rejected(self):
        folder=Path(self.bindings['references']['ref-reflective_pin_cell'])
        self.seal_reference(folder,'reflected_7x7')
        with self.assertRaises(ValueError):self.prepare()
        (folder/'seal.sha256').unlink()
        with self.assertRaises(ValueError):self.prepare()

    def test_changed_request_configuration_or_instruction_identity_rejected(self):
        self.prepare();original=self.setup.read_bytes()
        value=read(self.setup);value['request_configuration']['reasoning']={'effort':'high'}
        write(self.setup,value)
        with self.assertRaises(ValueError):self.verify()
        self.setup.write_bytes(original)
        value=read(self.setup);value['top_level_instructions_sha256']='f'*64;write(self.setup,value)
        with self.assertRaises(ValueError):self.verify()

    def test_raw_provider_body_is_not_a_request_setup_descriptor(self):
        write(self.setup,dict(model='synthetic',input=[],tools=[],authorization='SYNTHETIC_NOT_ALLOWED'))
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.output.exists())

    def test_missing_extra_and_wrong_local_resource_bindings_rejected(self):
        for kind in ('data','references','request_setups'):
            changed=copy.deepcopy(self.bindings);changed[kind]={}
            with self.assertRaises(ValueError):study.prepare(self.output,spec=self.spec,bindings=changed)
        changed=copy.deepcopy(self.bindings);changed['request_setups']['extra']=str(self.setup)
        with self.assertRaises(ValueError):study.prepare(self.output,spec=self.spec,bindings=changed)

    def test_relocating_identical_external_resources_preserves_identity(self):
        import shutil
        self.prepare();copy_root=self.root/'relocated'
        shutil.copytree(self.data,copy_root/'data')
        for resource,path in list(self.bindings['references'].items()):
            shutil.copytree(path,copy_root/resource);self.bindings['references'][resource]=str(copy_root/resource)
        shutil.copyfile(self.setup,copy_root/'setup.json')
        self.bindings['request_setups']['client-one']=str(copy_root/'setup.json')
        self.bindings['data']['data-one']=str(copy_root/'data/cross_sections.xml')
        self.assertEqual(self.verify()['status'],'verified_manifest')

    def test_links_in_data_setup_or_preparation_are_rejected(self):
        link=self.root/'setup-link.json';link.symlink_to(self.setup)
        self.bindings['request_setups']['client-one']=str(link)
        with self.assertRaises(ValueError):self.prepare()
        self.bindings['request_setups']['client-one']=str(self.setup)
        h5=self.data/'H1.h5';h5.unlink();h5.symlink_to(self.setup)
        with self.assertRaises(ValueError):self.prepare()

    def test_overwrite_and_output_inside_external_package_are_rejected(self):
        self.prepare()
        with self.assertRaises(ValueError):self.prepare()
        for protected in (self.data/'new',Path(self.bindings['references']['ref-reflective_pin_cell'])/'new'):
            with self.assertRaises(ValueError):study.prepare(protected,spec=self.spec,bindings=self.bindings)
            self.assertFalse(protected.exists())

    def test_protocol_tool_prompt_and_source_identity_changes_rejected(self):
        self.prepare()
        original=study.condition_prompt
        with patch.object(study,'condition_prompt',side_effect=lambda *a,**kw:original(*a,**kw)+'changed'):
            with self.assertRaises(ValueError):self.verify()
        with patch.object(study,'BOUNDARY_PROTOCOL','wrong-route'):
            with self.assertRaises(ValueError):self.verify()
        with patch.object(study.boundary_tool,'identity',return_value={'changed':True}):
            with self.assertRaises(ValueError):self.verify()
        with patch.object(study.smoke_tool,'identity',return_value={'changed':True}):
            with self.assertRaises(ValueError):self.verify()
        sources=study.source_inventory();sources['builder/route.py']='f'*64
        with patch.object(study,'source_inventory',return_value=sources):
            with self.assertRaises(ValueError):self.verify()


class RetainedPreparation(ManifestFixture):
    def test_order_analysis_spec_budget_and_protocol_edits_are_rejected(self):
        self.prepare()
        snapshot={n:(self.output/n).read_bytes() for n in study.FILES}
        changes=[
            ('assignments.json',lambda v:v.reverse(),False),
            ('analysis.json',lambda v:v.update(task_weights='pooled'),False),
            ('spec.json',lambda v:v.update(repetitions=3),False),
            ('manifest.json',lambda v:v.update(evaluator_protocol='wrong'),True),
            ('manifest.json',lambda v:v['ceilings'].update(model_requests=999),True),
            ('manifest.json',lambda v:v.update(execution_authorized=True),True),
            ('manifest.json',lambda v:v.update(format='historical-abc'),True)]
        for name,change,reseal in changes:
            self.mutate_file(name,change,reseal)
            with self.assertRaises(ValueError):self.verify()
            for n,raw in snapshot.items():(self.output/n).write_bytes(raw)

    def test_missing_extra_or_symlinked_artifact_is_rejected(self):
        self.prepare();extra=self.output/'extra.json';extra.write_text('{}')
        with self.assertRaises(ValueError):self.verify()
        extra.unlink();path=self.output/'analysis.json';raw=path.read_bytes();path.unlink()
        with self.assertRaises(ValueError):self.verify()
        other=self.root/'analysis.json';other.write_bytes(raw);path.symlink_to(other)
        with self.assertRaises(ValueError):self.verify()

    def test_trusted_expected_hash_rejects_an_alternative_valid_manifest(self):
        original=self.prepare()['manifest_sha256']
        self.output=self.root/'alternative'
        self.spec['assignments'].reverse()
        self.prepare()
        self.assertEqual(self.verify()['status'],'verified_manifest')
        with self.assertRaisesRegex(ValueError,'trusted expected hash'):self.verify(expected_sha256=original)

    def test_private_local_bindings_resolve_relative_paths_and_cli_stays_nonexecuting(self):
        local=self.root/'bindings.json'
        bindings={kind:{name:str(Path(path).relative_to(self.root)) for name,path in rows.items()}
                  for kind,rows in self.bindings.items()}
        write(local,bindings);spec=self.root/'spec-input.json';write(spec,self.spec)
        for args in (['prepare','--spec',str(spec)],['verify']):
            with patch('sys.argv',['manifest',*args,'--output',str(self.output),'--bindings',str(local)]), \
                 patch('sys.stdout',new_callable=io.StringIO) as stdout:
                study.main()
            result=json.loads(stdout.getvalue());self.assertEqual(result['model_calls'],0)
            self.assertFalse(result['execution_authorized'])

    def test_cli_error_does_not_echo_sensitive_local_paths(self):
        write(self.root/'bindings.json',{})
        with patch('sys.argv',['manifest','verify','--output',str(self.root/'SYNTHETIC_PRIVATE_PATH'),
              '--bindings',str(self.root/'bindings.json')]),patch('sys.stderr',new_callable=io.StringIO) as err:
            with self.assertRaises(SystemExit):study.main()
        self.assertNotIn('SYNTHETIC_PRIVATE_PATH',err.getvalue())


class CommittedPreparation(ManifestFixture):
    def test_optional_commit_gate_checks_source_and_all_prepared_files(self):
        repo=self.root/'repo';(repo/'builder').mkdir(parents=True)
        source=repo/'builder/source.py';source.write_text('SYNTHETIC_IMPLEMENTATION = True\n')
        def git(*args):
            return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL)
        git('init','-q')
        git('-c','user.name=Local Test','-c','user.email=test@example.invalid','add','builder/source.py')
        git('-c','user.name=Local Test','-c','user.email=test@example.invalid','commit','-qm','synthetic base')
        self.output=repo/'prepared'
        with patch.object(study,'ROOT',repo):
            self.prepare()
            with self.assertRaises(subprocess.CalledProcessError):self.verify(require_committed=True)
            git('add','prepared')
            git('-c','user.name=Local Test','-c','user.email=test@example.invalid','commit','-qm','synthetic preparation')
            self.assertTrue(self.verify(require_committed=True)['committed'])
            # Working bytes and manifest can agree but an uncommitted replacement must still fail.
            self.spec['assignments'].reverse();self.output=repo/'replacement';self.prepare()
            with self.assertRaises(subprocess.CalledProcessError):self.verify(require_committed=True)
            source.write_text('SYNTHETIC_IMPLEMENTATION = False\n')
            self.output=repo/'prepared'
            with self.assertRaises(ValueError):self.verify(require_committed=True)


if __name__ == '__main__':
    unittest.main()
