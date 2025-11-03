import traceback

try:
    from app.models import *  # noqa: F401
except ImportError:
    traceback.print_exc()
    raise
