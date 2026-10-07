#!/bin/bash
# Editable installs, so local changes to an extension apply without rebuilding the image.
# Production images have no extensions directory, which makes this a no-op.
set -e

EXTENSIONS_DIR="${EXTENSIONS_DIR:-/root_project/extensions}"

for dir in "$EXTENSIONS_DIR"/*/; do
    if [ -f "${dir}pyproject.toml" ]; then
        echo "Installing extension from ${dir}..."
        # --no-deps: extensions run on the core's dependency set.
        uv pip install --quiet --no-deps --editable "$dir"
    fi
done
