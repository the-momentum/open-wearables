"""
Tests for process_xml_upload Celery task.

Tests how the task stores the uploaded XML before importing it.
"""

import os
import tempfile
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.integrations.celery.tasks.process_xml_upload_task import process_xml_upload
from app.schemas.providers.apple.apple_xml import XMLParseStats

_TASK = "app.integrations.celery.tasks.process_xml_upload_task"


@dataclass
class FakeImport:
    """Stands in for the XML import, recording each temp file it was given."""

    files: list[tuple[str, bytes]] = field(default_factory=list)
    error: Exception | None = None

    def __call__(self, _db: Session, xml_path: str, _user_id: str) -> XMLParseStats:
        self.files.append((xml_path, Path(xml_path).read_bytes()))
        if self.error is not None:
            raise self.error
        return XMLParseStats()


@pytest.fixture
def fake_import(db: Session) -> Generator[FakeImport, None, None]:
    fake = FakeImport()
    with (
        patch(f"{_TASK}.SessionLocal") as mock_session_local,
        patch(f"{_TASK}._import_xml_data", side_effect=fake),
        patch(f"{_TASK}.emit_sync_started"),
        patch(f"{_TASK}.emit_sync_completed"),
        patch(f"{_TASK}.emit_sync_failed"),
        patch(f"{_TASK}.try_record_data_types"),
    ):
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        yield fake


class TestProcessXMLUploadTempFile:
    def test_uploads_with_the_same_filename_get_separate_files(self, fake_import: FakeImport) -> None:
        process_xml_upload(file_contents=b"<A/>", filename="export.xml", user_id=str(uuid4()))
        process_xml_upload(file_contents=b"<B/>", filename="export.xml", user_id=str(uuid4()))

        (path_a, content_a), (path_b, content_b) = fake_import.files
        assert path_a != path_b
        assert (content_a, content_b) == (b"<A/>", b"<B/>")

    def test_temp_file_name_ignores_client_filename_and_is_removed(self, fake_import: FakeImport) -> None:
        process_xml_upload(file_contents=b"<A/>", filename="../../evil.xml", user_id=str(uuid4()))

        ((path, _),) = fake_import.files
        assert os.path.dirname(path) == tempfile.gettempdir()
        assert "evil" not in os.path.basename(path)
        assert not os.path.exists(path)

    def test_temp_file_is_removed_when_import_fails(self, fake_import: FakeImport) -> None:
        fake_import.error = RuntimeError("parse failed")

        with pytest.raises(RuntimeError, match="parse failed"):
            process_xml_upload(file_contents=b"<A/>", filename="export.xml", user_id=str(uuid4()))

        ((path, _),) = fake_import.files
        assert not os.path.exists(path)
