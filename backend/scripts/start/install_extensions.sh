#!/bin/bash
# Install add-on modules checked out into the extensions directory (local development).
# Each subdirectory with a pyproject.toml is installed in editable mode, so code changes
# apply without rebuilding the image. Production images ship extensions preinstalled and
# have no such directory, which makes this a no-op.
set -e

EXTENSIONS_DIR="${EXTENSIONS_DIR:-/root_project/extensions}"

for dir in "$EXTENSIONS_DIR"/*/; do
    if [ -f "${dir}pyproject.toml" ]; then
        echo "Installing extension from ${dir}..."
        # --no-deps: extensions run on the core's dependency set.
        uv pip install --quiet --no-deps --editable "$dir"
    fi
done
