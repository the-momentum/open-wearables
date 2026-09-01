import traceback
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("open-wearables")
except PackageNotFoundError:  # package not installed (e.g. running from a bare checkout)
    __version__ = "unknown"

try:
    from app.models import *  # noqa: F403
except ImportError:
    traceback.print_exc()
    raise
