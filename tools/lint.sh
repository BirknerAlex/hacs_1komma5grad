#!/bin/bash
# Reproduces the type-checking warnings shown in editors (basedpyright)
# plus ruff's lint checks, so they can be seen and triaged outside the editor.
set -euo pipefail

cd "$(dirname "$0")/.."

VENV=.venv13

if [ -x "$VENV/bin/python" ]; then
  PIP="$VENV/bin/pip"
  PYTHON="$VENV/bin/python"
  RUFF="$VENV/bin/ruff"
  BASEDPYRIGHT="$VENV/bin/basedpyright"
else
  # No local venv (e.g. CI, where dependencies are installed system-wide).
  PIP="pip"
  PYTHON="python"
  RUFF="ruff"
  BASEDPYRIGHT="basedpyright"
fi

if ! command -v "$RUFF" >/dev/null 2>&1; then
  echo "Installing ruff..."
  "$PIP" install ruff
fi

if ! command -v "$BASEDPYRIGHT" >/dev/null 2>&1; then
  echo "Installing basedpyright..."
  "$PIP" install basedpyright
fi

echo "==> ruff check"
"$RUFF" check .

echo
echo "==> basedpyright custom_components/einskomma5grad"
# --pythonpath points basedpyright at the venv's interpreter so it resolves
# homeassistant/etc. the same way the editor's configured interpreter does.
"$BASEDPYRIGHT" --pythonpath "$PYTHON" custom_components/einskomma5grad
