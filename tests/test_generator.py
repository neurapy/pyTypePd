"""Exercise the wizard, portable launcher, generated projects, and file safety."""

from __future__ import annotations

import contextlib
import gzip
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "pytyped.sh"
SPEC = importlib.util.spec_from_file_location(
    "generate", ROOT / "assets" / "generate.py"
)
assert SPEC is not None and SPEC.loader is not None
generate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate)


class GeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="pytyped-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.project = self.base / "Navier Stokes PINN"
        self.env = {**os.environ, "NO_COLOR": "1"}
        # Avoid depending on, or copying, the developer's Git identity.
        self.env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})

    def launch(
        self,
        *arguments: str,
        cwd: Path | None = None,
        answers: str = "",
        launcher: Path = LAUNCHER,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(launcher), *arguments],
            cwd=cwd or self.base,
            env=self.env,
            input=answers,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )

    def assert_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("\033[", result.stdout)

    def test_no_arguments_asks_three_questions_in_order(self) -> None:
        self.project.mkdir()
        result = self.launch("--offline", cwd=self.project, answers="\n2\n3.12\n")
        self.assert_success(result)
        self.assertLess(result.stdout.index("1/3"), result.stdout.index("2/3"))
        self.assertLess(result.stdout.index("2/3"), result.stdout.index("3/3"))
        metadata = tomllib.loads((self.project / "pyproject.toml").read_text())
        self.assertEqual(metadata["project"]["name"], "navier-stokes-pinn")
        self.assertEqual(metadata["project"]["license"], "Apache-2.0")
        self.assertEqual((self.project / ".python-version").read_text(), "3.12\n")
        self.assertNotIn("authors", metadata["project"])

    def test_relative_launcher_and_dot_destination(self) -> None:
        self.project.mkdir()
        relative_launcher = Path(os.path.relpath(LAUNCHER, self.project))
        result = self.launch(
            ".",
            "--yes",
            "--python",
            "3.13",
            cwd=self.project,
            launcher=relative_launcher,
        )
        self.assert_success(result)
        self.assertTrue((self.project / "src/navier_stokes_pinn/py.typed").is_file())

    def test_invalid_interactive_answers_can_be_corrected(self) -> None:
        result = self.launch(
            str(self.project),
            "--offline",
            answers="../escape\nFluid Solver\n99\nbsd-3-clause\n3.12.3\n3.12\n",
        )
        self.assert_success(result)
        self.assertIn("Start with a letter", result.stdout)
        self.assertIn("Choose 1-7", result.stdout)
        self.assertIn("major.minor, without a patch number", result.stdout)
        self.assertTrue((self.project / "src/fluid_solver/main.py").is_file())

    def test_all_licenses_generate_consistent_metadata_and_complete_text(self) -> None:
        for identifier in generate.LICENSES:
            with self.subTest(license=identifier):
                project = self.base / identifier
                result = self.launch(
                    str(project),
                    "--name",
                    "Fluid Solver",
                    "--license",
                    identifier,
                    "--python",
                    "3.13",
                )
                self.assert_success(result)
                metadata = tomllib.loads((project / "pyproject.toml").read_text())
                self.assertEqual(metadata["project"]["requires-python"], "==3.13.*")
                self.assertEqual(
                    metadata["project"]["scripts"],
                    {"fluid-solver": "fluid_solver.main:main"},
                )
                self.assertEqual(metadata["tool"]["ruff"]["target-version"], "py313")
                self.assertEqual(metadata["tool"]["pyright"]["pythonVersion"], "3.13")
                self.assertEqual(
                    metadata["tool"]["ruff"]["lint"]["isort"]["known-first-party"],
                    ["fluid_solver"],
                )
                if identifier == "none":
                    self.assertFalse((project / "LICENSE").exists())
                    self.assertNotIn("license", metadata["project"])
                    self.assertNotIn("license-files", metadata["project"])
                else:
                    self.assertEqual(metadata["project"]["license"], identifier)
                    self.assertEqual(metadata["project"]["license-files"], ["LICENSE"])
                    text = (project / "LICENSE").read_text()
                    self.assertGreater(len(text), 1000)
                    self.assertNotIn("__copyright_holder__", text)
                    self.assertNotIn("__year__", text)
                    if identifier in {"MIT", "BSD-3-Clause"}:
                        self.assertIn("fluid-solver contributors", text)
                for path in project.rglob("*.py"):
                    compile(path.read_text(), str(path), "exec")

    def test_generated_module_runs(self) -> None:
        result = self.launch(str(self.project), "--yes", "--python", "3.13")
        self.assert_success(result)
        run = subprocess.run(
            [sys.executable, "-m", "navier_stokes_pinn"],
            cwd=self.project / "src",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("Hello from navier-stokes-pinn!", run.stderr)

    def test_existing_files_are_untouched(self) -> None:
        self.project.mkdir()
        sentinel = self.project / "README.md"
        sentinel.write_text("My existing project\n")
        result = self.launch(str(self.project), "--yes", "--python", "3.13")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty directory", result.stderr)
        self.assertEqual(sentinel.read_text(), "My existing project\n")
        self.assertEqual(list(self.project.iterdir()), [sentinel])

    def test_existing_git_directory_is_preserved(self) -> None:
        git_dir = self.project / ".git"
        git_dir.mkdir(parents=True)
        (git_dir / "keep").write_text("sentinel")
        result = self.launch(str(self.project), "--yes", "--python", "3.13")
        self.assert_success(result)
        self.assertEqual((git_dir / "keep").read_text(), "sentinel")

    def test_eof_cancels_without_creating_directories(self) -> None:
        result = self.launch(str(self.project))
        self.assertEqual(result.returncode, 130)
        self.assertIn("Cancelled", result.stderr)
        self.assertFalse(self.project.exists())

    def test_invalid_flags_fail_without_writing(self) -> None:
        for option, value in [
            ("--name", "../escape"),
            ("--name", "class"),
            ("--name", "logging"),
            ("--license", "made-up"),
            ("--python", "3.14.7"),
            ("--python", "3"),
            ("--python", "3.9"),
            ("--python", "3.15.0rc1"),
        ]:
            with self.subTest(option=option, value=value):
                arguments = {
                    "--name": "fluid-solver",
                    "--license": "MIT",
                    "--python": "3.13",
                }
                arguments[option] = value
                result = self.launch(
                    str(self.project),
                    *(part for pair in arguments.items() for part in pair),
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(self.project.exists())

    def test_nested_destination_is_created(self) -> None:
        target = self.base / "missing parent" / "deeper" / "solver"
        self.assert_success(self.launch(str(target), "--yes", "--python", "3.13"))
        self.assertTrue((target / "pyproject.toml").is_file())

    def test_destination_file_or_invalid_parent_has_a_clean_error(self) -> None:
        self.project.write_text("sentinel")
        for target in (self.project, self.project / "child"):
            result = self.launch(str(target), "--yes", "--python", "3.13")
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.project.read_text(), "sentinel")

    def test_quoted_git_identity_produces_valid_toml(self) -> None:
        files = generate.render_project(
            "fluid-solver", "MIT", "3.13", 'A "quoted" \\ author', "a@example.org"
        )
        metadata = tomllib.loads(files[Path("pyproject.toml")])
        self.assertEqual(
            metadata["project"]["authors"],
            [{"name": 'A "quoted" \\ author', "email": "a@example.org"}],
        )
        self.assertIn('A "quoted" \\ author', files[Path("LICENSE")])

    def test_help_lists_update_and_no_install_command(self) -> None:
        result = self.launch("-h")
        self.assert_success(result)
        self.assertIn("--update", result.stdout)
        self.assertIn("--uninstall", result.stdout)
        self.assertNotIn("--install", result.stdout)
        self.assertFalse(self.project.exists())
        self.assertEqual(self.launch("--install").returncode, 2)

    def test_maintenance_options_cannot_be_combined_with_generation(self) -> None:
        for option in ("--update", "--uninstall"):
            for arguments in ((str(self.project),), ("--yes",), ("--python", "3.14")):
                with self.subTest(option=option, arguments=arguments):
                    result = self.launch(option, *arguments)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(f"Use {option} on its own", result.stderr)
                    self.assertFalse(self.project.exists())
        self.assertEqual(self.launch("--update", "--uninstall").returncode, 2)

    def test_launcher_handles_spaces_and_relative_symlink_chains(self) -> None:
        checkout = self.base / "generator checkout"
        checkout.mkdir()
        shutil.copy2(LAUNCHER, checkout / "pytyped.sh")
        shutil.copytree(
            ROOT / "assets",
            checkout / "assets",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (self.base / "first link").symlink_to("generator checkout/pytyped.sh")
        (self.base / "second link").symlink_to("first link")
        result = self.launch(
            str(self.project),
            "--yes",
            "--python",
            "3.13",
            launcher=self.base / "second link",
        )
        self.assert_success(result)
        self.assertTrue((self.project / "pyproject.toml").is_file())

    def test_failed_write_rolls_back_only_created_files(self) -> None:
        git_dir = self.project / ".git"
        git_dir.mkdir(parents=True)
        sentinel = git_dir / "keep"
        sentinel.write_text("sentinel")
        original_open = Path.open

        def failing_open(path: Path, *args: object, **kwargs: object) -> object:
            if path.name == "second.txt":
                raise OSError("simulated full disk")
            return original_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", failing_open):
            with self.assertRaisesRegex(OSError, "full disk"):
                generate.write_project(
                    self.project,
                    {
                        Path("new/first.txt"): "first",
                        Path("new/second.txt"): "second",
                    },
                )
        self.assertEqual(list(self.project.iterdir()), [git_dir])
        self.assertEqual(sentinel.read_text(), "sentinel")

    def test_live_catalog_defaults_to_highest_stable_version(self) -> None:
        stdout = io.StringIO()
        with (
            mock.patch.object(
                generate,
                "fetch_releases",
                return_value={"3.14", "3.10", "3.13"},
            ),
            mock.patch.object(generate, "git_identity", return_value=("", "")),
            mock.patch(
                "builtins.input", side_effect=["Fluid Solver", "", ""]
            ) as prompts,
            contextlib.redirect_stdout(stdout),
        ):
            result = generate.main([str(self.project)])
        self.assertEqual(result, 0, stdout.getvalue())
        self.assertIn("[3.14]", prompts.call_args_list[-1].args[0])
        self.assertEqual((self.project / ".python-version").read_text(), "3.14\n")

    def test_catalog_filters_unpublished_and_prerelease_records(self) -> None:
        records = [
            {"name": "Python 3.14.7", "is_published": True, "pre_release": False},
            {"name": "Python 3.14.6", "is_published": True, "pre_release": False},
            {"name": "Python 3.10.0", "is_published": True, "pre_release": False},
            {"name": "Python 3.15.0rc1", "is_published": True, "pre_release": True},
            {"name": "Python 3.15.0", "is_published": False, "pre_release": False},
            {"name": "Python 3.16.0", "is_published": True, "pre_release": True},
            {"name": "Python 3.9.25", "is_published": True, "pre_release": False},
        ]
        for compressed in (False, True):
            payload = json.dumps(records).encode()
            if compressed:
                payload = gzip.compress(payload)
            with mock.patch.object(
                generate.urllib.request, "urlopen", return_value=io.BytesIO(payload)
            ):
                self.assertEqual(generate.fetch_releases(), {"3.14", "3.10"})

    def test_offline_and_failed_lookup_use_an_explicitly_labeled_local_default(
        self,
    ) -> None:
        for offline in (False, True):
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    generate,
                    "fetch_releases",
                    side_effect=urllib.error.URLError("offline"),
                ) as fetch,
                contextlib.redirect_stdout(stdout),
            ):
                version, releases = generate.release_defaults(
                    generate.Terminal(), offline
                )
            self.assertEqual(
                version, ".".join(str(part) for part in sys.version_info[:2])
            )
            self.assertFalse(releases)
            self.assertIn("latest release not verified", stdout.getvalue())
            self.assertEqual(fetch.call_count, 0 if offline else 1)

    def test_ctrl_c_during_prompt_creates_nothing(self) -> None:
        with (
            mock.patch("builtins.input", side_effect=KeyboardInterrupt),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = generate.main([str(self.project)])
        self.assertEqual(result, 130)
        self.assertFalse(self.project.exists())


if __name__ == "__main__":
    unittest.main()
