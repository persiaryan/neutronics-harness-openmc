"""D procedure binding and A/D preparation; synthetic provider/processes only."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from builder import context, region_skill, route, run as builder
from builder.submission import submission
from experiments import run as experiment
from experiments import dashboard_campaign as campaign
from prompts.prepare import build_prompt, prepare as prepare_prompt
from tests.test_request_profiles import launch, synthetic_body

D = region_skill.ASSISTANCE
PROFILE = 'authoring-requests-16-v1'


class RegionSkillTests(unittest.TestCase):
    def test_all_historical_abc_prompts_match_frozen_pre_intervention_hashes(self):
        fixture = Path(__file__).parent / 'fixtures/region_skill_prompt_baseline.json'
        baseline = json.loads(fixture.read_text())['prompts']
        for case, arms in baseline.items():
            for arm, profiles in arms.items():
                for cap, expected in profiles.items():
                    with self.subTest(case=case, arm=arm, cap=cap):
                        prompt = route.condition_prompt(build_prompt(case), arm,
                                                        request_budget=PROFILE if cap == '16' else None)
                        self.assertEqual(context.sha256(prompt.encode()), expected)

    def test_d_is_exactly_a_plus_the_one_allowlisted_procedure(self):
        raw, identity = region_skill.material()
        for profile in (None, PROFILE):
            a = route.condition_prompt(build_prompt('two_composition_5x5'), 'guided_construction',
                                       request_budget=profile)
            d = route.condition_prompt(build_prompt('two_composition_5x5'), D, request_budget=profile)
            self.assertEqual(d, a + region_skill.HEADER + raw.decode())
            self.assertEqual(experiment.budgets(D, profile),
                             experiment.budgets('guided_construction', profile))
        self.assertNotIn(D, route.BOUNDARY_CONDITIONS | route.SMOKE_CONDITIONS)
        self.assertEqual(identity['delivery'], 'preloaded_prompt')
        self.assertEqual(identity['sha256'], context.sha256(raw))

    def test_prepare_snapshots_exact_content_and_describes_coding_only(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment.agent, 'run') as dispatch:
            root = Path(tmp)
            plan = experiment.prepare(root/'D', assistance=D, request_budget=PROFILE,
                                      cases=('two_composition_5x5',))
            raw, identity = region_skill.material()
            self.assertEqual(plan['region_ownership_skill'], identity)
            self.assertEqual((root/'D'/region_skill.SNAPSHOT).read_bytes(), raw)
            self.assertEqual(plan['budgets']['model_requests'], 16)
            self.assertEqual(plan['observation_configuration']['configuration']['id'], 'D')
            self.assertEqual(plan['observation_configuration']['configuration']['tools'], ['coding'])
            self.assertEqual(plan['observation_configuration']['tools'][0]['id'], 'coding')
            dispatch.assert_not_called()

    def test_prepared_tampering_stops_before_dispatch(self):
        for change in ('missing_identity', 'identity', 'snapshot', 'missing_snapshot', 'source'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); folder = root/'D'
                plan = experiment.prepare(folder, assistance=D)
                if change == 'missing_identity':
                    del plan['region_ownership_skill']
                elif change == 'identity':
                    plan['region_ownership_skill']['delivery'] = 'native_discovery'
                elif change == 'snapshot':
                    (folder/region_skill.SNAPSHOT).write_text('changed')
                elif change == 'missing_snapshot':
                    (folder/region_skill.SNAPSHOT).unlink()
                (folder/'plan.json').write_text(json.dumps(plan))
                changed = root/'changed.md'
                changed.write_bytes(region_skill.material()[0] + b'\nCHANGED PROCEDURE\n')
                with patch.object(region_skill, 'PATH', changed if change == 'source' else region_skill.PATH), \
                     patch.object(experiment.agent, 'run') as dispatch:
                    with self.assertRaisesRegex(ValueError, 'Region skill'):
                        experiment.execute(folder)
                dispatch.assert_not_called()
                self.assertFalse((folder/'runs').exists())

    def test_a_rejects_undeclared_skill_metadata_or_snapshot(self):
        for field in ('identity', 'snapshot'):
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)/'A'
                plan = experiment.prepare(folder, assistance='guided_construction')
                if field == 'identity':
                    plan['region_ownership_skill'] = region_skill.material()[1]
                else:
                    (folder/region_skill.SNAPSHOT).write_bytes(region_skill.material()[0])
                (folder/'plan.json').write_text(json.dumps(plan))
                with patch.object(experiment.agent, 'run') as dispatch, \
                     self.assertRaisesRegex(ValueError, 'Undeclared region skill'):
                    experiment.execute(folder)
                dispatch.assert_not_called()

    def test_changed_binding_stops_builder_before_authentication_or_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); prepare_prompt('reflective_pin_cell', root/'input')
            wrong = dict(region_skill.material()[1], sha256='0'*64)
            with patch.object(builder, 'load_auth') as auth, patch.object(builder, 'docker') as docker:
                with self.assertRaisesRegex(ValueError, 'Prepared region skill changed'):
                    builder.run(root/'builder', case='reflective_pin_cell', prepared_input=root/'input',
                                assistance=D, expected_region_skill=wrong)
            auth.assert_not_called(); docker.assert_not_called()

    def test_material_rejects_linked_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); target = root/'content.md'; target.write_bytes(region_skill.material()[0])
            link = root/'link.md'; link.symlink_to(target)
            with patch.object(region_skill, 'PATH', link), self.assertRaisesRegex(ValueError, 'symlinks'):
                region_skill.material()

    def test_execution_passes_bound_identity_to_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = experiment.prepare(root/'D', assistance=D, request_budget=PROFILE,
                                      cases=('reflective_pin_cell',))
            with patch.object(experiment.agent, 'run', return_value={'status':'failed', 'cleanup_confirmed':True}) as dispatch:
                experiment.execute(root/'D', responder=lambda *_: b'local')
            self.assertEqual(dispatch.call_args.kwargs['expected_region_skill'], plan['region_ownership_skill'])
            self.assertEqual(dispatch.call_args.kwargs['max_requests'], 16)

    def test_retained_d_submission_binds_skill_and_preserves_context_isolation(self):
        folder, result, responder, _, adapters = launch(self, assistance=D, cap=16, profile=PROFILE,
                                                       constrain_setup=True)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(adapters, (0, 0))
        source, provenance = submission(folder, 'reflective_pin_cell')
        self.assertEqual(provenance['region_ownership_skill'], region_skill.material()[1])
        self.assertEqual((folder/region_skill.SNAPSHOT).read_bytes(), region_skill.material()[0])
        body = json.loads((folder/'request-01.json').read_text())
        inventory = context.request_inventory(body)
        self.assertFalse(inventory['skills_catalog_present'])
        self.assertFalse(inventory['memory_block_present'])
        self.assertEqual(inventory['user_texts'][-1], (folder/'prompt.txt').read_text())
        self.assertEqual(source, (folder/'candidate.py').read_bytes())
        self.assertEqual(responder.call_count, 1)

    def test_retained_snapshot_identity_and_first_request_tampering_are_rejected(self):
        for change in ('snapshot', 'identity', 'request'):
            with self.subTest(change=change):
                folder, result, _, _, _ = launch(self, assistance=D)
                self.assertEqual(result['status'], 'completed')
                if change == 'snapshot':
                    (folder/region_skill.SNAPSHOT).write_text('changed')
                elif change == 'identity':
                    path = folder/'manifest.json'; manifest = json.loads(path.read_text())
                    manifest['region_ownership_skill']['sha256'] = '0'*64
                    path.write_text(json.dumps(manifest))
                else:
                    path = folder/'request-01.json'; body = json.loads(path.read_text())
                    body['input'][-1]['content'][0]['text'] = 'Procedure omitted'
                    path.write_text(json.dumps(body))
                    (folder/'inventory-01.json').write_text(json.dumps(context.request_inventory(body)))
                with self.assertRaisesRegex(ValueError, 'Region skill'):
                    submission(folder, 'reflective_pin_cell')

    def test_does_not_accept_native_skill_catalog_as_preloaded_d(self):
        def insert_catalog(number, body):
            body['input'][-1]['content'][0]['text'] += '\n<skills_instructions>UNDECLARED</skills_instructions>'
        folder, result, responder, _, _ = launch(self, assistance=D, mutate=insert_catalog)
        self.assertEqual(result['status'], 'failed')
        responder.assert_not_called()


class RegionCampaignTests(unittest.TestCase):
    def test_prepare_36_balanced_ad_slots_with_no_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); index = root/'index'; index.write_text('synthetic; not nuclear data')
            setups = root/'setups.json'
            setups.write_text(json.dumps({m:context.request_setup(synthetic_body()) for m in campaign.MODELS}))
            with patch.object(campaign, 'execute') as execute, patch.object(campaign, 'evaluate') as evaluate:
                manifest = campaign.prepare_campaign(root/'comparison', pilot=False, data_index=index,
                    setup_file=setups, comparison=campaign.REGION_COMPARISON)
            self.assertEqual(manifest['sessions'], 36)
            self.assertEqual(manifest['maximum_model_requests'], 576)
            self.assertEqual(manifest['repeats'], 3)
            self.assertEqual(manifest['automatic_retries'], 0)
            self.assertEqual(set(manifest['arms']), {'A','D'})
            self.assertEqual(manifest['kind'], 'region_ownership_development_pilot')
            assignments = {(r['model'],r['arm'],r['case'],r['repeat']) for r in manifest['rows']}
            expected = {(m,a,t,r) for m in campaign.MODELS for a in ('A','D')
                        for t in ('two_composition_5x5','axially_zoned_5x5','reflective_pin_cell')
                        for r in (1,2,3)}
            self.assertEqual(assignments, expected)
            for row in manifest['rows']:
                folder = root/'comparison'/row['path']
                plan = json.loads((folder/'plan.json').read_text())
                region_skill.verify(folder, plan, plan['assistance'])
                self.assertEqual('region_ownership_skill' in plan, row['arm']=='D')
                self.assertEqual(plan['budgets']['model_requests'], 16)
                self.assertEqual(plan['budgets']['authoring_seconds'], 600)
                self.assertEqual(plan['observation_configuration']['configuration']['tools'], ['coding'])
            execute.assert_not_called(); evaluate.assert_not_called()

    def test_comparison_cannot_be_mixed_with_public_reference_pilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'no-output'
            with self.assertRaisesRegex(ValueError, 'separately'):
                campaign.prepare_campaign(root, pilot=True, data_index=None, setup_file=None,
                                          comparison=campaign.REGION_COMPARISON)
            self.assertFalse(root.exists())
