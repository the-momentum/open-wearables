#!/bin/bash
# Editable installs, so local changes to an extension apply without rebuilding the image.
# Production images have no extensions directory, which makes this a no-op.
set -e

EXTENSIONS_DIR="${EXTENSIONS_DIR:-/root_project/extensions}"

[ -d "$EXTENSIONS_DIR" ] || exit 0

python3 "$(dirname "$0")/uninstall_removed_extensions.py" "$EXTENSIONS_DIR" \
    || echo "Warning: could not check for removed extensions."

for dir in "$EXTENSIONS_DIR"/*/; do
    if [ -f "${dir}pyproject.toml" ]; then
        echo "Installing extension from ${dir}..."
        # --no-deps: extensions run on the core's dependency set.
        uv pip install --quiet --no-deps --editable "$dir" \
            || echo "Warning: could not install the extension in ${dir}, starting without it."
    fi
done
