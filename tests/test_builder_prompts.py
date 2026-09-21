"""Test the public-input boundary without importing or running OpenMC."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prompts import prepare as prompts


class BuilderPromptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.public = self.root / "prompts"
        (self.public / "cases").mkdir(parents=True)
        (self.public / "template_factory_v1.md").write_text("Instructions\n{{TASK_SPECIFICATION}}\n")
        (self.public / "cases/reflected_7x7.md").write_text("Public task input.\n")
        self.private = self.root / "evaluation"
        self.private.mkdir()
        (self.private / "model.py").write_text("PRIVATE_MODEL_CANARY")
        (self.private / "result.json").write_text("PRIVATE_RESULT_CANARY")
        (self.root / "AGENTS.md").write_text("PRIVATE_CONTEXT_CANARY")
        patcher = patch.object(prompts, "PROMPT_ROOT", self.public)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_only_two_allowlisted_inputs_are_read(self):
        reads = []
        original = Path.read_text

        def read(path, *args, **kwargs):
            reads.append(path)
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read), patch.dict(
                os.environ, {"BUILDER_TEST_PRIVATE_CONTEXT": "PRIVATE_ENV_CANARY"}):
            prompts.prepare("reflected_7x7", self.root / "bundle")
        self.assertEqual(reads, [self.public / "template_factory_v1.md",
                                 self.public / "cases/reflected_7x7.md"])
        files = {p.name: p.read_text() for p in (self.root / "bundle").iterdir()}
        self.assertEqual(set(files), {"prompt.txt", "messages.json", "manifest.json"})
        for content in files.values():
            self.assertNotIn("PRIVATE_", content)
            self.assertNotIn(str(self.root), content)
        self.assertEqual(json.loads(files["messages.json"]), [
            {"role": "user", "content": "Instructions\nPublic task input.\n"}])
        manifest = json.loads(files["manifest.json"])
        self.assertEqual(manifest["prompt_sha256"],
                         hashlib.sha256(files["prompt.txt"].encode()).hexdigest())
        self.assertEqual(manifest["messages_sha256"],
                         hashlib.sha256(files["messages.json"].encode()).hexdigest())
        self.assertFalse(manifest["dispatch_implemented"])

    def test_private_tree_is_not_required(self):
        for path in self.private.iterdir():
            path.unlink()
        self.private.rmdir()
        self.assertEqual(prompts.build_prompt("reflected_7x7"),
                         "Instructions\nPublic task input.\n")

    def test_unknown_case_and_path_traversal_are_rejected(self):
        for case in ("unknown", "../evaluation/model.py", str(self.private)):
            with self.subTest(case=case), self.assertRaises(ValueError):
                prompts.prepare(case, self.root / "bundle")
            self.assertFalse((self.root / "bundle").exists())

    def test_symlink_to_private_reference_is_rejected(self):
        task = self.public / "cases/reflected_7x7.md"
        task.unlink()
        task.symlink_to(self.private / "model.py")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            prompts.prepare("reflected_7x7", self.root / "bundle")
        self.assertFalse((self.root / "bundle").exists())

    def test_linked_case_directory_is_rejected(self):
        directory = self.public / "cases"
        (directory / "reflected_7x7.md").unlink()
        directory.rmdir()
        directory.symlink_to(self.private, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            prompts.build_prompt("reflected_7x7")

    def test_hardlink_to_private_reference_is_rejected(self):
        task = self.public / "cases/reflected_7x7.md"
        task.unlink()
        os.link(self.private / "model.py", task)
        with self.assertRaisesRegex(ValueError, "hard links"):
            prompts.prepare("reflected_7x7", self.root / "bundle")
        self.assertFalse((self.root / "bundle").exists())

    def test_repeated_output_is_not_overwritten(self):
        output = self.root / "bundle"
        prompts.prepare("reflected_7x7", output)
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        (self.public / "cases/reflected_7x7.md").write_text("Changed task.")
        with self.assertRaises(FileExistsError):
            prompts.prepare("reflected_7x7", output)
        self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_ambiguous_template_is_rejected(self):
        for text in ("No marker", "{{TASK_SPECIFICATION}}{{TASK_SPECIFICATION}}"):
            (self.public / "template_factory_v1.md").write_text(text)
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "exactly one"):
                prompts.prepare("reflected_7x7", self.root / "bundle")
            self.assertFalse((self.root / "bundle").exists())


if __name__ == "__main__":
    unittest.main()
