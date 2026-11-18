#!/bin/bash
set -e -x

scripts/start/install_extensions.sh

echo "Starting I/O worker..."
# Without --concurrency the thread pool is sized to the host's CPU count. Set
# IO_WORKER_CONCURRENCY to make it the same wherever the image runs.
uv run celery -A app.main:celery_app worker --loglevel=info --pool=threads ${IO_WORKER_CONCURRENCY:+--concurrency=$IO_WORKER_CONCURRENCY} -Q default,sdk_sync,garmin_sync,webhook_sync -n io@%h &
io_pid=$!

echo "Starting CPU worker..."
# XML imports are long and a direct upload carries the whole file in its message. With early
# acks a prefetch multiplier of 1 still reserves one extra message per busy process, so
# prefetch is disabled: the worker fetches a task only when a process is free.
uv run celery -A app.main:celery_app worker --loglevel=info --pool=prefork --concurrency=2 --prefetch-multiplier=1 --disable-prefetch -Q xml_sync -n cpu@%h &
cpu_pid=$!

# This shell is PID 1 in the container, so a SIGTERM from `docker stop` only reaches
# the workers if it is forwarded. Without it both are SIGKILLed after the grace period
# and tasks in flight are cut off instead of finishing (Celery warm shutdown).
signalled=0
stopping=0
trap 'stopping=1; signalled=1; kill -TERM "$io_pid" "$cpu_pid" 2>/dev/null || true' TERM INT

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

# The container lives as long as both workers. If one exits on its own (a crash, or
# killed for memory), the other is stopped and the container exits with the first one's
# status, so the orchestrator can restart it instead of reporting a container that no
# longer runs half its queues as healthy. Bash 3.2 (macOS, where the tests run too) has
# no `wait -n`, so the workers are polled; the trap interrupts the `wait` on the sleep.
# Tracing is turned off first, or every poll would end up in the container log.
set +x
while [ "$stopping" = 0 ] && kill -0 "$io_pid" 2>/dev/null && kill -0 "$cpu_pid" 2>/dev/null; do
    sleep 1 &
    wait $!
done

if [ "$stopping" = 1 ]; then
    # Stopped from outside: the exit status comes from the CPU worker, as before.
    first_pid=$cpu_pid
    other_pid=$io_pid
elif kill -0 "$cpu_pid" 2>/dev/null; then
    first_pid=$io_pid
    other_pid=$cpu_pid
else
    first_pid=$cpu_pid
    other_pid=$io_pid
fi

wait_for_exit "$first_pid"
status=$?

kill -TERM "$other_pid" 2>/dev/null
wait_for_exit "$other_pid"
exit "$status"
