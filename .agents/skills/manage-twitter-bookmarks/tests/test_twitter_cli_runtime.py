"""Check isolated-tool interpreter selection without executing or authenticating."""

import builtins
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
LOADERS = []
for name, loader_name in [
    ("download_twitter_bookmarks", "_load_twitter_cli"),
    ("clear_twitter_bookmarks", "load_twitter_cli"),
]:
    spec = importlib.util.spec_from_file_location("runtime_" + name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    LOADERS.append((module, loader_name))


class ExecRequested(Exception):
    pass


class TwitterRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.interpreter = root / "tool-venv" / "bin" / "python"
        self.interpreter.parent.mkdir(parents=True)
        self.interpreter.symlink_to(sys.executable)
        self.launcher = root / "twitter"
        self.launcher.write_text(f"#!{self.interpreter}\n")
        real_import = builtins.__import__

        def without_twitter(name, *args, **kwargs):
            if name == "twitter_cli" or name.startswith("twitter_cli."):
                raise ImportError("twitter-cli is only in the isolated tool environment")
            return real_import(name, *args, **kwargs)

        imports = patch("builtins.__import__", side_effect=without_twitter)
        imports.start()
        self.addCleanup(imports.stop)

    def test_tool_venv_symlink_is_used_even_with_the_same_base_python(self):
        self.assertEqual(self.interpreter.resolve(), Path(sys.executable).resolve())
        for module, loader_name in LOADERS:
            with self.subTest(script=module.__name__), \
                    patch.object(module.shutil, "which", return_value=str(self.launcher)), \
                    patch.object(module.os, "execve", side_effect=ExecRequested) as execute, \
                    patch.dict(os.environ, {module.REEXEC_GUARD: "0"}), \
                    patch.object(module.sys, "argv", [module.__file__, "--help"]):
                with self.assertRaises(ExecRequested):
                    getattr(module, loader_name)()
                self.assertEqual(execute.call_count, 1)
                executable, argv, environment = execute.call_args.args
                self.assertEqual(executable, str(self.interpreter))
                self.assertEqual(argv, [str(self.interpreter), str(Path(module.__file__).resolve()), "--help"])
                self.assertEqual(environment[module.REEXEC_GUARD], "1")

    def test_guard_prevents_repeated_reexecution(self):
        for module, loader_name in LOADERS:
            with self.subTest(script=module.__name__), \
                    patch.object(module.shutil, "which", return_value=str(self.launcher)), \
                    patch.object(module.os, "execve", side_effect=AssertionError("No real execution")) as execute, \
                    patch.dict(os.environ, {module.REEXEC_GUARD: "1"}):
                with self.assertRaises(RuntimeError):
                    getattr(module, loader_name)()
                execute.assert_not_called()

    def test_current_launch_path_does_not_reexecute(self):
        self.launcher.write_text(f"#!{sys.executable}\n")
        for module, loader_name in LOADERS:
            with self.subTest(script=module.__name__), \
                    patch.object(module.shutil, "which", return_value=str(self.launcher)), \
                    patch.object(module.os, "execve", side_effect=AssertionError("No real execution")) as execute, \
                    patch.dict(os.environ, {module.REEXEC_GUARD: "0"}):
                with self.assertRaises(RuntimeError):
                    getattr(module, loader_name)()
                execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
