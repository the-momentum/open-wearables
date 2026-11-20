#!/bin/bash
set -e -x
trap 'exit 143' TERM INT

scripts/start/install_extensions.sh

# Extension migrations need the core's tables, which app.sh may still be creating on a fresh database.
# Every worker loads the extensions, so none starts before the schema is there; the restart policy retries.
for poll in $(seq 1 60); do
    uv run alembic current 2>&1 | grep -qE "\(head\)|Can't locate revision" && break
    if [ "$poll" = 60 ]; then
        echo "core schema not at head after 60 polls; exiting so the container restarts" >&2
        exit 1
    fi
    sleep "${SCHEMA_POLL_SECONDS:-2}"
done

# The workers this container runs, e.g. "ext" for a service of its own that scales the extension queues separately.
roles=",${WORKER_ROLES:-io,cpu,ext},"
io_pid=""
cpu_pid=""
ext_pid=""

extension_queues=""
if [[ "$roles" == *,ext,* ]]; then
    # OWExtension.celery_queues of the active extensions, for the extension worker below.
    extension_queues=$(uv run python scripts/start/extension_queues.py | tee /dev/stderr | sed -n 's/^EXTENSION_QUEUES=//p')
fi

if [[ "$roles" == *,io,* ]]; then
    echo "Starting I/O worker..."
    uv run celery -A app.main:celery_app worker --loglevel=info --pool=threads -Q default,sdk_sync,garmin_sync,webhook_sync -n io@%h &
    io_pid=$!
fi

if [[ "$roles" == *,cpu,* ]]; then
    echo "Starting CPU worker..."
    # XML imports are long and a direct upload carries the whole file in its message. With early
    # acks a prefetch multiplier of 1 still reserves one extra message per busy process, so
    # prefetch is disabled: the worker fetches a task only when a process is free.
    uv run celery -A app.main:celery_app worker --loglevel=info --pool=prefork --concurrency=2 --prefetch-multiplier=1 --disable-prefetch -Q xml_sync -n cpu@%h &
    cpu_pid=$!
fi

if [ -n "$extension_queues" ]; then
    echo "Starting extension worker..."
    # Extension tasks can run for minutes, so they get their own pool. Prefetch is off as for the CPU worker:
    # other worker containers take their share and a stop waits only for the tasks in progress.
    uv run celery -A app.main:celery_app worker --loglevel=info --pool=threads --concurrency="${EXTENSION_WORKER_CONCURRENCY:-4}" --prefetch-multiplier=1 --disable-prefetch -Q "$extension_queues" -n ext@%h &
    ext_pid=$!
fi
worker_pids=(${io_pid:+"$io_pid"} ${cpu_pid:+"$cpu_pid"} ${ext_pid:+"$ext_pid"})
if [ "${#worker_pids[@]}" = 0 ]; then
    echo "no worker to run for WORKER_ROLES=${WORKER_ROLES:-io,cpu,ext}; exiting" >&2
    exit 1
fi

# This shell is PID 1 in the container, so a SIGTERM from `docker stop` only reaches
# the workers if it is forwarded. Without it all are SIGKILLed after the grace period
# and tasks in flight are cut off instead of finishing (Celery warm shutdown).
signalled=0
trap 'signalled=1; kill -TERM "${worker_pids[@]}" 2>/dev/null || true' TERM INT

# set -e would exit on the first non-zero `wait` and skip waiting for the other workers.
set +e

# `wait` returns early whenever a trapped signal arrives (a second `docker stop`, Ctrl+C);
# the trap sets `signalled` and the wait is repeated until the process is gone. After such
# an interruption bash 5 can lose the child's exit status and return 127, 255 or -1. Only
# then is the result replaced: by the status of an uninterrupted wait, or by 143 (stopped
# by SIGTERM), which happens only when a signal coincides with the worker's exit. A worker
# that exits with 127 or 255 on its own keeps that code.
wait_for_exit() {
    local status="" result interrupted=0
    while kill -0 "$1" 2>/dev/null; do
        signalled=0
        wait "$1"
        result=$?
        if [ "$signalled" = 0 ]; then status=$result; else interrupted=1; fi
    done
    signalled=1
    while [ "$signalled" = 1 ]; do
        signalled=0
        wait "$1"
        result=$?
        [ "$signalled" = 1 ] && interrupted=1
    done
    if [ "$interrupted" = 1 ] && { [ "$result" -lt 0 ] || [ "$result" -eq 127 ] || [ "$result" -ge 255 ]; }; then
        return "${status:-143}"
    fi
    return "$result"
}

# The container lives as long as all its workers: a queue nobody consumes must not go unnoticed.
# `wait -n` (bash 5.1+) returns when the first worker exits, or early for a stop signal.
wait -n -p first_pid "${worker_pids[@]}"
status=$?

if [ "$signalled" = 0 ]; then
    # A worker exited on its own: stop the others and keep its status, but never 0, which an on-failure restart
    # policy would take as a finished container.
    [ "$status" = 0 ] && status=1
    for pid in "${worker_pids[@]}"; do
        [ "$pid" != "$first_pid" ] && kill -TERM "$pid" 2>/dev/null
    done
    for pid in "${worker_pids[@]}"; do
        [ "$pid" != "$first_pid" ] && wait_for_exit "$pid"
    done
    exit "$status"
fi

# Stopped: the trap has signalled every worker, and the status is the CPU worker's, as before, or the first one's.
status_pid=${cpu_pid:-${worker_pids[0]}}
wait_for_exit "$status_pid"
status=$?
for pid in "${worker_pids[@]}"; do
    [ "$pid" != "$status_pid" ] && wait_for_exit "$pid"
done
exit "$status"
