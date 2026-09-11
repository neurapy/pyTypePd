"""A dependency-free, interactive Python project generator."""

from __future__ import annotations

import argparse
import gzip
import json
import keyword
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "assets" / "structure" / "app-name"
RELEASES_URL = (
    "https://www.python.org/api/v2/downloads/release/"
    "?is_published=true&pre_release=false&version=3"
)
LICENSES = {
    "MIT": "MIT License",
    "Apache-2.0": "Apache License 2.0",
    "BSD-3-Clause": "BSD 3-Clause License",
    "GPL-3.0-only": "GNU General Public License v3.0",
    "MPL-2.0": "Mozilla Public License 2.0",
    "Unlicense": "The Unlicense",
    "none": "No license",
}
TOKENS = re.compile(r"__([a-z_]+)__")
MINIMUM_PYTHON = (3, 10)


class SetupError(Exception):
    """An actionable setup error, shown without a traceback."""


class Terminal:
    def __init__(self) -> None:
        self.color = (
            sys.stdout.isatty()
            and os.environ.get("TERM", "dumb") != "dumb"
            and "NO_COLOR" not in os.environ
        )

    def style(self, value: str, code: str) -> str:
        return f"\033[{code}m{value}\033[0m" if self.color else value

    def note(self, message: str) -> None:
        print(self.style(f"  {message}", "2"), flush=True)

    def ask(self, label: str, default: str, validate: Callable[[str], str]) -> str:
        suffix = f" [{default}]" if default else ""
        while True:
            value = input(self.style(f"  {label}{suffix}: ", "36")).strip() or default
            try:
                return validate(value)
            except ValueError as exc:
                print(self.style(f"  {exc}", "33"))


def project_name(value: str) -> str:
    """Normalize a project name and ensure its import name is usable."""
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ._-]*", value):
        raise ValueError(
            "Start with a letter; use letters, numbers, spaces, dots, - or _."
        )
    name = re.sub(r"[ ._-]+", "-", value).strip("-").lower()
    module = name.replace("-", "_")
    reserved = set(getattr(sys, "stdlib_module_names", ())) | {
        "logging",
        "typing",
        "unittest",
        "python",
        "python3",
        "pip",
        "pip3",
        "uv",
        "uvx",
        "pre_commit",
        "pytest",
        "pyright",
        "ruff",
        "taplo",
        "nodeenv",
        "nodejs_wheel_binaries",
        "uv_build",
    }
    if keyword.iskeyword(module) or module in reserved:
        raise ValueError(
            f"Choose another name: {module!r} is reserved by Python or a project tool."
        )
    if len(name) > 64:
        raise ValueError("Keep the project name to 64 characters or fewer.")
    return name


def license_id(value: str) -> str:
    choices = list(LICENSES)
    if value.isdigit() and 1 <= int(value) <= len(choices):
        return choices[int(value) - 1]
    for identifier in choices:
        if identifier.lower() == value.lower():
            return identifier
    raise ValueError(
        f"Choose 1-{len(choices)}, or enter a license identifier from the menu."
    )


def python_version(value: str) -> str:
    if not re.fullmatch(r"3\.(?:0|[1-9][0-9]*)", value):
        raise ValueError(
            "Enter a Python version such as 3.14 (major.minor, without a patch number)."
        )
    if version_key(value) < MINIMUM_PYTHON:
        raise ValueError("This template requires Python 3.10 or newer.")
    return value


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def fetch_releases() -> set[str]:
    """Find major/minor versions with a published final release."""
    request = urllib.request.Request(
        RELEASES_URL,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "pytyped",
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = response.read()
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)
    records = json.loads(payload)
    if not isinstance(records, list):
        raise ValueError("Unexpected Python release response.")
    releases = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        if (
            record.get("pre_release") is not False
            or record.get("is_published") is not True
        ):
            continue
        match = re.fullmatch(r"Python (3\.[0-9]+)\.[0-9]+", str(record.get("name", "")))
        if match and version_key(match[1]) >= MINIMUM_PYTHON:
            releases.add(match[1])
    if not releases:
        raise ValueError("No stable Python releases were returned.")
    return releases


