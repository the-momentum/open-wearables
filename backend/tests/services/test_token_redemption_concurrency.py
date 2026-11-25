"""Single-use credentials stay single-use when the same one is sent concurrently.

The regular `db` fixture keeps a test on one connection, so it cannot show a race.
These tests commit their data and redeem it from separate sessions in parallel threads.
"""

import threading
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from app.models import Developer, RefreshToken, User
from app.models.user_invitation_code import UserInvitationCode
from app.schemas.auth import SDKTokenOrigin
from app.services.refresh_token_service import refresh_token_service
from app.services.user_invitation_code_service import user_invitation_code_service
from app.utils.exceptions import AppError

CONCURRENT_REQUESTS = 8


@dataclass
class Owners:
    user_id: UUID
    developer_id: UUID


@pytest.fixture
def owners(session_factory: Any) -> Generator[Owners, None, None]:
    """Commit a user and a developer for real, and remove everything they own afterwards."""
    owners = Owners(user_id=uuid4(), developer_id=uuid4())
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        session.add(User(id=owners.user_id, created_at=now, email=f"{owners.user_id}@example.com"))
        session.add(
            Developer(
                id=owners.developer_id,
                created_at=now,
                updated_at=now,
                email=f"{owners.developer_id}@example.com",
                hashed_password="hashed_test_password",
            )
        )
        session.commit()

    yield owners

    with session_factory() as session:
        session.execute(
            delete(RefreshToken).where(
                or_(
                    RefreshToken.user_id == owners.user_id,
                    RefreshToken.developer_id == owners.developer_id,
                    RefreshToken.issued_by_developer_id == owners.developer_id,
                )
            )
        )
        session.execute(delete(UserInvitationCode).where(UserInvitationCode.user_id == owners.user_id))
        session.execute(delete(User).where(User.id == owners.user_id))
        session.execute(delete(Developer).where(Developer.id == owners.developer_id))
        session.commit()


def _run_concurrently(session_factory: Any, call: Callable[[Session], object]) -> list[object]:
    """Run `call` from CONCURRENT_REQUESTS threads at once, each with its own session."""
    barrier = threading.Barrier(CONCURRENT_REQUESTS, timeout=10)

    def worker() -> object:
        with session_factory() as session:
            session.connection()  # connect up front, as a pooled server connection would be
            barrier.wait()
            try:
                return call(session)
            except AppError as exc:
                return exc

    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
        futures = [pool.submit(worker) for _ in range(CONCURRENT_REQUESTS)]
        return [future.result() for future in futures]


def test_concurrent_redeems_of_one_invitation_code_issue_tokens_once(session_factory: Any, owners: Owners) -> None:
    with session_factory() as session:
        generated = user_invitation_code_service.generate(session, owners.user_id, owners.developer_id)

    results = _run_concurrently(session_factory, lambda s: user_invitation_code_service.redeem(s, generated.code))

    failures = [r for r in results if isinstance(r, AppError)]
    assert len(results) - len(failures) == 1
    assert all(f.status_code == 404 for f in failures)
    with session_factory() as session:
        issued = session.query(RefreshToken).filter(RefreshToken.user_id == owners.user_id).count()
    assert issued == 1


def test_concurrent_refreshes_of_one_refresh_token_rotate_it_once(session_factory: Any, owners: Owners) -> None:
    with session_factory() as session:
        old_token = refresh_token_service.create_sdk_refresh_token(
            session,
            user_id=owners.user_id,
            origin=SDKTokenOrigin.INVITE,
            issued_by_developer_id=owners.developer_id,
        )

    results = _run_concurrently(session_factory, lambda s: refresh_token_service.refresh_token(s, old_token))

    failures = [r for r in results if isinstance(r, AppError)]
    assert len(results) - len(failures) == 1
    assert all(f.status_code == 401 for f in failures)
    with session_factory() as session:
        live = session.query(RefreshToken).filter(
            RefreshToken.user_id == owners.user_id, RefreshToken.revoked_at.is_(None)
        )
        assert live.count() == 1


def test_concurrent_refreshes_of_one_developer_refresh_token_rotate_it_once(
    session_factory: Any, owners: Owners
) -> None:
    with session_factory() as session:
        old_token = refresh_token_service.create_developer_refresh_token(session, developer_id=owners.developer_id)

    results = _run_concurrently(session_factory, lambda s: refresh_token_service.refresh_token(s, old_token))

    failures = [r for r in results if isinstance(r, AppError)]
    assert len(results) - len(failures) == 1
    assert all(f.status_code == 401 for f in failures)
    with session_factory() as session:
        live = session.query(RefreshToken).filter(
            RefreshToken.developer_id == owners.developer_id, RefreshToken.revoked_at.is_(None)
        )
        assert live.count() == 1


def test_invitation_code_claimed_by_an_unfinished_redeem_is_not_given_to_another(
    session_factory: Any, owners: Owners
) -> None:
    """A second redeem waits for the first; it wins only if the first one rolls back."""
    with session_factory() as session:
        code = user_invitation_code_service.generate(session, owners.user_id, owners.developer_id).code

    with session_factory() as first, session_factory() as second:
        assert user_invitation_code_service.crud.claim_valid_code(first, code) is not None

        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(user_invitation_code_service.crud.claim_valid_code, second, code)
            with pytest.raises(TimeoutError):
                pending.result(timeout=0.5)  # blocked on the row the first session holds
            first.rollback()
            assert pending.result(timeout=5) is not None
