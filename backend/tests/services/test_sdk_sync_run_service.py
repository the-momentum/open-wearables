from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.sdk_sync_run import SDKSyncChunk, SDKSyncRun
from app.services.sdk_sync_run_service import AcceptedSDKSyncChunk, sdk_sync_run_service


def test_manifest_models_match_migrated_table_names() -> None:
    assert SDKSyncRun.__tablename__ == "sdk_sync_run"
    assert SDKSyncChunk.__tablename__ == "sdk_sync_chunk"


def _accept(
    db: Session,
    *,
    user_id: str,
    sync_id: str,
    chunk_index: int,
    item_count: int,
    sleep_item_count: int = 0,
    is_final: bool = False,
    total_items: int | None = None,
    payload: bytes | None = None,
) -> AcceptedSDKSyncChunk:
    return sdk_sync_run_service.accept_chunk(
        db,
        user_id=user_id,
        provider="apple",
        client_sync_id=sync_id,
        chunk_index=chunk_index,
        is_final=is_final,
        declared_total_items=total_items,
        item_count=item_count,
        sleep_item_count=sleep_item_count,
        payload=payload or f"chunk-{chunk_index}".encode(),
        batch_id=str(uuid4()),
    )


def test_completion_requires_every_chunk_and_matching_item_count(db: Session) -> None:
    user_id = str(uuid4())
    sync_id = str(uuid4())
    first = _accept(
        db,
        user_id=user_id,
        sync_id=sync_id,
        chunk_index=0,
        item_count=2,
    )
    duplicate = _accept(
        db,
        user_id=user_id,
        sync_id=sync_id,
        chunk_index=0,
        item_count=2,
    )
    assert duplicate.duplicate is True
    assert duplicate.batch_id == first.batch_id

    run, should_emit_started = sdk_sync_run_service.mark_started(db, batch_id=first.batch_id)
    assert should_emit_started is True
    _, should_emit_started_again = sdk_sync_run_service.mark_started(db, batch_id=first.batch_id)
    assert should_emit_started_again is False
    assert run.client_sync_id == sync_id

    run, is_terminal, mismatch = sdk_sync_run_service.mark_processed(
        db,
        batch_id=first.batch_id,
        processed_items=2,
    )
    assert is_terminal is False
    assert mismatch is False
    assert run.status == "accepting"

    final = _accept(
        db,
        user_id=user_id,
        sync_id=sync_id,
        chunk_index=1,
        item_count=0,
        is_final=True,
        total_items=2,
    )
    run, is_terminal, mismatch = sdk_sync_run_service.mark_processed(
        db,
        batch_id=final.batch_id,
        processed_items=0,
    )

    assert is_terminal is True
    assert mismatch is False
    assert run.status == "completed"
    assert run.expected_chunks == 2
    assert run.received_chunks == 2
    assert run.processed_chunks == 2
    assert run.received_items == 2
    assert run.processed_items == 2


def test_manifest_tracks_sleep_items_across_chunks(db: Session) -> None:
    user_id = str(uuid4())
    sync_id = str(uuid4())
    first = _accept(
        db,
        user_id=user_id,
        sync_id=sync_id,
        chunk_index=0,
        item_count=3,
        sleep_item_count=2,
    )
    final = _accept(
        db,
        user_id=user_id,
        sync_id=sync_id,
        chunk_index=1,
        item_count=0,
        is_final=True,
        total_items=3,
    )

    sdk_sync_run_service.mark_processed(db, batch_id=first.batch_id, processed_items=3)
    run, is_terminal, mismatch = sdk_sync_run_service.mark_processed(
        db,
        batch_id=final.batch_id,
        processed_items=0,
    )

    assert is_terminal is True
    assert mismatch is False
    assert run.received_sleep_items == 2


def test_final_marker_fails_closed_on_count_mismatch(db: Session) -> None:
    user_id = str(uuid4())
    sync_id = str(uuid4())
    data = _accept(
        db,
        user_id=user_id,
        sync_id=sync_id,
        chunk_index=0,
        item_count=3,
    )
    sdk_sync_run_service.mark_processed(db, batch_id=data.batch_id, processed_items=2)
    final = _accept(
        db,
        user_id=user_id,
        sync_id=sync_id,
        chunk_index=1,
        item_count=0,
        is_final=True,
        total_items=3,
    )

    run, is_terminal, mismatch = sdk_sync_run_service.mark_processed(
        db,
        batch_id=final.batch_id,
        processed_items=0,
    )

    assert is_terminal is True
    assert mismatch is True
    assert run.status == "failed"


def test_chunk_index_cannot_be_reused_with_different_payload(db: Session) -> None:
    user_id = str(uuid4())
    sync_id = str(uuid4())
    _accept(
        db,
        user_id=user_id,
        sync_id=sync_id,
        chunk_index=0,
        item_count=1,
        payload=b"first",
    )

    with pytest.raises(ValueError, match="different content"):
        _accept(
            db,
            user_id=user_id,
            sync_id=sync_id,
            chunk_index=0,
            item_count=1,
            payload=b"changed",
        )


def test_chunk_index_cannot_change_manifest_headers_on_retry(db: Session) -> None:
    user_id = str(uuid4())
    sync_id = str(uuid4())
    _accept(
        db,
        user_id=user_id,
        sync_id=sync_id,
        chunk_index=0,
        item_count=0,
        payload=b"same-body",
    )

    with pytest.raises(ValueError, match="different content"):
        _accept(
            db,
            user_id=user_id,
            sync_id=sync_id,
            chunk_index=0,
            item_count=0,
            is_final=True,
            total_items=0,
            payload=b"same-body",
        )