def release_defaults(terminal: Terminal, offline: bool) -> tuple[str, set[str]]:
    releases: set[str] = set()
    if not offline:
        terminal.note("Looking up stable Python releases on python.org...")
        try:
            releases = fetch_releases()
        except (OSError, ValueError, urllib.error.URLError):
            terminal.note("Could not reach the Python release catalog.")
    if releases:
        return max(releases, key=version_key), releases
    if sys.version_info >= MINIMUM_PYTHON and sys.version_info.releaselevel == "final":
        local = ".".join(str(part) for part in sys.version_info[:2])
        terminal.note(
            f"Using installed Python {local} as the default; latest release not verified."
        )
        return local, releases
    terminal.note(
        "No default available. Enter a major/minor Python version (3.10 or newer)."
    )
    return "", releases


def validate_destination(destination: Path) -> None:
    if destination.exists():
        if not destination.is_dir():
            raise SetupError(f"Destination is not a directory: {destination}")
        existing = sorted(
            path.name
            for path in destination.iterdir()
            if path.name not in {".git", ".DS_Store"}
        )
        if existing:
            listing = ", ".join(existing[:5]) + (", ..." if len(existing) > 5 else "")
            raise SetupError(
                f"Use an empty directory (.git is fine). Existing files: {listing}"
            )
    else:
        parent = next(path for path in destination.parents if path.exists())
        if not parent.is_dir():
            raise SetupError(f"Destination parent is not a directory: {parent}")


