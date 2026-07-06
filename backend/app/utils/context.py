"""Request/task context propagation via Python ContextVar.

Set trace_id_var once at the entry point (Celery task, API request handler) and
every log_structured call in the same execution context inherits it automatically.
"""

from contextvars import ContextVar

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
