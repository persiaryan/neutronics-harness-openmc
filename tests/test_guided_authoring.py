"""Guided policy routing and unchanged optional prompts, without live inference."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from builder.route import condition_prompt, GUIDED_POLICY, CONSTRUCTION_POLICY
from experiments import run as experiment
from prompts.prepare import build_prompt

ROOT = Path(__file__).resolve().parents[1]


class GuidedPolicy(unittest.TestCase):
    def test_new_optional_presentation_is_versioned_not_relabelled_as_old_prompt(self):
        for case in ('reflective_pin_cell', 'moderated_cylinder'):
            # Tracked public preparation from the previous pilot plus literal hashes
            # retained in its live manifests; do not depend on untracked live files.
            expected = {'reflective_pin_cell': 'fc811b865c16a4741989ee51ef7fa53ddce6f7d4482f7e99aa5ded0426873541',
                        'moderated_cylinder': 'dc78dc6f5c9a617f94bae5026c1fad1e425078541eccc098c75adf88803bc004'}
            prompt = condition_prompt(build_prompt(case), 'boundaries')
            self.assertNotEqual(experiment.sha256(prompt.encode()), expected[case])
            self.assertIn('candidate-boundary-feedback-v1', prompt)
            self.assertIn('Tool availability does not require tool use.', prompt)

    def test_guided_prompt_requires_attempt_not_just_conditional_inspection(self):
        prompt = condition_prompt(build_prompt('reflective_pin_cell'), 'guided_boundaries')
        self.assertNotIn('Tool availability does not require tool use.', prompt)
        self.assertNotIn('You may inspect', prompt)
        self.assertIn('actually attempt to call build_model()', prompt)
        self.assertIn('At most one construction/export repair attempt', prompt)
        self.assertIn('Re-export after any model change.', prompt)
        self.assertIn('Unsupported observations are indeterminate', prompt)
        self.assertIn('brief Python comment in the final source', prompt)
        self.assertIn('timeout 60s python3 -B -', prompt)
        self.assertIn("model.export_to_model_xml(path='model.xml')", prompt)
        self.assertIn('Tool availability does not require tool use.', condition_prompt('', 'boundaries'))
        self.assertNotIn('guided-working-export', condition_prompt('', 'generic'))

    def test_matched_conditions_share_the_complete_construction_policy(self):
        shared = CONSTRUCTION_POLICY.read_text()
        a = condition_prompt('', 'guided_construction')
        b = condition_prompt('', 'guided_boundaries')
        self.assertIn(shared, a); self.assertIn(shared, b)
        self.assertNotIn('/work/inspect_boundaries.py', a)
        self.assertIn('/work/inspect_boundaries.py', b)

    def test_prepare_binds_guided_policy_and_keeps_budgets_and_both_cases(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment.agent, 'run') as dispatch:
            folder = Path(tmp)/'pilot'
            plan = experiment.prepare(folder, assistance='guided_boundaries')
            self.assertEqual(plan['condition'], 'generic_coding_guided_boundaries_v3')
            self.assertEqual(plan['cases'], ['reflective_pin_cell', 'moderated_cylinder'])
            self.assertEqual(plan['budgets'], experiment.BUDGETS)
            for case in plan['cases']:
                actual = condition_prompt((folder/'inputs'/case/'prompt.txt').read_text(), 'guided_boundaries')
                self.assertEqual(plan['authoring_prompt_sha256'][case], experiment.sha256(actual.encode()))
            # A changed prepared condition must stop before any live request.
            plan['authoring_prompt_sha256']['reflective_pin_cell'] = 'changed'
            (folder/'plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'guided policy/prompt changed'):
                experiment.execute(folder)
            dispatch.assert_not_called()
            self.assertFalse((folder/'runs').exists())

    def test_later_policy_edit_cannot_silently_change_prepared_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment.agent, 'run') as dispatch:
            folder = Path(tmp)/'pilot'
            experiment.prepare(folder, assistance='guided_boundaries')
            changed = Path(tmp)/'policy.md'; changed.write_text(GUIDED_POLICY.read_text()+'\nChanged.\n')
            with patch('builder.route.GUIDED_POLICY', changed):
                with self.assertRaisesRegex(ValueError, 'guided policy/prompt changed'):
                    experiment.execute(folder)
            dispatch.assert_not_called()