def git_identity(destination: Path) -> tuple[str, str]:
    directory = (
        destination
        if destination.exists()
        else next(path for path in destination.parents if path.exists())
    )
    values = []
    for key in ("user.name", "user.email"):
        try:
            result = subprocess.run(
                ["git", "-C", str(directory), "config", "--get", key],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            values.append(result.stdout.strip() if result.returncode == 0 else "")
        except (OSError, subprocess.TimeoutExpired):
            values.append("")
    return values[0], values[1]


def render_project(
    name: str, license_name: str, version: str, author: str, email: str
) -> dict[Path, str]:
    module = name.replace("-", "_")
    author_metadata = ""
    if author:
        author_metadata = (
            f"\n\n[[project.authors]]\nname = {json.dumps(author, ensure_ascii=False)}"
        )
        if email:
            author_metadata += f"\nemail = {json.dumps(email, ensure_ascii=False)}"
    values = {
        "project_name": name,
        "package_name": module,
        "python_version": version,
        "python_minor": version,
        "ruff_target": "py" + version.replace(".", ""),
        "author_metadata": author_metadata,
        "license_metadata": (
            f'license = "{license_name}"\nlicense-files = ["LICENSE"]'
            if license_name != "none"
            else ""
        ),
        "license_readme": (
            f"[{LICENSES[license_name]}](LICENSE)."
            if license_name != "none"
            else "No license selected."
        ),
    }

    def substitute(match: re.Match[str]) -> str:
        # Preserve Python names such as __name__ and __main__.
        return values.get(match[1], match[0])

    if not TEMPLATE.is_dir():
        raise SetupError(
            f"Template not found: {TEMPLATE}. Keep the generator with its assets directory."
        )
    files = {}
    for source in sorted(TEMPLATE.rglob("*")):
        relative = source.relative_to(TEMPLATE)
        if {
            "__pycache__",
            ".venv",
            ".git",
            ".pytest_cache",
            ".ruff_cache",
        }.intersection(relative.parts):
            continue
        if (
            source.is_file()
            and source.suffix not in {".pyc", ".pyo"}
            and source.name != ".DS_Store"
        ):
            relative = Path(TOKENS.sub(substitute, relative.as_posix()))
            files[relative] = TOKENS.sub(substitute, source.read_text(encoding="utf-8"))
    if license_name != "none":
        license_text = (ROOT / "assets" / "licenses" / f"{license_name}.txt").read_text(
            encoding="utf-8"
        )
        copyright_values = {
            "year": str(datetime.now(timezone.utc).year),
            "copyright_holder": author or f"{name} contributors",
        }
        files[Path("LICENSE")] = TOKENS.sub(
            lambda match: copyright_values.get(match[1], match[0]),
            license_text,
        )
    return files


def write_project(destination: Path, files: dict[Path, str]) -> None:
    """Never replace a file, and roll back this run's files if a write fails."""
    validate_destination(destination)
    created_directories: list[Path] = []
    created_files: list[Path] = []

    def mkdir(directory: Path) -> None:
        if not directory.exists():
            mkdir(directory.parent)
            directory.mkdir()
            created_directories.append(directory)

    try:
        mkdir(destination)
        for relative, content in files.items():
            target = destination / relative
            mkdir(target.parent)
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                created_files.append(target)
                stream.write(content)
    except (OSError, KeyboardInterrupt):
        for path in reversed(created_files):
            path.unlink()
        for directory in reversed(created_directories):
            directory.rmdir()
        raise


def checkout_git(*arguments: str, missing_ok: bool = False) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SetupError("Git is required to manage the pytyped checkout.") from exc
    if missing_ok and result.returncode == 1:
        return ""
    if result.returncode:
        raise SetupError(
            result.stderr.strip() or "Could not read the pytyped Git checkout."
        )
    return result.stdout.strip()


def update_checkout(terminal: Terminal) -> None:
    """Update this checkout, independently of the caller's working directory."""
    if not (ROOT / ".git").exists():
        raise SetupError(
            "This copy is not a Git checkout. Install pytyped with install.sh."
        )

    if checkout_git("status", "--porcelain", "--untracked-files=all"):
        raise SetupError(
            f"The pytyped checkout has uncommitted changes: {ROOT}. "
            "Commit or stash them before running --update."
        )
    if not checkout_git("branch", "--show-current"):
        raise SetupError(
            "The pytyped checkout has a detached HEAD. Check out a branch before updating."
        )
    upstream = checkout_git(
        "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    before = checkout_git("rev-parse", "HEAD")
    terminal.note(f"Updating pytyped in {ROOT} from {upstream}...")
    result = subprocess.run(
        ["git", "-C", str(ROOT), "pull", "--ff-only", "--no-rebase", "--no-autostash"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode:
        raise SetupError(
            "Update failed. Resolve the Git error above and run pytyped --update again."
        )
    message = (
        "Already up to date."
        if checkout_git("rev-parse", "HEAD") == before
        else "pytyped updated."
    )
    print(terminal.style(f"\n  {message}\n", "32"))


def is_installed_checkout() -> bool:
    installed_root = checkout_git(
        "config", "--local", "--get", "pytyped.installRoot", missing_ok=True
    )
    if installed_root:
        return installed_root == str(ROOT)

    # Older installers left no marker. Recognize only the dedicated default path
    # and the expected repository; the caller still checks for local work.
    data_home = Path(
        os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    )
    repository = (
        os.environ.get("PYTYPED_REPO_URL") or "https://github.com/neurapy/pyTypePd.git"
    )
    return (
        ROOT == (data_home / "pytyped").expanduser().resolve()
        and checkout_git("remote", "get-url", "origin") == repository
    )


def uninstall_checkout(terminal: Terminal) -> None:
    """Remove our command links and an unchanged, installer-owned checkout."""
    directories = [
        str(Path.home() / ".local" / "bin"),
        os.environ.get("PYTYPED_BIN_DIR", ""),
        *os.environ.get("PATH", "").split(os.pathsep),
    ]
    commands = {Path(directory) / "pytyped" for directory in directories if directory}
    keep_reason = "it is not an installer-owned checkout"
    try:
        if (ROOT / ".git").exists():
            recorded = checkout_git(
                "config", "--local", "--get-all", "pytyped.command", missing_ok=True
            )
            commands.update(Path(path) for path in recorded.splitlines() if path)
            if (ROOT / ".git").is_dir() and is_installed_checkout():
                worktrees = checkout_git("worktree", "list", "--porcelain")
                if (
                    sum(line.startswith("worktree ") for line in worktrees.splitlines())
                    > 1
                ):
                    keep_reason = "it has linked Git worktrees"
                elif checkout_git(
                    "status", "--porcelain", "--untracked-files=all", "--ignored"
                ):
                    keep_reason = "it contains local files or changes"
                elif checkout_git(
                    "rev-list", "--max-count=1", "HEAD", "--all", "--not", "--remotes"
                ):
                    keep_reason = "it contains local commits or stashes"
                else:
                    keep_reason = ""
    except SetupError as exc:
        keep_reason = f"could not verify it is safe to remove: {exc}"

    removed_command = False
    for command in sorted(commands):
        # A command may have been replaced or redirected since installation.
        try:
            matches = command.is_symlink() and command.resolve() == ROOT / "pytyped.sh"
        except (OSError, RuntimeError):
            matches = False
        if matches:
            command.unlink()
            removed_command = True
            terminal.note(f"Removed command: {command}")

    if keep_reason:
        terminal.note(f"Kept checkout: {ROOT} ({keep_reason}).")
        message = (
            "pytyped command removed; checkout kept."
            if removed_command
            else "Nothing removed; checkout kept."
        )
    else:
        shutil.rmtree(ROOT)
        terminal.note(f"Removed checkout: {ROOT}")
        message = "pytyped uninstalled."
    print(terminal.style(f"\n  {message}", "32"))
    print("\n  Reinstall with:\n")
    print(
        "    wget -qO- https://raw.githubusercontent.com/neurapy/pyTypePd/main/install.sh | sh\n"
    )


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pytyped",
        description="Create a typed Python project. Omit options to answer three short questions.",
        epilog="Example: pytyped . --name navier-stokes-pinn --license MIT --python 3.14",
    )
    parser.add_argument(
        "destination",
        nargs="?",
        default=".",
        help="project directory (default: current directory)",
    )
    parser.add_argument("--name", help="project name (default: directory name)")
    parser.add_argument(
        "--license",
        dest="license_name",
        help="license identifier: " + ", ".join(LICENSES),
    )
    parser.add_argument(
        "--python", dest="python", help="major/minor Python version, e.g. 3.14"
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="accept defaults for unanswered questions",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="skip release lookup; default to the running Python version",
    )
    maintenance = parser.add_mutually_exclusive_group()
    maintenance.add_argument(
        "--update",
        action="store_true",
        help="update the pytyped Git checkout with a fast-forward pull",
    )
    maintenance.add_argument(
        "--uninstall",
        action="store_true",
        help="remove the pytyped command and its unchanged installer-owned checkout",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = argument_parser()
    options = parser.parse_args(argv)
    terminal = Terminal()
    try:
        if options.update or options.uninstall:
            action = "--update" if options.update else "--uninstall"
            if options.destination != "." or any(
                (
                    options.name is not None,
                    options.license_name is not None,
                    options.python is not None,
                    options.yes,
                    options.offline,
                )
            ):
                raise SetupError(f"Use {action} on its own.")
            if options.update:
                update_checkout(terminal)
            else:
                uninstall_checkout(terminal)
            return 0

        destination = Path(options.destination).expanduser().resolve()
        validate_destination(destination)
        print(terminal.style("\n  pytyped", "1;36"))
        terminal.note("A clean start for your next Python project.")
        terminal.note(f"Destination: {destination}\n")

        raw_name = options.name if options.name is not None else destination.name
        if options.name is not None or options.yes:
            name = project_name(raw_name)
        else:
            name = terminal.ask("1/3  Project name", raw_name, project_name)
        terminal.note(f"Project: {name}  |  Package: {name.replace('-', '_')}")

        if options.license_name is not None or options.yes:
            license_name = license_id(
                options.license_name if options.license_name is not None else "MIT"
            )
        else:
            print(terminal.style("\n  2/3  License\n", "1"))
            for index, (identifier, title) in enumerate(LICENSES.items(), 1):
                default = " (default)" if index == 1 else ""
                print(f"       {index}  {identifier:<14} {title}{default}")
            print()
            license_name = terminal.ask("Choose a license", "1", license_id)
        if options.python is not None:
            version = python_version(options.python)
        else:
            print()
            default_version, releases = release_defaults(terminal, options.offline)

            def validate_version(value: str) -> str:
                value = python_version(value)
                if releases and value not in releases:
                    raise ValueError(
                        f"Python {value} is not a published stable release. Choose another version."
                    )
                return value

            if options.yes:
                if not default_version:
                    raise SetupError(
                        "Could not determine a default Python version. Supply --python X.Y."
                    )
                version = validate_version(default_version)
            else:
                version = terminal.ask(
                    "3/3  Python version", default_version, validate_version
                )

        author, email = git_identity(destination)
        files = render_project(name, license_name, version, author, email)
        write_project(destination, files)
        print(terminal.style(f"\n  Created {name}", "1;32"))
        terminal.note(
            f"Python {version}  |  {LICENSES[license_name]}  |  {len(files)} files\n"
        )
        print("  Next steps:\n")
        if destination != Path.cwd().resolve():
            print(f"    cd {shlex.quote(str(destination))}")
        print("    git init\n    make install\n    make check\n")
        print("    # make necessary initial changes")
        print('    git add . && git commit -m "Initial Commit"\n')
        return 0
    except (EOFError, KeyboardInterrupt):
        if options.update:
            message = "Update cancelled."
        elif options.uninstall:
            message = "Uninstall interrupted. Some files may already have been removed."
        else:
            message = "Cancelled. No project was created."
        print(f"\n  {message}", file=sys.stderr)
        return 130
    except (SetupError, ValueError, OSError) as exc:
        print(f"\n  pytyped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
