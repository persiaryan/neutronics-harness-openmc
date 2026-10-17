"""Candidate-suite isolation and identity checks; no OpenMC or model calls."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prompts import confirmation, prepare as public


class ConfirmationTaskTests(unittest.TestCase):
    def test_twelve_new_tasks_are_separate_from_the_historical_six(self):
        value, _ = confirmation.suite()
        self.assertEqual(len(value['tasks']), 12)
        self.assertEqual(len(public.CASE_FILES), 6)
        self.assertTrue(set(confirmation.TASKS).isdisjoint(public.CASE_FILES))
        self.assertEqual([r['family'] for r in value['tasks']],
                         ['reuse']*4 + ['transfer']*4 + ['control']*4)
        self.assertFalse(value['assessment_ready'])
        self.assertEqual(value['reference_status'], 'not_created')
        self.assertEqual(value['agent_generations'], 0)
        self.assertEqual(value['campaign_design']['assignments'], 240)
        self.assertFalse(value['campaign_design']['sample_size_justified'])

    def test_each_bundle_contains_only_template_and_selected_specification(self):
        value, _ = confirmation.suite()
        with tempfile.TemporaryDirectory() as tmp:
            for record in value['tasks']:
                output = Path(tmp)/record['id']
                manifest = confirmation.prepare(record['id'], output)
                prompt = (output/'prompt.txt').read_text()
                expected = public.read_public_text('template_factory_v1.md').replace(
                    '{{TASK_SPECIFICATION}}', public.read_public_text(record['path']).rstrip()).rstrip() + '\n'
                self.assertEqual(prompt, expected)
                self.assertEqual(json.loads((output/'messages.json').read_text()),
                                 [dict(role='user', content=prompt)])
                self.assertEqual(manifest['prompt_sha256'], hashlib.sha256(prompt.encode()).hexdigest())
                self.assertEqual(set(p.name for p in output.iterdir()),
                                 {'prompt.txt', 'messages.json', 'manifest.json'})
                self.assertNotIn('region-ownership', prompt)
                self.assertFalse(manifest['assessment_ready'])
                self.assertFalse(manifest['dispatch_implemented'])

    def copied_public(self, root):
        destination = root/'prompts'
        shutil.copytree(public.PROMPT_ROOT/'confirmation_v1', destination/'confirmation_v1')
        shutil.copy(public.PROMPT_ROOT/'template_factory_v1.md', destination)
        return destination

    def test_changed_specification_or_template_is_rejected_before_output(self):
        for relative in ('confirmation_v1/cases/offset_plate_bank.md', 'template_factory_v1.md'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                copied = self.copied_public(root)
                (copied/relative).write_text('Changed bytes')
                with patch.object(public, 'PROMPT_ROOT', copied), self.assertRaises(ValueError):
                    confirmation.prepare('offset_plate_bank', root/'output')
                self.assertFalse((root/'output').exists())

    def test_unknown_or_private_manifest_paths_are_rejected(self):
        for path in ('../evaluation/private.py', '/private.py',
                     'confirmation_v1/cases/staggered_seven_pin_cluster.md'):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                copied = self.copied_public(root)
                file = copied/confirmation.MANIFEST
                value = json.loads(file.read_text())
                value['tasks'][0]['path'] = path
                file.write_text(json.dumps(value))
                with patch.object(public, 'PROMPT_ROOT', copied), self.assertRaises(ValueError):
                    confirmation.prepare('offset_plate_bank', root/'output')
                self.assertFalse((root/'output').exists())

    def test_symlinked_specification_is_rejected_even_with_matching_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            copied = self.copied_public(root)
            path = copied/'confirmation_v1/cases/offset_plate_bank.md'
            private = root/'private.md'
            private.write_bytes(path.read_bytes())
            path.unlink()
            path.symlink_to(private)
            with patch.object(public, 'PROMPT_ROOT', copied), self.assertRaisesRegex(ValueError, 'symlinks'):
                confirmation.prepare('offset_plate_bank', root/'output')
            self.assertFalse((root/'output').exists())

    def test_unknown_case_and_existing_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaises(ValueError):
                confirmation.prepare('../private', root/'unknown')
            self.assertFalse((root/'unknown').exists())
            output = root/'bundle'
            confirmation.prepare('offset_plate_bank', output)
            before = {p.name:p.read_bytes() for p in output.iterdir()}
            with self.assertRaises(FileExistsError):
                confirmation.prepare('offset_plate_bank', output)
            self.assertEqual(before, {p.name:p.read_bytes() for p in output.iterdir()})
