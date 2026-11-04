"""Tests for scripts/init_env.sh (`make init`).

The script runs in a copy of the repository layout under tmp_path, with the real
.env.example files, so the tests cover what a developer gets on a fresh checkout.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from dotenv import dotenv_values

from app.config import MIN_SECRET_KEY_LENGTH, PUBLISHED_SECRET_VALUES, Settings

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


def _run(repo: Path, env: dict[str, str] | None = None, check: bool = True) -> str:
    result = subprocess.run(
        ["sh", str(repo / "scripts" / "init_env.sh")],
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, **(env or {})},
    )
    return result.stdout


def _secret_key(repo: Path) -> str | None:
    return dotenv_values(_backend_env(repo)).get("SECRET_KEY")


def _write_backend_env(repo: Path, content: str) -> None:
    _backend_env(repo).write_bytes(content.encode())


class TestFreshCheckout:
    def test_creates_both_env_files(self, repo: Path) -> None:
        _run(repo)

        assert _backend_env(repo).is_file()
        assert (repo / "frontend" / ".env").is_file()

    def test_generates_a_secret_key_the_backend_accepts(self, repo: Path) -> None:
        _run(repo)

        key = _secret_key(repo)
        assert key is not None
        assert Settings(secret_key=key).secret_key == key

    def test_backend_env_is_readable_by_its_owner_only(self, repo: Path) -> None:
        _run(repo)

        assert stat.S_IMODE(_backend_env(repo).stat().st_mode) == 0o600

    def test_running_again_changes_nothing(self, repo: Path) -> None:
        _run(repo)
        first = _backend_env(repo).read_bytes()

        output = _run(repo)

        assert _backend_env(repo).read_bytes() == first
        assert "Kept     SECRET_KEY" in output


class TestExistingEnv:
    @pytest.mark.parametrize("published", sorted(PUBLISHED_SECRET_VALUES["secret_key"]))
    def test_replaces_every_value_the_backend_refuses_as_published(self, repo: Path, published: str) -> None:
        _write_backend_env(repo, f"SECRET_KEY={published}\n")

        output = _run(repo)

        assert _secret_key(repo) not in (None, published)
        assert "Replaced SECRET_KEY (it was a published default)" in output
        assert "signs everyone out" in output
        assert "make run" in output

    def test_replaces_a_key_shorter_than_the_backend_accepts(self, repo: Path) -> None:
        _write_backend_env(repo, f"SECRET_KEY={'k' * (MIN_SECRET_KEY_LENGTH - 1)}\n")

        output = _run(repo)

        assert len(_secret_key(repo) or "") >= MIN_SECRET_KEY_LENGTH
        assert f"shorter than {MIN_SECRET_KEY_LENGTH} characters" in output

    def test_keeps_a_strong_key(self, repo: Path) -> None:
        _write_backend_env(repo, f"SECRET_KEY={STRONG_KEY}\n")

        _run(repo)

        assert _secret_key(repo) == STRONG_KEY

    @pytest.mark.parametrize(
        "line",
        [
            f"SECRET_KEY = {STRONG_KEY}\n",
            f"export SECRET_KEY={STRONG_KEY}\n",
            f"SECRET_KEY='{STRONG_KEY}'  # mine\n",
        ],
        ids=["spaces", "export", "single-quoted-with-comment"],
    )
    def test_keeps_a_strong_key_however_it_is_written(self, repo: Path, line: str) -> None:
        _write_backend_env(repo, line)

        output = _run(repo)

        assert _backend_env(repo).read_text() == line
        assert "Kept     SECRET_KEY" in output

    def test_reads_a_quoted_key_up_to_its_closing_quote(self, repo: Path) -> None:
        """Inside quotes " #" is part of the key, not a comment, so the key is long enough."""
        key = "k" * 20 + " #" + "k" * 20
        line = f'SECRET_KEY="{key}"\n'
        _write_backend_env(repo, line)

        _run(repo)

        assert _secret_key(repo) == key

    @pytest.mark.parametrize(
        "line",
        [
            'SECRET_KEY="secret-key-str"  # old default\n',
            "SECRET_KEY=secret-key-str\r\n",
            "SECRET_KEY = secret-key-str\n",
            "export SECRET_KEY=secret-key-str\n",
        ],
        ids=["quoted-with-comment", "crlf", "spaces", "export"],
    )
    def test_recognises_the_published_default_however_it_is_written(self, repo: Path, line: str) -> None:
        _write_backend_env(repo, f"OTHER=1\r\n{line}")

        _run(repo)

        assert _secret_key(repo) != "secret-key-str"
        assert dotenv_values(_backend_env(repo)).get("OTHER") == "1"

    def test_judges_the_last_occurrence_and_leaves_one_line(self, repo: Path) -> None:
        """python-dotenv uses the last occurrence, so the script must judge that one."""
        _write_backend_env(repo, f"SECRET_KEY={STRONG_KEY}\nSECRET_KEY=secret-key-str\n")

        _run(repo)

        lines = [line for line in _backend_env(repo).read_text().splitlines() if line.startswith("SECRET_KEY")]
        assert len(lines) == 1
        assert _secret_key(repo) not in (STRONG_KEY, "secret-key-str")

    def test_keeps_an_existing_file_mode(self, repo: Path) -> None:
        _write_backend_env(repo, "SECRET_KEY=secret-key-str\n")
        _backend_env(repo).chmod(0o640)

        _run(repo)

        assert stat.S_IMODE(_backend_env(repo).stat().st_mode) == 0o640

    def test_keeps_a_key_that_references_another_variable(self, repo: Path) -> None:
        """python-dotenv expands ${VAR}; the literal text is short, the key the backend gets is not."""
        content = f"MY_KEY={STRONG_KEY}\nSECRET_KEY=${{MY_KEY}}\n"
        _write_backend_env(repo, content)

        output = _run(repo)

        assert _backend_env(repo).read_text() == content
        assert "not checked" in output
        assert _secret_key(repo) == STRONG_KEY

    @pytest.mark.skipif(os.geteuid() == 0, reason="root can write a read-only file")
    def test_failed_write_leaves_no_copy_of_the_env_behind(self, repo: Path) -> None:
        """The temporary copy holds every secret in .env."""
        _write_backend_env(repo, "SECRET_KEY=secret-key-str\nPROVIDER_SECRET=keep-me-private\n")
        _backend_env(repo).chmod(0o400)
        tmpdir = repo / "tmp"
        tmpdir.mkdir()

        _run(repo, env={"TMPDIR": str(tmpdir)}, check=False)

        assert list(tmpdir.iterdir()) == []
        assert _secret_key(repo) == "secret-key-str"
