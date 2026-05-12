"""Logging filters applied to third-party loggers (uvicorn, etc).

Production OW emitted ~88% of the GCP project log ingest in May 2026,
almost entirely from uvicorn's per-request access lines on happy-path
``2xx`` responses (see axlbrains/open-wearables#8).  4xx/5xx access
lines remain — those carry signal — and the structured app logger is
unaffected.
"""

import logging


class UvicornAccess2xxFilter(logging.Filter):
    """Drop ``uvicorn.access`` records for ``2xx`` responses.

    ``uvicorn.access`` records carry the status code as the 5th element
    of ``record.args`` (a 5-tuple ``(client_addr, method, full_path,
    http_version, status_code)``).  When that shape isn't present we
    leave the record alone — losing a noisy line is fine, dropping a
    real error because the format changed is not.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            try:
                status = int(args[4])
            except (TypeError, ValueError):
                return True
            return not (200 <= status < 300)
        return True
