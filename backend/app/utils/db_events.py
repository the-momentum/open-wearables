"""Decorator factory for deferring a function's execution until a Session's real,
outermost commit.

Session-level ``after_commit`` fires for every SAVEPOINT release (any
``begin_nested()`` block that commits cleanly), not only for the session's
actual outermost COMMIT - see ``SessionTransaction.commit()`` in
sqlalchemy/orm/session.py: ``if self._parent is None or self.nested: ...
dispatch.after_commit(...)``. A callback registered directly via
``event.listens_for(db_session, "after_commit", once=True)`` inside a
savepoint therefore fires before the caller's actual commit, and if that
savepoint later fails, the ``once=True`` listener never gets a chance to
fire (and thus never gets removed) - it lingers on the session and fires
against a later, unrelated commit instead. ``defer_until_commit`` fixes
both: it only runs the decorated function once the outermost transaction
commits, and drops the call entirely if the savepoint that scheduled it
rolls back instead.
"""

from collections.abc import Callable

from sqlalchemy import event as sa_event
from sqlalchemy.orm import SessionTransaction

from app.database import DbSession

_PENDING_KEY = "_deferred_commit_callbacks"
_INSTALLED_KEY = "_deferred_commit_dispatcher_installed"


def defer_until_commit(db_session: DbSession) -> Callable[[Callable[[], None]], Callable[[], None]]:
    """``@defer_until_commit(db_session)`` on a zero-argument function schedules it to run
    once ``db_session``'s outermost transaction actually commits - applying the decorator is
    enough, there's nothing left to call.

    Safe to use from inside a ``begin_nested()`` block: the function is dropped, never run,
    if that savepoint rolls back instead of committing.
    """

    def decorator(func: Callable[[], None]) -> Callable[[], None]:
        """Record `func` against the current (possibly nested) transaction and return it unchanged."""
        owner = db_session.get_nested_transaction() or db_session.get_transaction()
        pending: list[tuple[SessionTransaction | None, Callable[[], None]]] = db_session.info.setdefault(
            _PENDING_KEY, []
        )
        pending.append((owner, func))

        if not db_session.info.get(_INSTALLED_KEY):
            db_session.info[_INSTALLED_KEY] = True
            _install_dispatchers(db_session)

        return func

    return decorator


def _install_dispatchers(db_session: DbSession) -> None:
    """Wire the after_commit/after_soft_rollback listeners that flush or drop pending callbacks.

    Installed once per session (guarded by `_INSTALLED_KEY`) rather than once per
    `defer_until_commit` call, since SQLAlchemy would otherwise re-run the pending
    list once per registered listener.
    """

    @sa_event.listens_for(db_session, "after_commit")
    def _run_pending(session: DbSession) -> None:
        """Run and clear all pending callbacks once the outermost transaction commits."""
        if session.in_nested_transaction():
            return
        for _, pending_callback in session.info.pop(_PENDING_KEY, []):
            pending_callback()

    @sa_event.listens_for(db_session, "after_soft_rollback")
    def _drop_rolled_back(session: DbSession, previous_transaction: SessionTransaction) -> None:
        """Discard callbacks whose owning transaction was rolled back, keeping the rest pending."""
        still_pending = session.info.get(_PENDING_KEY)
        if not still_pending:
            return
        session.info[_PENDING_KEY] = [
            (owner, pending_callback)
            for owner, pending_callback in still_pending
            if not _is_or_descends_from(owner, previous_transaction)
        ]


def _is_or_descends_from(transaction: SessionTransaction | None, ancestor: SessionTransaction) -> bool:
    """Return whether `transaction` is `ancestor` or was nested (directly or transitively) inside it."""
    while transaction is not None:
        if transaction is ancestor:
            return True
        transaction = transaction.parent
    return False
