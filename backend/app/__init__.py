import traceback

try:
    from app.models import *  # noqa: F403
except ImportError:
    traceback.print_exc()
    raise
