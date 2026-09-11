#!/bin/sh
# Keep the caller's working directory; resolve links without GNU-only readlink -f.
set -eu

pytyped_path=$0
while [ -L "$pytyped_path" ]; do
    pytyped_dir=$(CDPATH= cd -P "$(dirname "$pytyped_path")" && pwd)
    pytyped_link=$(readlink "$pytyped_path")
    case $pytyped_link in
        /*) pytyped_path=$pytyped_link ;;
        *) pytyped_path=$pytyped_dir/$pytyped_link ;;
    esac
done
pytyped_dir=$(CDPATH= cd -P "$(dirname "$pytyped_path")" && pwd)

if command -v python3 >/dev/null 2>&1 &&
    python3 -I -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    exec python3 -I "$pytyped_dir/assets/generate.py" "$@"
fi

if command -v uv >/dev/null 2>&1; then
    exec uv run --no-project --no-config --python '>=3.9' \
        python -I "$pytyped_dir/assets/generate.py" "$@"
fi

printf '%s\n' 'pytyped needs Python 3.9+ or uv. Install uv: https://docs.astral.sh/uv/getting-started/installation/' >&2
exit 1
