"""Print EXTENSION_QUEUES=<the active extensions' queues, comma-separated> for worker.sh."""

import sys

from app.extensions import collect_celery_queues


def main() -> None:
    try:
        queues = collect_celery_queues()
    except Exception as exc:  # the core's workers must start whatever an extension does
        print(f"Could not read the extensions' queues: {exc!r}", file=sys.stderr)
        queues = ()
    print(f"EXTENSION_QUEUES={','.join(queues)}")


if __name__ == "__main__":
    main()
