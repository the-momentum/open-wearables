"""Uninstall extensions whose directory was removed since the container was created.

Their editable installs stay in the environment otherwise, and their entry points fail to load
on every start. Called by install_extensions.sh with the extensions directory.
"""

import json
import subprocess
import sys
from pathlib import Path


def removed_extensions(extensions_dir: Path) -> list[str]:
    listing = subprocess.run(
        ["uv", "pip", "list", "--editable", "--format", "json"], capture_output=True, text=True, check=True
    )
    root = extensions_dir.resolve()
    return [
        package["name"]
        for package in json.loads(listing.stdout)
        if root in Path(package.get("editable_project_location") or "/").resolve().parents
        and not (Path(package["editable_project_location"]) / "pyproject.toml").is_file()
    ]


def main() -> None:
    for name in removed_extensions(Path(sys.argv[1])):
        print(f"Uninstalling extension {name}, its directory is gone...", flush=True)
        if subprocess.run(["uv", "pip", "uninstall", "--quiet", name]).returncode != 0:
            print(f"Warning: could not uninstall extension {name}.", flush=True)


if __name__ == "__main__":
    main()
