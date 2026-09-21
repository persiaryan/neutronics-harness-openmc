"""Declared authoring capabilities must match the runtime before inference."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from builder import openmc_python as environment, run


class EnvironmentTests(unittest.TestCase):
    def test_wrong_version_solver_or_data_is_rejected(self):
        good = {'openmc_version': '0.15.3', 'openmc_init_sha256': 'source-hash',
                'native_openmc_present': False, 'data_directory_present': False,
                'cross_sections_configured': False}
        environment.verify_probe(good, True)
        for change in ({'openmc_version': None}, {'openmc_version': '0.15.2'},
                       {'native_openmc_present': True}, {'data_directory_present': True},
                       {'cross_sections_configured': True}, {'openmc_init_sha256': None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                environment.verify_probe({**good, **change}, True)
        with self.assertRaises(ValueError):
            environment.verify_probe(good, False)

    def test_unlabelled_or_wrong_environment_image_is_rejected(self):
        for info in ({}, {'Config': {'Labels': {environment.LABEL: 'another-version'}}}):
            with self.subTest(info=info), self.assertRaises(ValueError):
                environment.verify_image(info, True)



    def test_build_cleanup_attempts_both_aliases_even_if_one_removal_fails(self):
        calls = []
        def command(args, **kwargs):
            calls.append(args)
            if args[1] == 'build' or (args[1:3] == ['image', 'rm']
                                     and sum(c[1:3] == ['image', 'rm'] for c in calls) == 1):
                raise subprocess.CalledProcessError(1, args)
        with patch.object(environment.subprocess, 'check_output', side_effect=[
                json.dumps([{'Id': environment.BUILDER_ID}]).encode(),
                json.dumps([{'Id': environment.PACKAGES_ID}]).encode()]), \
                patch.object(environment.subprocess, 'run', side_effect=command):
            with self.assertRaisesRegex(RuntimeError, 'cleanup uncertain'):
                environment.main()
        tagged = [c[-1] for c in calls if c[1] == 'tag']
        removed = [c[-1] for c in calls if c[1:3] == ['image', 'rm']]
        self.assertEqual(removed, tagged)


if __name__ == '__main__':
    unittest.main()
