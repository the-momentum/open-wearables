"""Continuously convert and import a synchronized Gadgetbridge SQLite export."""

import argparse
import fcntl
import os
import signal
import sqlite3
from logging import getLogger
from pathlib import Path
from threading import Event
from uuid import UUID

import httpx

from app.services.providers.gadgetbridge.automatic import AutomaticImporter
from app.utils.structured_logging import log_structured


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--api-url", default=os.environ.get("GADGETBRIDGE_API_URL", "http://app:8000"))
    parser.add_argument("--user-id", type=UUID, default=os.environ.get("GADGETBRIDGE_USER_ID"))
    parser.add_argument("--timezone", default=os.environ.get("GADGETBRIDGE_TIMEZONE", "Europe/Paris"))
    parser.add_argument("--device-id", type=int)
    parser.add_argument("--gadgetbridge-user-id", type=int)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--poll-seconds", type=float, default=30)
    parser.add_argument("--settle-seconds", type=float, default=30)
    parser.add_argument("--retry-seconds", type=float, default=300)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--once", action="store_true", help="Process one stable export and exit; useful for testing")
    args = parser.parse_args()
    key = os.environ.get("OPEN_WEARABLES_API_KEY")
    if not key or not args.user_id:
        parser.error("Set OPEN_WEARABLES_API_KEY and GADGETBRIDGE_USER_ID (or --user-id)")
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be positive")
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    logger = getLogger(__name__)
    args.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with (args.state / "watch.lock").open("a") as lock:
            (args.state / "watch.lock").chmod(0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with httpx.Client(
                base_url=args.api_url.rstrip("/"),
                timeout=30,
                headers={"X-Open-Wearables-API-Key": key},
                # The self-hosted API and its credentials must stay off environment HTTP proxies.
                trust_env=False,
            ) as client:
                importer = AutomaticImporter(
                    args.database,
                    args.state,
                    client,
                    str(args.user_id),
                    args.timezone,
                    args.device_id,
                    args.gadgetbridge_user_id,
                    args.batch_size,
                    args.settle_seconds,
                    args.retry_seconds,
                    args.timeout,
                )
                log_structured(logger, "info", "Automatic Gadgetbridge importer started", provider="gadgetbridge")
                previous = None
                while not stop.is_set():
                    try:
                        result = importer.step()
                    except (OSError, ValueError, RuntimeError, sqlite3.Error, httpx.HTTPError) as error:
                        # Report the class only: validation exceptions may contain private measurements.
                        log_structured(
                            logger,
                            "error",
                            "Automatic import failed; persistent state retained for retry",
                            provider="gadgetbridge",
                            error_type=type(error).__name__,
                            http_status=error.response.status_code
                            if isinstance(error, httpx.HTTPStatusError)
                            else None,
                        )
                        if args.once:
                            parser.exit(1, "Import failed; see logs and persistent state\n")
                        result = "retry_wait"
                    if result != previous or result == "confirmed":
                        log_structured(logger, "info", "Automatic import cycle", provider="gadgetbridge", result=result)
                    previous = result
                    if args.once and result in {"confirmed", "unchanged"}:
                        break
                    if args.once and result in {"waiting_for_export", "retry_wait"}:
                        parser.exit(1, "No import confirmed; see persistent state or missing input file\n")
                    stop.wait(args.poll_seconds)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot start automatic importer: {error}\n")


if __name__ == "__main__":
    main()
