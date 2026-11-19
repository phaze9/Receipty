#!/bin/sh
set -eu

RECEIPTY_PROJECT="$HOME/Projects/Receipty"
if [ "$#" -eq 0 ]; then
    printf 'Usage: %s WORKSPACE [--port PORT]\n' "$0" >&2
    exit 2
fi

if [ -x "$RECEIPTY_PROJECT/.venv/bin/python" ]; then
    RECEIPTY_PYTHON="$RECEIPTY_PROJECT/.venv/bin/python"
elif [ -x "$RECEIPTY_PROJECT/venv/bin/python" ]; then
    RECEIPTY_PYTHON="$RECEIPTY_PROJECT/venv/bin/python"
elif [ -x "$HOME/venv/bin/python" ]; then
    RECEIPTY_PYTHON="$HOME/venv/bin/python"
else
    RECEIPTY_PYTHON=python3
fi

export PYTHONPATH="$RECEIPTY_PROJECT/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$RECEIPTY_PYTHON" -m receipty serve "$@"
