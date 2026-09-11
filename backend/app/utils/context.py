"""Request/task context propagation via Python ContextVar.

Set trace_id_var once at the entry point (Celery task, API request handler) and
every log_structured call in the same execution context inherits it automatically.

sync_run_var works the same way for the run being ingested, so the shared write paths
can stamp outgoing data events with it without every provider threading it through.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from app.schemas.sync_status import SyncRunContext, SyncScope, SyncSource

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

sync_run_var: ContextVar[SyncRunContext | None] = ContextVar("sync_run", default=None)


@contextmanager
def sync_run_context(
    *,
    run_id: str,
    source: SyncSource | str,
    scope: SyncScope | str,
) -> Iterator[SyncRunContext]:
    """Mark everything ingested in this block as belonging to one sync run.

    Resets on exit, so a worker reusing the thread for the next task does not inherit it.
    """
    context = SyncRunContext(run_id=run_id, source=SyncSource(source), scope=SyncScope(scope))
    token = sync_run_var.set(context)
    try:
        yield context
    finally:
        sync_run_var.reset(token)
