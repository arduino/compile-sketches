#!/bin/sh

# Set up the Python environment for the action's script to run in

# https://stackoverflow.com/a/29835459
SCRIPT_PATH="$(
  CDPATH='' \
  cd -- "$(
    dirname -- "$0"
  )" && (
    pwd -P
  )
)"
readonly SCRIPT_PATH

readonly PYTHON_VENV_PATH="${SCRIPT_PATH}/compilesketches/.venv"
readonly PYTHON_VENV_ACTIVATE_SCRIPT_PATH="${PYTHON_VENV_PATH}/bin/activate"

# Create Python virtual environment
python -m venv --system-site-packages "$PYTHON_VENV_PATH"

# Activate Python virtual environment
# shellcheck source=/dev/null
. "$PYTHON_VENV_ACTIVATE_SCRIPT_PATH"

# Install Python dependencies
python -m pip install --upgrade pip > /dev/null
python -m pip install --quiet --requirement "${SCRIPT_PATH}/compilesketches/requirements.txt"

# Set outputs for use in GitHub Actions workflow steps
# See: https://docs.github.com/en/free-pro-team@latest/actions/reference/workflow-commands-for-github-actions#setting-an-output-parameter
echo "::set-output name=python-venv-activate-script-path::$PYTHON_VENV_ACTIVATE_SCRIPT_PATH"
