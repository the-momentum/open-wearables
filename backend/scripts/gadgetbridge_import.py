"""Convert a read-only Gadgetbridge SQLite export, optionally deliver and confirm each batch."""

import argparse
import fcntl
import json
import os
import sqlite3
from pathlib import Path
from uuid import UUID

import httpx

from app.services.providers.gadgetbridge.export import HuaweiExport, batches, fingerprint
from app.services.providers.gadgetbridge.upload import upload_batches, write_private_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timezone", default="Europe/Paris")
    parser.add_argument("--device-id", type=int)
    parser.add_argument("--gadgetbridge-user-id", type=int)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--hrv-kind", choices=["rmssd", "sdnn"], default="rmssd")
    parser.add_argument("--hrv-unit", choices=["ms"], default="ms", help="Verified Huawei HRV unit: milliseconds")
    parser.add_argument("--activity-calorie-unit", choices=["cal", "kcal"], default="cal")
    parser.add_argument("--workout-calorie-unit", choices=["cal", "kcal"], default="kcal")
    parser.add_argument("--sleep-stage-map", help="JSON object mapping verified numeric codes to SDK labels")
    parser.add_argument("--api-url", help="When absent, export only; no network calls")
    parser.add_argument("--user-id", type=UUID)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument(
        "--retry-unconfirmed", action="store_true", help="Repost unconfirmed batches with a fresh run ID"
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.api_url and (not args.user_id or not os.environ.get("OPEN_WEARABLES_API_KEY")):
        parser.error("Delivery requires --user-id and OPEN_WEARABLES_API_KEY in the process environment")
    try:
        mapping = (
            {int(code): label for code, label in json.loads(args.sleep_stage_map).items()}
            if args.sleep_stage_map
            else None
        )
        exporter = HuaweiExport(
            args.database,
            args.timezone,
            args.device_id,
            args.gadgetbridge_user_id,
            args.hrv_kind,
            args.activity_calorie_unit,
            args.workout_calorie_unit,
            mapping,
        )
        data = exporter.convert()
        payloads = batches(data, args.batch_size)
        directory = args.output / fingerprint(payloads)[:16]
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        for index, payload in enumerate(payloads):
            path = directory / f"batch-{index:05d}.json"
            if path.exists() and json.loads(path.read_text()) != payload:
                raise ValueError("Existing payload differs; refusing to overwrite it")
            if not path.exists():
                write_private_json(path, payload)
        write_private_json(directory / "report.json", dict(exporter.report))
        print(json.dumps({"batches": len(payloads), "report": dict(exporter.report)}))
        if args.api_url:
            lock_path = directory / "upload.lock"
            with lock_path.open("a") as lock:
                lock_path.chmod(0o600)
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with httpx.Client(
                    base_url=args.api_url.rstrip("/"),
                    timeout=30,
                    headers={"X-Open-Wearables-API-Key": os.environ["OPEN_WEARABLES_API_KEY"]},
                ) as client:
                    count = upload_batches(
                        client,
                        str(args.user_id),
                        payloads,
                        directory / "checkpoint.json",
                        args.timeout,
                        args.retry_unconfirmed,
                    )
                print(f"Confirmed {count} batches after worker processing")
    except (ValueError, OSError, RuntimeError, sqlite3.Error, httpx.HTTPError) as error:
        parser.exit(1, f"Import stopped: {type(error).__name__}; checkpoint preserved. {error}\n")


if __name__ == "__main__":
    main()
