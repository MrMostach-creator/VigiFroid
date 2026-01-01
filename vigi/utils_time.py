# vigi/utils_time.py  ✅ FINAL (safe timezone + Flask-aware)

from datetime import datetime
import pytz
from flask import current_app


def get_now(tz=None):
    """
    Returns timezone-aware now().
    Uses app config BABEL_DEFAULT_TIMEZONE if tz is not provided.
    Safe fallback to Africa/Casablanca if config is invalid.
    """
    if tz is None:
        tzname = "Africa/Casablanca"
        try:
            tzname = current_app.config.get("BABEL_DEFAULT_TIMEZONE", tzname)
        except Exception:
            # in case called outside app context
            pass

        try:
            tz = pytz.timezone(tzname)
        except Exception:
            tz = pytz.timezone("Africa/Casablanca")

    return datetime.now(tz)


def get_today_date():
    """Returns today's date in the configured timezone."""
    return get_now().date()
