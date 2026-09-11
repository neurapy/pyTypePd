# pytyped

A small interactive generator for typed Python projects on macOS and Linux.
Choose a name, a license, and a Python version such as 3.14. Get a runnable, buildable
project with Ruff, strict Pyright, pytest, pre-commit, and uv already configured.

## Install

Run this from any directory:

```sh
wget -qO- https://raw.githubusercontent.com/neurapy/pyTypePd/main/install.sh | sh
```

Or use curl, available by default on macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/neurapy/pyTypePd/main/install.sh | sh
```

The installer asks where to clone the Git repository. Press Enter for
`~/.local/share/pytyped` (or `$XDG_DATA_HOME/pytyped` when set). It creates
`~/.local/bin/pytyped` and adds that directory to your shell configuration:
`.zshrc` for zsh, or `.bashrc` and the login profile for bash. Existing settings
are preserved. Open a new terminal afterward, or paste the printed PATH command
into your current shell.

The question reads from the terminal, so it also works when the script is piped
into `sh`. For unattended installation, supply a directory or accept the default:

```sh
curl -fsSL https://raw.githubusercontent.com/neurapy/pyTypePd/main/install.sh | sh -s -- "$HOME/tools/pytyped"
curl -fsSL https://raw.githubusercontent.com/neurapy/pyTypePd/main/install.sh | sh -s -- --yes
```

You can also run `sh install.sh` from a downloaded checkout. Installation needs
Git and either Python 3.9+ or [uv](https://docs.astral.sh/uv/getting-started/installation/).
Run `sh install.sh -h` for installer options, including overrides for the Git URL,
command directory, and shell configuration file.

Re-running the installer reuses an existing checkout of the same repository and
avoids duplicate configuration entries. It can migrate a symlink created by the
previous installer; unrelated commands and existing project files are preserved.

## Create a project

Keep this repository anywhere on your machine. The launcher needs Python 3.9+
or [uv](https://docs.astral.sh/uv/getting-started/installation/); it has no Python
package dependencies. When only uv is available, uv obtains a Python interpreter
to run the generator.

```sh
mkdir navier_stokes_pinn
cd navier_stokes_pinn
pytyped .
```

Omit `.` to use your current directory, or pass a new directory and pytyped will
create it, including missing parents. Running `/path/to/pyTypePd/pytyped.sh .`
directly from a checkout also works, including with a relative path.

```text
  pytyped
  A clean start for your next Python project.

  1/3  Project name [navier_stokes_pinn]:

  2/3  License

       1  MIT            MIT License (default)
       2  Apache-2.0     Apache License 2.0
       3  BSD-3-Clause   BSD 3-Clause License
       4  GPL-3.0-only   GNU General Public License v3.0
       5  MPL-2.0        Mozilla Public License 2.0
       6  Unlicense      The Unlicense
       7  none           No license

  Choose a license [1]:
  3/3  Python version [latest stable major/minor version]:
```

Press Enter to accept a default. Choose a license by number or identifier.
Invalid answers can be corrected in place; Ctrl-C or Ctrl-D cancels before any
project files are written. Color is used in terminals and respects `NO_COLOR`.

Then, with `uv` and `make` installed:

```sh
make install
make check
make run
```

`make install` downloads the selected Python version if necessary, creates `.venv`,
and installs the project and developer tools. To enable Git hooks, run `git init`
before `make install`. Commit `uv.lock` after the first install.
Use a current uv release so it knows about the latest Python downloads.

## Help and updates

```sh
pytyped -h
pytyped --update
```

`-h` (or `--help`) lists generator options. `--update` pulls the tracked branch
of pytyped's own Git checkout, regardless of your current directory. It requires
a clean checkout and uses a fast-forward pull, preserving local changes and
commits if an update cannot proceed. Generated projects are independent of the
generator checkout and keep their existing files.

Installation is handled by `install.sh`; there is no `pytyped --install` option.

## Defaults and options

- **Name:** defaults to the destination folder. Spaces, dots, hyphens, and
  underscores normalize to a lowercase project name such as `navier-stokes-pinn`,
  with the importable package `navier_stokes_pinn`. Start with a letter and keep
  the name to 64 characters or fewer. Python keywords and known conflicting module
  names are rejected.
- **License:** defaults to MIT. Full license texts are bundled locally.
  MIT/BSD copyright uses the destination's Git `user.name`, or `<project> contributors`
  when unset. Git author name and email also populate package metadata when
  available. Choosing `none` omits both the license file and license metadata.
- **Python:** defaults to the newest published stable release from
  [python.org's release catalog](https://www.python.org/downloads/), excluding
  prereleases. Enter a major/minor version such as `3.14`, at least 3.10. The wizard
  checks it against the release catalog when reachable. `.python-version` contains
  `3.14`, and `requires-python = "==3.14.*"` allows any patch in that series.
  Ruff and Pyright also target the selected major/minor version.
- **Offline:** `--offline` skips the release lookup. A failed lookup also falls
  back to the interpreter running the generator, clearly labeled as unverified.
  If that interpreter is older than 3.10 or a prerelease, enter a version manually.
  An explicit `--python` skips the catalog and validates the version's format;
  availability is checked by uv when installing.

Supply individual answers as flags to skip those questions, or all three for a
non-interactive run:

```sh
pytyped ./navier_stokes_pinn \
  --name navier-stokes-pinn \
  --license BSD-3-Clause \
  --python 3.14
```

`--yes` accepts the defaults for remaining answers. For example:

```sh
pytyped ./experiment --yes
pytyped ./experiment --yes --offline --python 3.13
pytyped --help
```

The destination must be empty, apart from an existing `.git` entry or `.DS_Store`.
Files are never overwritten, and interrupted or failed writes are rolled back.
Generation creates source and configuration files; dependency installation is
the separate `make install` step.

## Develop the generator

The standalone installer is `install.sh`, the portable launcher is `pytyped.sh`,
and the standard-library implementation is `assets/generate.py`.
Edit the template in `assets/structure/app-name/` and the
bundled texts in `assets/licenses/` to customize future projects.

Run the generator tests (Python 3.11+):

```sh
python3 -m unittest discover -s tests -v
```

To check the generated project as well, create a disposable project and run its
`make install`, `make check`, `make run`, and `make build` targets.
The GitHub Actions workflow runs the tests and this workflow on Linux and macOS.
Installation tests use temporary directories and local Git remotes, including
piped installation with a controlling terminal and fast-forward updates.
