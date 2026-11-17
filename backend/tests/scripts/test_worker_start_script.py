"""Tests for signal handling in scripts/start/worker.sh.

The script runs two Celery workers in one container, and a third when installed extensions
declare queues. A fake `uv` on PATH stands in for them, so the tests cover the shell logic
only: signal forwarding, which worker decides the exit status, waiting for a worker that
takes time to shut down, and that one worker's failure does not stop the others.
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

# Fake `uv`: identifies the worker by its node name (io@%h / cpu@%h / ext@%h), records what
# happens to it in $EVENTS_LOG and exits as configured through the environment:
#   EXIT_NOW_<role>=<code>      exit after EXIT_DELAY seconds without being signalled
#   SHUTDOWN_DELAY_<role>=<s>   take this long to shut down after SIGTERM
#   EXIT_ON_TERM_<role>=<code>  exit code after SIGTERM
# The TERM trap is installed before "started" is logged, so a test that waits for
# "started" can signal right away.
_FAKE_UV = """#!/bin/bash
# The extensions' queue lookup: the core's log of loading them, then the marker line (or a failure)
if [[ "$*" == *extension_queues.py* ]]; then
    echo '{"message": "Extension disabled", "reason": "migrations failed"}'
    [ -n "$LOOKUP_FAILS" ] && exit 1
    echo "EXTENSION_QUEUES=${EXT_QUEUES:-}"
    exit 0
fi

# The core schema check: a revision that is not head for the first NOT_HEAD_ANSWERS calls, then head;
# with UNKNOWN_REVISION it fails as alembic does on a revision missing from this image
if [[ "$*" == *"alembic current"* ]]; then
    echo "$*" >> "$EVENTS_LOG"
    if [ -n "$UNKNOWN_REVISION" ]; then
        echo "ERROR [alembic.util.messaging] Can't locate revision identified by 'abc123'" >&2
        echo "FAILED: Can't locate revision identified by 'abc123'"
        exit 255
    fi
    calls=$(cat "$ALEMBIC_COUNTER" 2>/dev/null || echo 0)
    echo $((calls + 1)) > "$ALEMBIC_COUNTER"
    if [ "$calls" -lt "${NOT_HEAD_ANSWERS:-0}" ]; then echo "abc123"; else echo "abc123 (head)"; fi
    exit 0
fi

for arg in "$@"; do
    case "$arg" in
        io@*) role=io ;;
        cpu@*) role=cpu ;;
        ext@*) role=ext ;;
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
echo "$role args $*" >> "$EVENTS_LOG"
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
            "ALEMBIC_COUNTER": str(tmp_path / "alembic_counter"),
            "SCHEMA_POLL_SECONDS": "0.1",
            **env_overrides,
        }
        with (tmp_path / "container.log").open("ab") as container_log:
            process = subprocess.Popen(
                ["bash", str(_SCRIPT_PATH)],
                env=env,
                stdout=container_log,
                stderr=subprocess.STDOUT,
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


def test_sigterm_is_forwarded_to_every_worker(run_worker_script: Callable) -> None:
    process, events_log = run_worker_script(EXT_QUEUES="my_queue", SHUTDOWN_DELAY_ext="0.5")
    _wait_for(events_log, "io started", "cpu started", "ext started")

    process.send_signal(signal.SIGTERM)

    assert process.wait(timeout=_TIMEOUT_S) == 0
    assert "io got TERM" in _events(events_log)
    assert "cpu got TERM" in _events(events_log)
    assert "ext stopped" in _events(events_log)


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
def test_cpu_worker_exit_stops_the_other_workers_and_the_container(
    run_worker_script: Callable, cpu_status: int
) -> None:
    """The worker's own exit code is kept, including 127 and 255 that bash 5 also uses for a lost status."""
    process, events_log = run_worker_script(
        EXT_QUEUES="my_queue",
        EXIT_NOW_cpu=str(cpu_status),
        EXIT_DELAY="0.5",
        SHUTDOWN_DELAY_io="0.5",
        SHUTDOWN_DELAY_ext="0.5",
    )
    _wait_for(events_log, "io started", "cpu started", "ext started")

    assert process.wait(timeout=_TIMEOUT_S) == cpu_status
    assert "io stopped" in _events(events_log)
    assert "ext stopped" in _events(events_log)


@pytest.mark.parametrize("role", ["io", "ext"])
def test_io_or_extension_worker_crash_keeps_the_container_running(run_worker_script: Callable, role: str) -> None:
    process, events_log = run_worker_script(EXT_QUEUES="my_queue", **{f"EXIT_NOW_{role}": "1"})
    _wait_for(events_log, f"{role} exited", "cpu started")

    time.sleep(0.5)
    assert process.poll() is None

    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=_TIMEOUT_S) == 0
    assert "cpu got TERM" in _events(events_log)


