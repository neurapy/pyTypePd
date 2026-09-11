#!/bin/sh
# Keep the entry point last so a piped download is parsed before installation starts.
set -eu

pytyped_fail() {
    printf '\n  pytyped: %s\n' "$*" >&2
    exit 1
}

pytyped_usage() {
    cat <<'USAGE'
Usage: install.sh [--yes] [DIRECTORY]

Clone pytyped and install the command in ~/.local/bin.
With no arguments, ask where to clone (default: ~/.local/share/pytyped).
Ask for your full name and email, using your Git identity as defaults.
Pass a directory to skip the location question, or --yes to accept all defaults.

Environment overrides:
  XDG_DATA_HOME          Parent of the default pytyped checkout
  PYTYPED_REPO_URL       Git URL (default: https://github.com/neurapy/pyTypePd.git)
  PYTYPED_BIN_DIR        Directory for the pytyped command (default: ~/.local/bin)
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

pytyped_install() {
    pytyped_destination=${XDG_DATA_HOME:-$HOME/.local/share}/pytyped
    pytyped_prompt=true
    pytyped_has_destination=false
    while [ $# -gt 0 ]; do
        case $1 in
            -h|--help) pytyped_usage; return ;;
            -y|--yes) pytyped_prompt=false ;;
            -*) pytyped_fail "Unknown option: $1. Use install.sh -h for help." ;;
            '') pytyped_fail 'The installation directory cannot be empty.' ;;
            *)
                [ "$pytyped_has_destination" = false ] || pytyped_fail 'Supply only one installation directory.'
                pytyped_destination=$1
                pytyped_has_destination=true
                ;;
        esac
        shift
    done

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
            pytyped_fail 'No terminal available. Use sh install.sh --yes [DIRECTORY] to accept defaults.'
        fi
        if [ "$pytyped_has_destination" = false ]; then
            printf '  Install directory [%s]: ' "$pytyped_destination"
            IFS= read -r pytyped_answer </dev/tty || pytyped_fail 'Installation cancelled.'
            pytyped_destination=${pytyped_answer:-$pytyped_destination}
        fi
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

    pytyped_config=$pytyped_destination/pytyped.conf
    [ ! -L "$pytyped_config" ] || pytyped_fail "The configuration is a symbolic link: $pytyped_config"
    if [ -e "$pytyped_config" ] && [ ! -f "$pytyped_config" ]; then
        pytyped_fail "The configuration is not a file: $pytyped_config"
    fi
    # Read defaults from the caller's Git context before cloning or changing directories.
    pytyped_name=$(git config --get user.name || true)
    pytyped_email=$(git config --get user.email || true)
    if [ -f "$pytyped_config" ]; then
        git config --file "$pytyped_config" --list >/dev/null || pytyped_fail "Invalid configuration: $pytyped_config"
        pytyped_name=$(git config --file "$pytyped_config" --get user.name || printf '%s' "$pytyped_name")
        pytyped_email=$(git config --file "$pytyped_config" --get user.email || printf '%s' "$pytyped_email")
    fi
    if [ "$pytyped_prompt" = true ]; then
        printf '  Full name [%s]: ' "$pytyped_name"
        IFS= read -r pytyped_answer </dev/tty || pytyped_fail 'Installation cancelled.'
        pytyped_name=${pytyped_answer:-$pytyped_name}
        printf '  Email [%s]: ' "$pytyped_email"
        IFS= read -r pytyped_answer </dev/tty || pytyped_fail 'Installation cancelled.'
        pytyped_email=${pytyped_answer:-$pytyped_email}
    fi

    pytyped_repository=${PYTYPED_REPO_URL:-https://github.com/neurapy/pyTypePd.git}
    pytyped_cloned=false
    if [ -e "$pytyped_destination/.git" ]; then
        pytyped_origin=$(git -C "$pytyped_destination" remote get-url origin)
        [ "$pytyped_origin" = "$pytyped_repository" ] || pytyped_fail "A checkout of another repository exists at $pytyped_destination."
        printf '\n  Using existing checkout: %s\n' "$pytyped_destination"
    else
        printf '\n  Cloning into %s...\n' "$pytyped_destination"
        git clone -- "$pytyped_repository" "$pytyped_destination"
        pytyped_cloned=true
    fi
    [ -x "$pytyped_launcher" ] && [ -f "$pytyped_destination/assets/generate.py" ] ||
        pytyped_fail "The checkout at $pytyped_destination does not contain the pytyped launcher and assets."

    git config --file "$pytyped_config" user.name "$pytyped_name"
    git config --file "$pytyped_config" user.email "$pytyped_email"

    # Record ownership inside the checkout so uninstall can preserve manual clones.
    if [ "$pytyped_cloned" = true ]; then
        git -C "$pytyped_destination" config --local pytyped.installRoot "$pytyped_destination"
    fi
    if ! git -C "$pytyped_destination" config --local --get-all pytyped.command | grep -Fqx -- "$pytyped_command"; then
        git -C "$pytyped_destination" config --local --add pytyped.command "$pytyped_command"
    fi

    if [ "$pytyped_replace_link" = true ]; then
        rm "$pytyped_command"
    fi
    if [ ! -L "$pytyped_command" ]; then
        ln -s "$pytyped_launcher" "$pytyped_command"
    fi

    printf '\n  Installed %s\n' "$pytyped_command"
    printf '  Configuration: %s\n' "$pytyped_config"
    case :${PATH:-}: in
        *:"$pytyped_bin":*) ;;
        *)
            # Print a safely quoted suggestion; never change shell startup files.
            pytyped_escaped_bin=$(printf '%s' "$pytyped_bin" | sed 's/[\\$`"]/\\&/g')
            printf '\n  %s is not on PATH. To use pytyped in this shell, run:\n\n' "$pytyped_bin"
            printf '    %s\n' "export PATH=\"$pytyped_escaped_bin:\$PATH\""
            ;;
    esac
    printf '\n  Get started: pytyped .\n  Help:        pytyped -h\n  Update:      pytyped --update\n  Uninstall:   pytyped --uninstall\n\n'
}

pytyped_install "$@"
