"""Exercise installation, updates, and removal with disposable Git repositories."""

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
        self.config = self.base / "zsh settings" / ".zshrc"
        self.config.parent.mkdir()
        self.env = {
            **os.environ,
            "NO_COLOR": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "XDG_DATA_HOME": str(self.checkout.parent),
            "PYTYPED_REPO_URL": str(self.remote),
            "PYTYPED_BIN_DIR": str(self.bin),
            "SHELL": "/bin/zsh",
            "ZDOTDIR": str(self.config.parent),
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

    def maintenance(
        self,
        option: str,
        cwd: Path | None = None,
        launcher: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(launcher or self.bin / "pytyped"), option],
            cwd=cwd or self.base,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )

    def update(self, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return self.maintenance("--update", cwd=cwd)

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
        settings = "# Existing settings\nexport EXISTING_SETTING=keep\n"
        self.config.write_text(settings)
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        first = self.install("--yes")
        self.assert_installed(first)
        self.assert_installed(self.install("--yes"))
        self.assertEqual(self.config.read_text(), settings)
        self.assertNotIn("export PATH", first.stdout)
        self.assertNotIn("Added PATH", first.stdout)
        project = self.base / "new-project"
        project.mkdir()
        result = subprocess.run(
            ["pytyped", "--yes", "--python", "3.14"],
            cwd=project,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((project / ".python-version").read_text(), "3.14\n")

    def test_missing_path_prints_a_safely_quoted_instruction(self) -> None:
        self.bin = (
            self.base / 'bin $not_a_variable `touch EXECUTED` "quotes" \\ apostrophe\''
        )
        self.env["PYTYPED_BIN_DIR"] = str(self.bin)
        installed = self.install("--yes")
        self.assert_installed(installed)
        self.assertFalse(self.config.exists())
        self.assertIn("is not on PATH", installed.stdout)
        instruction = next(
            line.strip()
            for line in installed.stdout.splitlines()
            if line.strip().startswith("export PATH=")
        )
        for shell in ("bash", "zsh"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                result = subprocess.run(
                    [
                        shell,
                        "-f",
                        "-c",
                        instruction + "; command -v pytyped; pytyped -h",
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

    def test_install_does_not_create_shell_configuration(self) -> None:
        obsolete_override = self.base / "old shell override"
        self.env["PYTYPED_SHELL_CONFIG"] = str(obsolete_override)
        self.assert_installed(self.install("--yes"))
        self.assertFalse(self.config.exists())
        self.assertFalse(obsolete_override.exists())

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

    def test_uninstall_removes_installation_and_prints_reinstall_command(self) -> None:
        self.assert_installed(self.install("--yes"))
        self.assert_installed(self.install("--yes"))
        self.config.write_text("# My shell settings\n")
        other_command = self.bin / "keep"
        other_command.write_text("another tool")
        project = self.base / "my-project"
        project.mkdir()
        (project / "main.py").write_text("# My project\n")
        # The recorded command path works even without installation-time overrides.
        self.env.pop("PYTYPED_BIN_DIR")
        self.env.pop("XDG_DATA_HOME")
        result = self.maintenance("--uninstall", cwd=project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.bin / "pytyped").is_symlink())
        self.assertFalse(self.checkout.exists())
        self.assertEqual(other_command.read_text(), "another tool")
        self.assertEqual((project / "main.py").read_text(), "# My project\n")
        self.assertEqual(self.config.read_text(), "# My shell settings\n")
        self.assertTrue(
            result.stdout.rstrip().endswith(
                "wget -qO- https://raw.githubusercontent.com/neurapy/pyTypePd/main/install.sh | sh"
            )
        )

    def test_uninstall_from_inside_a_custom_checkout(self) -> None:
        checkout = self.base / "custom checkout"
        self.assert_installed(self.install(str(checkout)), checkout)
        result = self.maintenance("--uninstall", cwd=checkout / "assets")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(checkout.exists())
        self.assertFalse((self.bin / "pytyped").is_symlink())

    def test_uninstall_preserves_reused_and_older_checkouts(self) -> None:
        for checkout in (self.seed, self.checkout):
            with self.subTest(checkout=checkout):
                self.assert_installed(self.install(str(checkout)), checkout)
                if checkout == self.checkout:
                    # Older installers did not record ownership or command paths.
                    self.git(
                        checkout, "config", "--local", "--remove-section", "pytyped"
                    )
                original = (checkout / "pytyped.sh").read_bytes()
                result = self.maintenance("--uninstall")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Kept checkout", result.stdout)
                self.assertEqual((checkout / "pytyped.sh").read_bytes(), original)
                self.assertFalse((self.bin / "pytyped").is_symlink())

    def test_uninstall_preserves_local_files_including_ignored_files(self) -> None:
        self.assert_installed(self.install("--yes"))
        for filename in ("pytyped.sh", "untracked.txt", ".DS_Store"):
            with self.subTest(filename=filename):
                self.assert_installed(self.install("--yes"))
                path = self.checkout / filename
                original = path.read_text() if path.exists() else None
                changed = (original or "") + "\n# local change\n"
                path.write_text(changed)
                result = self.maintenance("--uninstall")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("local files or changes", result.stdout)
                self.assertEqual(path.read_text(), changed)
                self.assertFalse((self.bin / "pytyped").is_symlink())
                if original is None:
                    path.unlink()
                else:
                    path.write_text(original)

    def test_uninstall_preserves_local_commits_on_other_branches_and_stashes(
        self,
    ) -> None:
        self.assert_installed(self.install("--yes"))
        self.git(self.checkout, "checkout", "-b", "local-work")
        (self.checkout / "local.txt").write_text("Local commit\n")
        self.commit(self.checkout, "Local change")
        local_commit = self.git(self.checkout, "rev-parse", "HEAD")
        self.git(self.checkout, "checkout", "main")
        result = self.maintenance("--uninstall")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("local commits or stashes", result.stdout)
        self.assertEqual(
            self.git(self.checkout, "rev-parse", "local-work"), local_commit
        )
        self.assertFalse((self.bin / "pytyped").is_symlink())

        self.assert_installed(self.install("--yes"))
        self.git(self.checkout, "checkout", "local-work")
        (self.checkout / "local.txt").write_text("Stashed change\n")
        self.git(
            self.checkout,
            "-c",
            "user.name=Test Author",
            "-c",
            "user.email=test@example.org",
            "stash",
            "push",
            "-m",
            "Keep this stash",
        )
        self.git(self.checkout, "checkout", "main")
        self.git(self.checkout, "branch", "-D", "local-work")
        result = self.maintenance("--uninstall")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("local commits or stashes", result.stdout)
        self.assertIn("Keep this stash", self.git(self.checkout, "stash", "list"))

    def test_uninstall_preserves_linked_worktrees(self) -> None:
        self.assert_installed(self.install("--yes"))
        linked = self.base / "linked checkout"
        self.git(self.checkout, "worktree", "add", "-b", "linked", str(linked))
        result = self.maintenance("--uninstall")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("linked Git worktrees", result.stdout)
        self.assertTrue((self.checkout / "pytyped.sh").is_file())
        self.assertEqual(self.git(linked, "branch", "--show-current"), "linked")

    def test_uninstall_leaves_replaced_commands_untouched(self) -> None:
        for replacement in ("file", "link"):
            with self.subTest(replacement=replacement):
                self.assert_installed(self.install("--yes"))
                command = self.bin / "pytyped"
                command.unlink()
                if replacement == "file":
                    command.write_text("another tool")
                else:
                    command.symlink_to(self.base / "missing tool")
                result = self.maintenance(
                    "--uninstall", launcher=self.checkout / "pytyped.sh"
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(self.checkout.exists())
                if replacement == "file":
                    self.assertEqual(command.read_text(), "another tool")
                else:
                    self.assertEqual(command.readlink(), self.base / "missing tool")
                command.unlink()

    def test_uninstall_removes_links_in_all_recorded_command_directories(self) -> None:
        self.assert_installed(self.install("--yes"))
        old_command = self.bin / "pytyped"
        self.bin = self.base / "another bin"
        self.env["PYTYPED_BIN_DIR"] = str(self.bin)
        self.assert_installed(self.install("--yes"))
        result = self.maintenance("--uninstall")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(old_command.is_symlink())
        self.assertFalse((self.bin / "pytyped").is_symlink())
        self.assertFalse(self.checkout.exists())


if __name__ == "__main__":
    unittest.main()
