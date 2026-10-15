#!/bin/bash
set -e -x

scripts/start/install_extensions.sh

echo "Starting I/O worker..."
uv run celery -A app.main:celery_app worker --loglevel=info --pool=threads -Q default,sdk_sync,garmin_sync,webhook_sync -n io@%h &
io_pid=$!

echo "Starting CPU worker..."
uv run celery -A app.main:celery_app worker --loglevel=info --pool=prefork --concurrency=2 -Q xml_sync -n cpu@%h &
cpu_pid=$!

# This shell is PID 1 in the container, so a SIGTERM from `docker stop` only reaches
# the workers if it is forwarded. Without it both are SIGKILLed after the grace period
# and tasks in flight are cut off instead of finishing (Celery warm shutdown).
signalled=0
trap 'signalled=1; kill -TERM "$io_pid" "$cpu_pid" 2>/dev/null || true' TERM INT

# set -e would exit on the first non-zero `wait` and skip waiting for the other worker.
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

# The container lives as long as the CPU worker, as before.
wait_for_exit "$cpu_pid"
status=$?

kill -TERM "$io_pid" 2>/dev/null
wait_for_exit "$io_pid"
exit "$status"
