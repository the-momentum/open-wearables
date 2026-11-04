"""scripts/init_env.sh (`make init`), run on a copy of the repository's .env.example files."""

import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from dotenv import dotenv_values

from app.config import MIN_SECRET_KEY_LENGTH, Settings

_REPO_ROOT = Path(__file__).resolve().parents[3]

STRONG_KEY = "k" * MIN_SECRET_KEY_LENGTH


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for relative in ("scripts/init_env.sh", "backend/config/.env.example", "frontend/.env.example"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_REPO_ROOT / relative, target)
    return tmp_path


def _backend_env(repo: Path) -> Path:
    return repo / "backend" / "config" / ".env"


def _run(repo: Path) -> None:
    subprocess.run(["sh", str(repo / "scripts" / "init_env.sh")], capture_output=True, check=True)


def _secret_key(repo: Path) -> str | None:
    return dotenv_values(_backend_env(repo)).get("SECRET_KEY")


def test_creates_the_env_files_with_a_key_the_backend_accepts(repo: Path) -> None:
    _run(repo)

    assert (repo / "frontend" / ".env").exists()
    key = _secret_key(repo)
    assert key is not None
    assert Settings(secret_key=key).secret_key == key
    assert stat.S_IMODE(_backend_env(repo).stat().st_mode) == 0o600


def test_running_again_keeps_the_key(repo: Path) -> None:
    _run(repo)
    key = _secret_key(repo)

    _run(repo)

    assert _secret_key(repo) == key


@pytest.mark.parametrize(
    ("line", "replaced"), [("SECRET_KEY=secret-key-str", True), (f"SECRET_KEY={STRONG_KEY}", False)]
)
def test_replaces_only_the_old_default(repo: Path, line: str, replaced: bool) -> None:
    _backend_env(repo).write_text(f"{line}\nOTHER=1\n")

    _run(repo)

    assert (_secret_key(repo) != line.partition("=")[2]) is replaced
    assert dotenv_values(_backend_env(repo))["OTHER"] == "1"


def test_a_generated_key_leaves_the_env_readable_by_its_owner_only(repo: Path) -> None:
    _backend_env(repo).write_text("SECRET_KEY=\n")
    _backend_env(repo).chmod(0o644)

    _run(repo)

    assert stat.S_IMODE(_backend_env(repo).stat().st_mode) == 0o600
