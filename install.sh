#!/bin/sh
# Keep the entry point last so a piped download is parsed before installation starts.
set -eu

pytyped_fail() {
    printf '\n  pytyped: %s\n' "$*" >&2
    exit 1
}

pytyped_usage() {
    cat <<'USAGE'
Usage: install.sh [DIRECTORY | --yes]

Clone pytyped and install the command in ~/.local/bin.
With no arguments, ask where to clone (default: ~/.local/share/pytyped).
Pass a directory to skip the question, or --yes to use the default.

Environment overrides:
  XDG_DATA_HOME          Parent of the default pytyped checkout
  PYTYPED_REPO_URL       Git URL (default: https://github.com/neurapy/pyTypePd.git)
  PYTYPED_BIN_DIR        Directory for the pytyped command (default: ~/.local/bin)
  PYTYPED_SHELL_CONFIG   POSIX shell startup file to configure instead of auto-detection
USAGE
}

pytyped_absolute_path() {
    case $1 in
        \~) printf '%s\n' "$HOME" ;;
        \~/*) printf '%s/%s\n' "$HOME" "${1#\~/}" ;;
        /*) printf '%s\n' "$1" ;;
        *) printf '%s/%s\n' "$PWD" "$1" ;;
    esac
}

pytyped_add_path() {
    if [ -e "$1" ] && [ ! -f "$1" ]; then
        pytyped_fail "Shell configuration is not a file: $1"
    fi
    if [ ! -f "$1" ] || ! grep -Fqx "$pytyped_path_line" "$1"; then
        mkdir -p "$(dirname "$1")"
        printf '\n# pytyped\n%s\n' "$pytyped_path_line" >> "$1"
        printf '  Added PATH to %s\n' "$1"
    fi
}

pytyped_install() {
    pytyped_destination=${XDG_DATA_HOME:-$HOME/.local/share}/pytyped
    pytyped_prompt=true
    case $# in
        0) ;;
        1)
            case $1 in
                -h|--help) pytyped_usage; return ;;
                -y|--yes) pytyped_prompt=false ;;
                -*) pytyped_fail "Unknown option: $1. Use install.sh -h for help." ;;
                '') pytyped_fail 'The installation directory cannot be empty.' ;;
                *) pytyped_destination=$1; pytyped_prompt=false ;;
            esac
            ;;
        *) pytyped_fail 'Supply one installation directory, or use install.sh -h for help.' ;;
    esac

    command -v git >/dev/null 2>&1 || pytyped_fail 'Git is required. Install Git and run this installer again.'
    if ! command -v uv >/dev/null 2>&1; then
        if ! command -v python3 >/dev/null 2>&1 ||
            ! python3 -I -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
            pytyped_fail 'Python 3.9+ or uv is required. Install uv: https://docs.astral.sh/uv/getting-started/installation/'
        fi
    fi

    printf '\n  pytyped\n  Install once. Start projects anywhere.\n\n'
    if [ "$pytyped_prompt" = true ]; then
        # stdin contains this script when invoked with wget/curl | sh.
        if ! ( : </dev/tty ) 2>/dev/null; then
            pytyped_fail 'No terminal available. Pass a directory: sh install.sh /path/to/pytyped (or --yes).'
        fi
        printf '  Install directory [%s]: ' "$pytyped_destination"
        IFS= read -r pytyped_answer </dev/tty || pytyped_fail 'Installation cancelled.'
        pytyped_destination=${pytyped_answer:-$pytyped_destination}
    fi

    pytyped_destination=$(pytyped_absolute_path "$pytyped_destination")
    pytyped_bin=$(pytyped_absolute_path "${PYTYPED_BIN_DIR:-$HOME/.local/bin}")
    # Colons separate PATH entries; line breaks cannot be represented in a prompt.
    case "$pytyped_destination$pytyped_bin" in
        *:*) pytyped_fail 'Choose paths without colons.' ;;
        *'
'*) pytyped_fail 'Choose paths without line breaks.' ;;
    esac
    while [ "$pytyped_destination" != / ] && [ "${pytyped_destination%/}" != "$pytyped_destination" ]; do
        pytyped_destination=${pytyped_destination%/}
    done
    [ ! -L "$pytyped_destination" ] || pytyped_fail "The installation directory is a symbolic link: $pytyped_destination"
    mkdir -p "$(dirname "$pytyped_destination")" "$pytyped_bin"
    pytyped_parent=$(CDPATH='' cd -P "$(dirname "$pytyped_destination")" && pwd)
    pytyped_destination=$pytyped_parent/$(basename "$pytyped_destination")
    pytyped_bin=$(CDPATH='' cd -P "$pytyped_bin" && pwd)
    pytyped_command=$pytyped_bin/pytyped
    pytyped_launcher=$pytyped_destination/pytyped.sh
    pytyped_replace_link=false

    if [ -L "$pytyped_command" ]; then
        if [ "$(readlink "$pytyped_command")" != "$pytyped_launcher" ]; then
            # Migrate links made by the earlier installer, leaving that checkout intact.
            if [ -f "$pytyped_command" ] && grep -Fq "\$pytyped_dir/assets/generate.py" "$pytyped_command"; then
                pytyped_replace_link=true
            else
                pytyped_fail "A different command already exists at $pytyped_command; it has been left untouched."
            fi
        fi
    elif [ -e "$pytyped_command" ]; then
        pytyped_fail "A command already exists at $pytyped_command; it has been left untouched."
    fi

    pytyped_repository=${PYTYPED_REPO_URL:-https://github.com/neurapy/pyTypePd.git}
    if [ -e "$pytyped_destination/.git" ]; then
        pytyped_origin=$(git -C "$pytyped_destination" remote get-url origin)
        [ "$pytyped_origin" = "$pytyped_repository" ] || pytyped_fail "A checkout of another repository exists at $pytyped_destination."
        printf '\n  Using existing checkout: %s\n' "$pytyped_destination"
    else
        printf '\n  Cloning into %s...\n' "$pytyped_destination"
        git clone -- "$pytyped_repository" "$pytyped_destination"
    fi
    [ -x "$pytyped_launcher" ] && [ -f "$pytyped_destination/assets/generate.py" ] ||
        pytyped_fail "The checkout at $pytyped_destination does not contain the pytyped launcher and assets."

    if [ "$pytyped_replace_link" = true ]; then
        rm "$pytyped_command"
    fi
    if [ ! -L "$pytyped_command" ]; then
        ln -s "$pytyped_launcher" "$pytyped_command"
    fi

    # Escape literal path characters for a double-quoted shell assignment; never eval input.
    pytyped_escaped_bin=$(printf '%s' "$pytyped_bin" | sed 's/[\\$`"]/\\&/g')
    pytyped_path_line="export PATH=\"$pytyped_escaped_bin:\$PATH\""
    if [ -n "${PYTYPED_SHELL_CONFIG:-}" ]; then
        pytyped_add_path "$(pytyped_absolute_path "$PYTYPED_SHELL_CONFIG")"
    else
        case ${SHELL:-/bin/sh} in
            */zsh)
                pytyped_add_path "${ZDOTDIR:-$HOME}/.zshrc"
                ;;
            */bash)
                pytyped_add_path "$HOME/.bashrc"
                # Bash login shells read the first existing file from this list.
                pytyped_login_file=$HOME/.profile
                for pytyped_candidate in "$HOME/.bash_profile" "$HOME/.bash_login" "$HOME/.profile"; do
                    if [ -f "$pytyped_candidate" ]; then
                        pytyped_login_file=$pytyped_candidate
                        break
                    fi
                done
                pytyped_add_path "$pytyped_login_file"
                ;;
            *) pytyped_add_path "$HOME/.profile" ;;
        esac
    fi

    printf '\n  Installed %s\n' "$pytyped_command"
    printf '\n  Open a new terminal, or run this in your current shell:\n\n    %s\n' "$pytyped_path_line"
    printf '\n  Get started: pytyped .\n  Help:        pytyped -h\n  Update:      pytyped --update\n\n'
}

pytyped_install "$@"
