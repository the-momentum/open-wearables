import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "start" / "install_extensions.sh"

# Stands in for uv: records every call, prints $UV_PIP_LIST for `uv pip list` and fails to
# install any directory whose name contains "broken".
FAKE_UV = """#!/bin/bash
echo "$*" >> "$UV_LOG"
if [ "$1 $2" = "pip list" ]; then
    cat "$UV_PIP_LIST"
elif [ "$1 $2" = "pip install" ] && [[ "${@: -1}" == *broken* ]]; then
    echo "error: Failed to parse metadata" >&2
    exit 1
fi
"""


@dataclass
class ScriptRun:
    returncode: int
    stdout: str
    stderr: str
    uv_calls: list[str]


@pytest.fixture
def extensions_dir(tmp_path: Path) -> Path:
    return tmp_path / "extensions"


@pytest.fixture
def run_script(tmp_path: Path, extensions_dir: Path) -> Callable[..., ScriptRun]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "uv").write_text(FAKE_UV)
    (bin_dir / "uv").chmod(0o755)
    (bin_dir / "python3").symlink_to(sys.executable)
    log = tmp_path / "uv.log"
    pip_list = tmp_path / "pip-list.json"

    def run(editable: list[dict[str, str]] | None = None) -> ScriptRun:
        pip_list.write_text(json.dumps(editable or []))
        env = os.environ | {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "EXTENSIONS_DIR": str(extensions_dir),
            "UV_LOG": str(log),
            "UV_PIP_LIST": str(pip_list),
        }
        result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
        calls = log.read_text().splitlines() if log.exists() else []
        return ScriptRun(result.returncode, result.stdout, result.stderr, calls)

    return run


def _extension(extensions_dir: Path, name: str) -> None:
    path = extensions_dir / name
    path.mkdir(parents=True)
    (path / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')


def test_a_broken_extension_does_not_stop_startup_or_the_others(
    run_script: Callable[..., ScriptRun], extensions_dir: Path
) -> None:
    for name in ("alpha", "broken", "omega"):
        _extension(extensions_dir, name)

    run = run_script()

    assert run.returncode == 0, run.stderr
    installed = [Path(call.split()[-1]).name for call in run.uv_calls if call.startswith("pip install")]
    assert installed == ["alpha", "broken", "omega"]
    assert "Warning" in run.stdout


def test_an_extension_whose_directory_is_gone_is_uninstalled(
    run_script: Callable[..., ScriptRun], extensions_dir: Path
) -> None:
    _extension(extensions_dir, "present")

    run = run_script(
        editable=[
            {"name": "gone", "editable_project_location": str(extensions_dir / "gone")},
            {"name": "present", "editable_project_location": str(extensions_dir / "present")},
            {"name": "elsewhere", "editable_project_location": "/somewhere/else"},
        ]
    )

    assert run.returncode == 0, run.stderr
    assert [call for call in run.uv_calls if call.startswith("pip uninstall")] == ["pip uninstall --quiet gone"]


def test_no_extensions_directory_is_a_no_op(run_script: Callable[..., ScriptRun]) -> None:
    run = run_script()

    assert run.returncode == 0, run.stderr
    assert run.uv_calls == []
