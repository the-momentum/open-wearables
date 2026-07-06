"""SSE (Server-Sent Events) formatting helpers."""


def format_event(data: str, *, event_type: str | None = None, event_id: str | None = None) -> str:
    """Format a single SSE event frame."""
    lines: list[str] = []
    if event_type:
        lines.append(f"event: {event_type}")
    if event_id:
        lines.append(f"id: {event_id}")
    for line in data.splitlines() or [data]:
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


def format_comment(comment: str) -> str:
    """Format an SSE comment (keepalive / debug)."""
    return f": {comment}\n\n"
