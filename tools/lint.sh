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
  # Resolve to an absolute path: basedpyright's --pythonpath does its own
  # environment/site-packages discovery from the given path and doesn't
  # reliably fall back to a PATH lookup for a bare command name.
  PIP="pip"
  PYTHON="$(command -v python3 || command -v python)"
  RUFF="ruff"
  BASEDPYRIGHT="basedpyright"
fi

# Always install/upgrade to the latest release, not just "some version is
# present". ruff-action@v1 in CI always installs latest ruff with no
# version pin, and a stale local ruff/basedpyright can have a different
# default rule set (e.g. ruff added DTZ005/BLE001/I001/PIE810 to its
# defaults between 0.15 and 0.16), silently passing here while CI fails.
echo "Installing/upgrading ruff and basedpyright..."
"$PIP" install -q -U ruff basedpyright

echo "==> ruff check"
"$RUFF" check .

echo
echo "==> basedpyright custom_components/einskomma5grad tests"
# --pythonpath points basedpyright at the venv's interpreter so it resolves
# homeassistant/etc. the same way the editor's configured interpreter does.
"$BASEDPYRIGHT" --pythonpath "$PYTHON" custom_components/einskomma5grad tests
