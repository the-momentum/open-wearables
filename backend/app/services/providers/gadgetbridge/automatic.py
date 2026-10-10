"""Import a synchronized SQLite export after it settles, with durable worker-confirmed recovery."""

import hashlib
import json
import os
import sqlite3
import stat
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.services.providers.gadgetbridge.export import SDK_VERSION, HuaweiExport, batches, fingerprint
from app.services.providers.gadgetbridge.upload import upload_batches, write_private_json


@dataclass(frozen=True)
class FileVersion:
    device: int
    inode: int
    size: int
    modified: int
    changed: int

    @classmethod
    def read(cls, metadata: os.stat_result) -> "FileVersion":
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("The input must be a regular exported SQLite file, not a symlink")
        return cls(metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns)


def snapshot(source: Path, directory: Path) -> tuple[Path, str]:
    """Copy a stable export privately and reject partial files, symlinks and live WAL databases."""
    if Path(str(source) + "-wal").exists():
        raise ValueError("Export the database from Gadgetbridge; do not synchronize a live WAL database")
    before = FileVersion.read(source.lstat())
    descriptor, name = tempfile.mkstemp(prefix="snapshot-", suffix=".db", dir=directory)
    destination = Path(name)
    digest = hashlib.sha256()
    try:
        with (
            os.fdopen(descriptor, "wb") as output,
            os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), "rb") as incoming,
        ):
            if FileVersion.read(os.fstat(incoming.fileno())) != before:
                raise ValueError("Input changed before snapshot")
            while block := incoming.read(1024 * 1024):
                output.write(block)
                digest.update(block)
            if FileVersion.read(os.fstat(incoming.fileno())) != before:
                raise ValueError("Input changed during snapshot")
        if FileVersion.read(source.lstat()) != before:
            raise ValueError("Input was replaced during snapshot")
        with sqlite3.connect(destination.resolve().as_uri() + "?mode=ro", uri=True) as database:
            database.execute("PRAGMA query_only=ON")
            if database.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite integrity check failed; waiting for a complete export")
        return destination, digest.hexdigest()
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


class AutomaticImporter:
    def __init__(
        self,
        source: Path,
        state_directory: Path,
        client: httpx.Client,
        user_id: str,
        timezone_name: str = "Europe/Paris",
        device_id: int | None = None,
        gadgetbridge_user_id: int | None = None,
        batch_size: int = 500,
        settle_seconds: float = 30,
        retry_seconds: float = 300,
        timeout: float = 120,
    ) -> None:
        if settle_seconds < 0 or retry_seconds <= 0 or timeout <= 0 or not 1 <= batch_size <= 5000:
            raise ValueError("Invalid settle, retry, timeout or batch-size setting")
        self.source = source
        self.directory = state_directory
        self.client = client
        self.user_id = user_id
        self.timezone_name = timezone_name
        self.device_id = device_id
        self.gadgetbridge_user_id = gadgetbridge_user_id
        self.batch_size = batch_size
        self.settle_seconds = settle_seconds
        self.retry_seconds = retry_seconds
        self.timeout = timeout
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.status_file = self.directory / "status.json"
        target = {
            "url": str(client.base_url),
            "user_id": user_id,
            "timezone": timezone_name,
            "device_id": device_id,
            "gadgetbridge_user_id": gadgetbridge_user_id,
            "batch_size": batch_size,
            "converter": SDK_VERSION,
        }
        self.status: dict[str, Any] = (
            json.loads(self.status_file.read_text()) if self.status_file.exists() else {"target": target}
        )
        if self.status["target"] != target:
            raise ValueError("Persistent state belongs to another user, server or conversion configuration")
        self.observed: FileVersion | None = None
        self.processed_version: FileVersion | None = None
        self.observed_at = 0.0

    def save(self) -> None:
        write_private_json(self.status_file, self.status)

    def step(self, now: float | None = None) -> str:
        """Run one polling cycle; retain pending data across transfer changes and process restarts."""
        now = time.time() if now is None else now
        if now < self.status.get("retry_at", 0):
            return "retry_wait"
        try:
            if self.status.get("pending"):
                return self.deliver(now)
            try:
                version = FileVersion.read(self.source.lstat())
            except FileNotFoundError:
                self.observed = None
                return "waiting_for_export"
            if version != self.observed:
                self.observed = version
                self.observed_at = now
            if version == self.processed_version:
                return "unchanged"
            if now - self.observed_at < self.settle_seconds:
                return "waiting_for_stable_file"
            database, digest = snapshot(self.source, self.directory)
            try:
                if FileVersion.read(self.source.lstat()) != version:
                    raise ValueError("Input changed while waiting for a stable export")
                if digest == self.status.get("confirmed_sha256"):
                    self.processed_version = version
                    return "unchanged"
                exporter = HuaweiExport(database, self.timezone_name, self.device_id, self.gadgetbridge_user_id)
                payloads = batches(exporter.convert(), self.batch_size)
                job_id = fingerprint(payloads)
                job = self.directory / "jobs" / job_id
                write_private_json(job / "payloads.json", payloads)
                write_private_json(job / "report.json", dict(exporter.report))
                self.status["pending"] = {"sha256": digest, "job": job_id, "attempts": 0}
                self.save()
            finally:
                database.unlink(missing_ok=True)
            result = self.deliver(now)
            self.processed_version = version
            return result
        except (OSError, ValueError, RuntimeError, sqlite3.Error, httpx.HTTPError) as error:
            self.status["retry_at"] = now + self.retry_seconds
            self.status["last_error"] = type(error).__name__
            self.save()
            raise

    def deliver(self, now: float) -> str:
        pending = self.status["pending"]
        job = self.directory / "jobs" / pending["job"]
        payloads = json.loads((job / "payloads.json").read_text())
        retry = pending["attempts"] > 0
        pending["attempts"] += 1
        self.save()
        count = upload_batches(
            self.client,
            self.user_id,
            payloads,
            job / "checkpoint.json",
            timeout=self.timeout,
            retry_unconfirmed=retry,
            reconcile_before_retry=True,
        )
        self.status.update(
            confirmed_sha256=pending["sha256"],
            confirmed_job=pending["job"],
            confirmed_batches=count,
            last_success=now,
        )
        self.status.pop("pending")
        self.status.pop("retry_at", None)
        self.status.pop("last_error", None)
        self.save()
        # Full payloads are needed only during recovery; completed jobs keep small audit files.
        (job / "payloads.json").unlink(missing_ok=True)
        return "confirmed"
