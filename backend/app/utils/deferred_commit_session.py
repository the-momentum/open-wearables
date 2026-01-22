"""Session wrapper that defers commits for bulk operations."""

from typing import Any

from app.database import DbSession


class DeferredCommitSession:
    """Wraps a database session to defer commits until explicitly requested.
    
    Used for bulk import operations to batch multiple commits into one.
    """
    
    def __init__(self, session: DbSession):
        self._session = session
        self._deferred = False
        self._original_commit = session.commit
    
    def __enter__(self) -> "DeferredCommitSession":
        self._deferred = True
        # Replace commit with a no-op
        self._session.commit = lambda: None  # type: ignore[method-assign]
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        # Restore original commit
        self._session.commit = self._original_commit  # type: ignore[method-assign]
        
        if exc_type is None:
            # No exception, commit all deferred changes
            self._session.commit()
        else:
            # Exception occurred, rollback
            self._session.rollback()
        
        self._deferred = False
        return False
    
    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the wrapped session."""
        return getattr(self._session, name)
