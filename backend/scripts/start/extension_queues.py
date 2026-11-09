"""Print the Celery queues the active extensions declare, for worker.sh: EXTENSION_QUEUES=<comma-separated>.

A marker line, since loading the extensions logs to stdout too. When they can't be loaded the list is empty and only the
core's own workers start; the failure is printed to stderr."""

import sys


def main() -> None:
    try:
        from app.extensions import collect_celery_queues, get_extensions

        queues = collect_celery_queues()
        # Loading logs to stdout, which worker.sh drops; say why an extension gets no worker
        for loaded in get_extensions():
            if loaded.error:
                print(f"Extension {loaded.name} disabled, its queues get no worker: {loaded.error}", file=sys.stderr)
    except Exception as exc:  # the core's workers must start whatever an extension does
        print(f"Could not read the extensions' queues: {exc!r}", file=sys.stderr)
        queues = ()
    print(f"EXTENSION_QUEUES={','.join(queues)}")


if __name__ == "__main__":
    main()