@pytest.mark.parametrize(
    "env", [{}, {"EXT_QUEUES": "my_queue", "LOOKUP_FAILS": "1"}], ids=["none_declared", "lookup_failed"]
)
def test_only_the_core_workers_start_without_extension_queues(run_worker_script: Callable, env: dict[str, str]) -> None:
    process, events_log = run_worker_script(**env)
    _wait_for(events_log, "io started", "cpu started")

    time.sleep(0.5)
    assert "ext started" not in _events(events_log)


def test_extension_worker_runs_the_extension_queues(run_worker_script: Callable) -> None:
    process, events_log = run_worker_script(EXT_QUEUES="my_queue,other")
    _wait_for(events_log, "io started", "cpu started", "ext started")

    [args] = [event for event in _events(events_log) if event.startswith("ext args ")]
    assert "-Q my_queue,other" in args
    assert "--pool=threads" in args
    assert "--prefetch-multiplier=1" in args
    assert "--disable-prefetch" in args


def test_workers_start_only_after_the_core_schema_is_at_head(run_worker_script: Callable) -> None:
    process, events_log = run_worker_script(EXT_QUEUES="my_queue", NOT_HEAD_ANSWERS="3")
    _wait_for(events_log, "io started", "cpu started", "ext started")

    events = _events(events_log)
    schema_checks = [i for i, event in enumerate(events) if event.endswith("alembic current")]
    assert len(schema_checks) == 4
    assert max(schema_checks) < events.index("io started")


def test_workers_start_when_the_core_schema_never_reaches_head(run_worker_script: Callable) -> None:
    process, events_log = run_worker_script(NOT_HEAD_ANSWERS="1000", SCHEMA_POLL_SECONDS="0")
    _wait_for(events_log, "io started", "cpu started")

    schema_checks = [event for event in _events(events_log) if event.endswith("alembic current")]
    assert len(schema_checks) == 60


def test_workers_start_at_once_when_the_database_is_at_a_revision_this_image_does_not_know(
    run_worker_script: Callable,
) -> None:
    process, events_log = run_worker_script(UNKNOWN_REVISION="1", SCHEMA_POLL_SECONDS="0")
    _wait_for(events_log, "io started", "cpu started")

    schema_checks = [event for event in _events(events_log) if event.endswith("alembic current")]
    assert len(schema_checks) == 1


def test_a_stop_during_the_schema_wait_ends_the_script_within_one_poll(run_worker_script: Callable) -> None:
    process, events_log = run_worker_script(NOT_HEAD_ANSWERS="1000", SCHEMA_POLL_SECONDS="1")
    _wait_for(events_log, "run alembic current")

    process.send_signal(signal.SIGTERM)

    assert process.wait(timeout=_TIMEOUT_S) == 143
    events = _events(events_log)
    assert events.count("run alembic current") == 1
    assert "io started" not in events


def test_the_log_of_loading_the_extensions_reaches_the_container_log(
    run_worker_script: Callable, tmp_path: Path
) -> None:
    process, events_log = run_worker_script()
    _wait_for(events_log, "io started", "cpu started")

    assert '"message": "Extension disabled"' in (tmp_path / "container.log").read_text()
