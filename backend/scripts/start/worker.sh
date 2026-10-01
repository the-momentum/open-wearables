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
# the trap sets `signalled` and the wait is repeated until the process is gone. Only the
# status of an uninterrupted wait is trusted: after an interruption bash 5 can lose the
# child's exit status and return 127, 255 or -1. The status then falls back to 143
# (stopped by SIGTERM), which only happens when a signal coincides with the worker's exit.
wait_for_exit() {
    local status="" result
    while kill -0 "$1" 2>/dev/null; do
        signalled=0
        wait "$1"
        result=$?
        [ "$signalled" = 0 ] && status=$result
    done
    signalled=1
    while [ "$signalled" = 1 ]; do
        signalled=0
        wait "$1"
        result=$?
    done
    if [ "$result" -ge 0 ] && [ "$result" -le 254 ] && [ "$result" -ne 127 ]; then
        return "$result"
    fi
    return "${status:-143}"
}

# The container lives as long as the CPU worker, as before.
wait_for_exit "$cpu_pid"
status=$?

kill -TERM "$io_pid" 2>/dev/null
wait_for_exit "$io_pid"
exit "$status"
