"""Exercise installation and updates using real, disposable Git repositories."""

from __future__ import annotations

import errno
import os
import pty
import select
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "install.sh"


class InstallationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="pytyped-install-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.seed = self.base / "source"
        self.remote = self.base / "origin.git"
        self.checkout = self.base / "data" / "pytyped"
        self.bin = self.base / "local bin"
        self.config = self.base / "shell config"
        self.env = {
            **os.environ,
            "NO_COLOR": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "XDG_DATA_HOME": str(self.checkout.parent),
            "PYTYPED_REPO_URL": str(self.remote),
            "PYTYPED_BIN_DIR": str(self.bin),
            "PYTYPED_SHELL_CONFIG": str(self.config),
        }
        self.seed.mkdir()
        for filename in ("pytyped.sh", "install.sh", ".gitignore"):
            shutil.copy2(ROOT / filename, self.seed / filename)
        shutil.copytree(
            ROOT / "assets",
            self.seed / "assets",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.git(self.seed, "init", "-q", "-b", "main")
        self.commit(self.seed, "Initial generator")
        self.git(self.base, "clone", "--bare", str(self.seed), str(self.remote))
        self.git(self.seed, "remote", "add", "origin", str(self.remote))

    def git(self, directory: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(directory), *arguments],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def commit(self, directory: Path, message: str) -> None:
        self.git(directory, "add", ".")
        self.git(
            directory,
            "-c",
            "user.name=Test Author",
            "-c",
            "user.email=test@example.org",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            message,
        )

    def install(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        # Feed the script over stdin, as wget/curl | sh does.
        return subprocess.run(
            ["sh", "-s", "--", *arguments],
            input=INSTALLER.read_text(),
            cwd=self.base,
            env=self.env,
            start_new_session=True,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )

    def assert_installed(
        self, result: subprocess.CompletedProcess[str], checkout: Path | None = None
    ) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        checkout = checkout or self.checkout
        self.assertTrue((checkout / ".git").is_dir())
        self.assertEqual((self.bin / "pytyped").resolve(), checkout / "pytyped.sh")

    def update(self, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.bin / "pytyped"), "--update"],
            cwd=cwd or self.base,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )

    def publish_update(self) -> str:
        (self.seed / "release-note.txt").write_text("New template release\n")
        self.commit(self.seed, "Update template")
        self.git(self.seed, "push", "origin", "main")
        return self.git(self.seed, "rev-parse", "HEAD")

    def interactive_install(self, answer: str) -> subprocess.CompletedProcess[str]:
        # A controlling terminal is distinct from stdin, which carries the shell script.
        pid, descriptor = pty.fork()
        if pid == 0:
            os.chdir(self.base)
            os.execve(
                "/bin/sh",
                ["sh", "-c", 'cat "$1" | sh', "installer-test", str(INSTALLER)],
                self.env,
            )
        output = bytearray()
        answered = False
        deadline = time.monotonic() + 15
        try:
            while time.monotonic() < deadline:
                if not select.select([descriptor], [], [], 0.1)[0]:
                    continue
                try:
                    chunk = os.read(descriptor, 65536)
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
                if not chunk:
                    break
                output.extend(chunk)
                if b"Install directory [" in output and not answered:
                    os.write(descriptor, (answer + "\n").encode())
                    answered = True
            else:
                self.fail(
                    "Installer did not finish: " + output.decode(errors="replace")
                )
            _, status = os.waitpid(pid, 0)
            pid = 0
            return subprocess.CompletedProcess(
                [], os.waitstatus_to_exitcode(status), output.decode(), ""
            )
        finally:
            os.close(descriptor)
            if pid:
                os.killpg(pid, signal.SIGKILL)
                os.waitpid(pid, 0)

    def test_piped_installer_prompts_through_terminal_and_accepts_default(self) -> None:
        result = self.interactive_install("")
        self.assert_installed(result)
        self.assertIn(f"Install directory [{self.checkout}]", result.stdout)

    def test_piped_installer_accepts_custom_directory_with_spaces(self) -> None:
        target = self.base / "custom checkout"
        result = self.interactive_install(str(target))
        self.assert_installed(result, target)

    def test_no_terminal_requires_a_directory_or_yes(self) -> None:
        result = self.install()
        self.assertEqual(result.returncode, 1)
        self.assertIn("No terminal available", result.stderr)
        self.assertFalse(self.checkout.exists())

    def test_install_is_repeatable_and_preserves_shell_configuration(self) -> None:
        self.config.write_text("# Existing settings\nexport EXISTING_SETTING=keep\n")
        self.assert_installed(self.install("--yes"))
        self.assert_installed(self.install("--yes"))
        text = self.config.read_text()
        self.assertTrue(
            text.startswith("# Existing settings\nexport EXISTING_SETTING=keep\n")
        )
        self.assertEqual(text.count("# pytyped\n"), 1)
        project = self.base / "new-project"
        project.mkdir()
        result = subprocess.run(
            [
                "bash",
                "--noprofile",
                "--norc",
                "-c",
                '. "$1"; pytyped --yes --python 3.14',
                "installer-test",
                str(self.config),
            ],
            cwd=project,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((project / ".python-version").read_text(), "3.14\n")

    def test_paths_are_quoted_when_shell_config_is_sourced(self) -> None:
        self.bin = (
            self.base / 'bin $not_a_variable `touch EXECUTED` "quotes" \\ apostrophe\''
        )
        self.env["PYTYPED_BIN_DIR"] = str(self.bin)
        self.assert_installed(self.install("--yes"))
        for shell in ("bash", "zsh"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                result = subprocess.run(
                    [
                        shell,
                        "-f",
                        "-c",
                        '. "$1"; command -v pytyped; pytyped -h',
                        "installer-test",
                        str(self.config),
                    ],
                    cwd=self.base,
                    env=self.env,
                    text=True,
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(str(self.bin / "pytyped"), result.stdout)
                self.assertIn("--update", result.stdout)
                self.assertFalse((self.base / "EXECUTED").exists())

    def test_zsh_configuration_respects_zdotdir(self) -> None:
        self.env.pop("PYTYPED_SHELL_CONFIG")
        self.env["SHELL"] = "/bin/zsh"
        self.env["ZDOTDIR"] = str(self.base / "zsh settings")
        self.assert_installed(self.install("--yes"))
        config = Path(self.env["ZDOTDIR"]) / ".zshrc"
        self.assertIn(str(self.bin), config.read_text())

    def test_existing_command_or_broken_link_is_preserved(self) -> None:
        self.bin.mkdir()
        command = self.bin / "pytyped"
        command.write_text("existing command")
        self.assertEqual(self.install("--yes").returncode, 1)
        self.assertEqual(command.read_text(), "existing command")
        command.unlink()
        command.symlink_to("missing")
        self.assertEqual(self.install("--yes").returncode, 1)
        self.assertEqual(command.readlink(), Path("missing"))
        self.assertFalse(self.checkout.exists())

    def test_old_pytyped_link_is_migrated_without_changing_old_checkout(self) -> None:
        self.bin.mkdir()
        old_launcher = self.seed / "pytyped.sh"
        original = old_launcher.read_bytes()
        (self.bin / "pytyped").symlink_to(old_launcher)
        self.assert_installed(self.install("--yes"))
        self.assertEqual(old_launcher.read_bytes(), original)

    def test_existing_directory_and_other_repository_are_preserved(self) -> None:
        self.checkout.mkdir(parents=True)
        marker = self.checkout / "keep"
        marker.write_text("sentinel")
        self.assertNotEqual(self.install("--yes").returncode, 0)
        self.assertEqual(marker.read_text(), "sentinel")
        self.git(self.checkout, "init", "-q")
        self.git(
            self.checkout, "remote", "add", "origin", str(self.base / "different.git")
        )
        result = self.install("--yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another repository", result.stderr)
        self.assertEqual(marker.read_text(), "sentinel")

    def test_update_fast_forwards_the_installation_and_leaves_caller_repo_unchanged(
        self,
    ) -> None:
        self.assert_installed(self.install("--yes"))
        caller = self.base / "caller-project"
        self.git(self.base, "clone", str(self.remote), str(caller))
        before = self.git(caller, "rev-parse", "HEAD")
        after = self.publish_update()
        result = self.update(caller)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git(self.checkout, "rev-parse", "HEAD"), after)
        self.assertEqual(self.git(caller, "rev-parse", "HEAD"), before)
        self.assertTrue((self.checkout / "release-note.txt").is_file())
        self.assertIn("Already up to date", self.update().stdout)

    def test_update_preserves_tracked_and_untracked_changes(self) -> None:
        self.assert_installed(self.install("--yes"))
        before = self.git(self.checkout, "rev-parse", "HEAD")
        self.publish_update()
        for filename in ("pytyped.sh", "untracked.txt"):
            with self.subTest(filename=filename):
                path = self.checkout / filename
                original = path.read_text() if path.exists() else None
                path.write_text((original or "") + "\n# local change\n")
                result = self.update()
                self.assertEqual(result.returncode, 1)
                self.assertIn("uncommitted changes", result.stderr)
                self.assertIn("# local change", path.read_text())
                self.assertEqual(self.git(self.checkout, "rev-parse", "HEAD"), before)
                if original is None:
                    path.unlink()
                else:
                    path.write_text(original)

    def test_update_refuses_diverged_history_without_merging_or_rebasing(self) -> None:
        self.assert_installed(self.install("--yes"))
        (self.checkout / "local.txt").write_text("Local commit\n")
        self.commit(self.checkout, "Local change")
        before = self.git(self.checkout, "rev-parse", "HEAD")
        self.git(self.checkout, "config", "pull.rebase", "true")
        self.publish_update()
        result = self.update()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Update failed", result.stderr)
        self.assertEqual(self.git(self.checkout, "rev-parse", "HEAD"), before)
        self.assertEqual(self.git(self.checkout, "status", "--porcelain"), "")

    def test_update_handles_detached_head_and_missing_upstream(self) -> None:
        self.assert_installed(self.install("--yes"))
        self.git(self.checkout, "checkout", "--detach")
        self.assertIn("detached HEAD", self.update().stderr)
        self.git(self.checkout, "checkout", "main")
        self.git(self.checkout, "branch", "--unset-upstream")
        result = self.update()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
