"""Tests for signal handling in scripts/start/worker.sh.

The script runs two Celery workers in one container. A fake `uv` on PATH stands in for
both, so the tests cover the shell logic only: signal forwarding, which worker decides
the exit status, waiting for a worker that takes time to shut down, and that one
worker's failure does not stop the other.
"""

import contextlib
import os
import signal
import stat
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "start" / "worker.sh"

# Fake `uv`: identifies the worker by its node name (io@%h / cpu@%h), records what
# happens to it in $EVENTS_LOG and exits as configured through the environment:
#   EXIT_NOW_<role>=<code>      exit after EXIT_DELAY seconds without being signalled
#   SHUTDOWN_DELAY_<role>=<s>   take this long to shut down after SIGTERM
#   EXIT_ON_TERM_<role>=<code>  exit code after SIGTERM
# The TERM trap is installed before "started" is logged, so a test that waits for
# "started" can signal right away.
_FAKE_UV = """#!/bin/bash
for arg in "$@"; do
    case "$arg" in
        io@*) role=io ;;
        cpu@*) role=cpu ;;
    esac
done

shutdown_delay_var="SHUTDOWN_DELAY_$role"
exit_on_term_var="EXIT_ON_TERM_$role"
on_term() {
    echo "$role got TERM" >> "$EVENTS_LOG"
    sleep "${!shutdown_delay_var:-0}"
    echo "$role stopped" >> "$EVENTS_LOG"
    exit "${!exit_on_term_var:-0}"
}
trap on_term TERM
echo "$role pid $$" >> "$EVENTS_LOG"
echo "$role started" >> "$EVENTS_LOG"

exit_now_var="EXIT_NOW_$role"
if [ -n "${!exit_now_var}" ]; then
    sleep "${EXIT_DELAY:-0}"
    echo "$role exited" >> "$EVENTS_LOG"
    exit "${!exit_now_var}"
fi

while true; do
    sleep 0.05
done
"""

_TIMEOUT_S = 10.0


@pytest.fixture
def run_worker_script(tmp_path: Path) -> Iterator[Callable[..., tuple[subprocess.Popen, Path]]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(_FAKE_UV)
    fake_uv.chmod(fake_uv.stat().st_mode | stat.S_IEXEC)
    events_log = tmp_path / "events.log"
    events_log.touch()
    processes: list[subprocess.Popen] = []

    def start(**env_overrides: str) -> tuple[subprocess.Popen, Path]:
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "EVENTS_LOG": str(events_log),
            **env_overrides,
        }
        process = subprocess.Popen(
            ["bash", str(_SCRIPT_PATH)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # Own process group, so teardown also reaches the fake workers.
            start_new_session=True,
        )
        processes.append(process)
        return process, events_log

    yield start

    for process in processes:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def _events(events_log: Path) -> list[str]:
    return events_log.read_text().splitlines()


def _wait_for(events_log: Path, *expected: str) -> None:
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        if all(event in _events(events_log) for event in expected):
            return
        time.sleep(0.05)
    pytest.fail(f"Timed out waiting for {expected}; events so far: {_events(events_log)}")


def test_sigterm_is_forwarded_to_both_workers(run_worker_script: Callable) -> None:
    process, events_log = run_worker_script()
    _wait_for(events_log, "io started", "cpu started")

    process.send_signal(signal.SIGTERM)

    assert process.wait(timeout=_TIMEOUT_S) == 0
    assert "io got TERM" in _events(events_log)
    assert "cpu got TERM" in _events(events_log)


@pytest.mark.parametrize("cpu_status", ["0", "3"])
def test_exit_status_comes_from_the_cpu_worker(run_worker_script: Callable, cpu_status: str) -> None:
    process, events_log = run_worker_script(EXIT_ON_TERM_cpu=cpu_status, EXIT_ON_TERM_io="1")
    _wait_for(events_log, "io started", "cpu started")

    process.send_signal(signal.SIGTERM)

    assert process.wait(timeout=_TIMEOUT_S) == int(cpu_status)


def test_failing_io_worker_on_shutdown_does_not_skip_waiting_for_the_cpu_worker(
    run_worker_script: Callable,
) -> None:
    process, events_log = run_worker_script(EXIT_ON_TERM_io="1", SHUTDOWN_DELAY_cpu="0.5")
    _wait_for(events_log, "io started", "cpu started")

    process.send_signal(signal.SIGTERM)

    assert process.wait(timeout=_TIMEOUT_S) == 0
    assert "cpu stopped" in _events(events_log)


def _wait_until_reaped(pid: int) -> None:
    """Wait until the script has collected the process, so it is waiting for the next one."""
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    pytest.fail(f"Process {pid} was not reaped")


def test_second_signal_does_not_cut_a_slow_shutdown_short(run_worker_script: Callable) -> None:
    process, events_log = run_worker_script(SHUTDOWN_DELAY_io="1.5", SHUTDOWN_DELAY_cpu="0.2")
    _wait_for(events_log, "io started", "cpu started")
    [cpu_pid] = [int(event.split()[-1]) for event in _events(events_log) if event.startswith("cpu pid ")]

    process.send_signal(signal.SIGTERM)
    _wait_for(events_log, "cpu stopped")
    _wait_until_reaped(cpu_pid)
    process.send_signal(signal.SIGTERM)

    assert process.wait(timeout=_TIMEOUT_S) == 0
    assert "io stopped" in _events(events_log)


@pytest.mark.parametrize("cpu_status", [2, 127, 255])
def test_cpu_worker_exit_stops_the_io_worker_and_the_container(run_worker_script: Callable, cpu_status: int) -> None:
    """The worker's own exit code is kept, including 127 and 255 that bash 5 also uses for a lost status."""
    process, events_log = run_worker_script(EXIT_NOW_cpu=str(cpu_status), EXIT_DELAY="0.5", SHUTDOWN_DELAY_io="0.5")
    _wait_for(events_log, "io started", "cpu started")

    assert process.wait(timeout=_TIMEOUT_S) == cpu_status
    assert "io stopped" in _events(events_log)


def test_io_worker_crash_keeps_the_container_running(run_worker_script: Callable) -> None:
    process, events_log = run_worker_script(EXIT_NOW_io="1")
    _wait_for(events_log, "io exited", "cpu started")

    time.sleep(0.5)
    assert process.poll() is None

    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=_TIMEOUT_S) == 0
    assert "cpu got TERM" in _events(events_log)
