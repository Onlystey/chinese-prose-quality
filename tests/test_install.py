"""Meaningful ownership and preservation tests using isolated temporary homes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "install.py"
spec = importlib.util.spec_from_file_location("cpq_installer", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "test-home"
        self.codex = self.home / ".codex"
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("---\nname: chinese-prose-quality\ndescription: Test fixture.\n---\nReview prose.\n", encoding="utf-8")
        (self.source / "references").mkdir()
        (self.source / "references" / "rules.md").write_text("Keep meaning.\n", encoding="utf-8")
        self.p = mod.paths(self.home, self.codex)

    def install(self):
        return mod.install(self.source, self.home, self.codex)

    def agents(self, value):
        self.codex.mkdir(parents=True, exist_ok=True)
        self.p["agents"].write_bytes(value)

    def test_install_and_idempotence(self):
        self.agents("已有全局要求。\n".encode())
        result = self.install()
        self.assertTrue(result["changed"])
        self.assertEqual(Path(result["agents_backup"]).read_bytes(), "已有全局要求。\n".encode())
        self.assertTrue(self.p["link"].is_symlink())
        self.assertEqual(self.p["link"].resolve(), self.p["target"].resolve())
        self.assertIn(str(self.p["profile"]), self.p["agents"].read_text())
        before = self.p["agents"].read_bytes()
        count = len(list(self.p["backups"].iterdir()))
        self.assertFalse(self.install()["changed"])
        self.assertEqual(before, self.p["agents"].read_bytes())
        self.assertEqual(count, len(list(self.p["backups"].iterdir())))
        self.assertEqual(mod.status(self.home, self.codex)["state"], "installed")

    def test_unmanaged_same_name_is_not_overwritten(self):
        self.p["target"].mkdir(parents=True)
        file = self.p["target"] / "mine.txt"
        file.write_text("private work")
        with self.assertRaises(mod.InstallError):
            self.install()
        self.assertEqual(file.read_text(), "private work")
        self.assertFalse(self.p["agents"].exists())

    def test_conflicting_link_is_not_replaced(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        self.p["link"].parent.mkdir(parents=True)
        self.p["link"].symlink_to(elsewhere)
        with self.assertRaises(mod.InstallError):
            self.install()
        self.assertEqual(self.p["link"].resolve(), elsewhere.resolve())
        self.assertFalse(self.p["target"].exists())

    def test_update_and_uninstall_keep_external_guidance_and_profile(self):
        self.agents(b"Original guidance.\n")
        self.install()
        self.p["profile"].parent.mkdir(parents=True)
        self.p["profile"].write_text("Private preference.")
        self.p["override"].write_text("Temporary override.")
        text = self.p["agents"].read_text()
        self.p["agents"].write_text("New prefix.\n" + text + "New suffix.\n")
        (self.source / "references" / "rules.md").write_text("New official rules.\n")
        result = self.install()
        self.assertTrue(result["changed"])
        self.assertTrue(result["warnings"])
        updated = self.p["agents"].read_text()
        self.assertTrue(updated.startswith("New prefix.\nOriginal guidance.\n"))
        self.assertTrue(updated.endswith("New suffix.\n"))
        self.assertEqual(updated.count(mod.BEGIN), 1)
        mod.uninstall(self.home, self.codex)
        retained = self.p["agents"].read_text()
        self.assertIn("New prefix.\nOriginal guidance.\n", retained)
        self.assertIn("New suffix.\n", retained)
        self.assertNotIn(mod.BEGIN, retained)
        self.assertFalse(self.p["target"].exists())
        self.assertFalse(mod.exists(self.p["link"]))
        self.assertEqual(self.p["profile"].read_text(), "Private preference.")
        self.assertEqual(self.p["override"].read_text(), "Temporary override.")

    def test_modified_installation_blocks_update_and_uninstall(self):
        self.install()
        changed = self.p["target"] / "references" / "rules.md"
        changed.write_text("My local edits.\n")
        before = self.p["agents"].read_bytes()
        for operation in (self.install, lambda: mod.uninstall(self.home, self.codex)):
            with self.assertRaises(mod.InstallError):
                operation()
            self.assertEqual(changed.read_text(), "My local edits.\n")
            self.assertEqual(before, self.p["agents"].read_bytes())
        self.assertEqual(mod.status(self.home, self.codex)["state"], "conflict_or_modified")

    def test_added_file_blocks_deletion(self):
        self.install()
        extra = self.p["target"] / "private-notes.txt"
        extra.write_text("Do not delete.")
        with self.assertRaises(mod.InstallError):
            mod.uninstall(self.home, self.codex)
        self.assertEqual(extra.read_text(), "Do not delete.")

    def test_edited_managed_guidance_is_not_overwritten(self):
        self.install()
        text = self.p["agents"].read_text().replace("普通简短问答", "自定义普通简短问答")
        self.p["agents"].write_text(text)
        with self.assertRaises(mod.InstallError):
            self.install()
        with self.assertRaises(mod.InstallError):
            mod.uninstall(self.home, self.codex)
        self.assertEqual(text, self.p["agents"].read_text())

    def test_empty_original_and_absent_original_are_distinguished(self):
        self.agents(b"")
        self.install()
        mod.uninstall(self.home, self.codex)
        self.assertTrue(self.p["agents"].is_file())
        self.assertEqual(self.p["agents"].read_bytes(), b"")
        self.p["agents"].unlink()
        self.install()
        mod.uninstall(self.home, self.codex)
        self.assertFalse(self.p["agents"].exists())
        self.assertFalse(mod.uninstall(self.home, self.codex)["changed"])

    def test_no_trailing_newline_original_is_restored_exactly(self):
        self.agents("保留这段文字".encode())
        self.install()
        mod.uninstall(self.home, self.codex)
        self.assertEqual(self.p["agents"].read_bytes(), "保留这段文字".encode())

    def test_removed_block_is_not_recreated_on_uninstall(self):
        self.install()
        self.p["agents"].write_bytes(b"")
        mod.uninstall(self.home, self.codex)
        self.assertTrue(self.p["agents"].is_file())
        self.assertEqual(self.p["agents"].read_bytes(), b"")

    def test_source_symlink_is_rejected_before_install(self):
        (self.source / "private-link").symlink_to(self.root / "not-for-copying")
        with self.assertRaises(mod.InstallError):
            self.install()
        self.assertFalse(self.p["target"].exists())

    def test_duplicate_markers_are_rejected(self):
        self.install()
        self.p["agents"].write_text(self.p["agents"].read_text() + mod.BEGIN)
        with self.assertRaises(mod.InstallError):
            mod.uninstall(self.home, self.codex)
        self.assertTrue(self.p["target"].exists())

    def test_cli_custom_home_and_codex_home(self):
        custom = self.root / "codex-custom"
        env = dict(os.environ, CODEX_HOME=str(self.root / "must-not-use"))
        args = [sys.executable, str(SCRIPT), "--home", str(self.home), "install", "--codex-home", str(custom), "--source", str(self.source)]
        run = subprocess.run(args, capture_output=True, text=True, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(Path(json.loads(run.stdout)["target"]).resolve(), (custom / "skills" / mod.NAME).resolve())
        self.assertFalse((self.root / "must-not-use").exists())
        self.assertFalse(self.codex.exists())
        self.assertTrue((self.home / ".agents" / "skills" / mod.NAME).is_symlink())

    def test_explicit_home_ignores_ambient_codex_home(self):
        env = dict(os.environ, CODEX_HOME=str(self.root / "must-not-use"))
        run = subprocess.run([sys.executable, str(SCRIPT), "install", "--home", str(self.home), "--source", str(self.source)], capture_output=True, text=True, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(self.p["target"].is_dir())
        self.assertFalse((self.root / "must-not-use").exists())


if __name__ == "__main__":
    unittest.main()
