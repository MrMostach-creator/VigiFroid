
# ─────────────────────────────────────────────────────────
# config.py  
# ─────────────────────────────────────────────────────────
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    # ── i18n / Babel ─────────────────────────────────────
    LANGUAGES = ["ar", "fr", "en"]
    BABEL_DEFAULT_LOCALE = "fr"
    BABEL_DEFAULT_TIMEZONE = "Africa/Casablanca"
    BABEL_TRANSLATION_DIRECTORIES = str(BASE_DIR / "translations")
    ASSET_VERSION = "v2.4.2"

    # ── Security / Sessions ──────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-vigifroid-keep-this-constant")

    SESSION_COOKIE_NAME = "vf_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(days=90)
    REMEMBER_COOKIE_DURATION = timedelta(days=7)

    # ── DB (PostgreSQL) ─────────────────────────────────
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or "postgresql+psycopg2://postgres:loni@localhost:5432/vigifroid_db"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Files ────────────────────────────────────────────
    UPLOAD_FOLDER = str(BASE_DIR / "static" / "images")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB

    # ── Misc ─────────────────────────────────────────────
    JSON_AS_ASCII = False
    PREFERRED_URL_SCHEME = "http"

    # Cache (اختياري)
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = 300
    CACHE_REDIS_URL = os.environ.get("CACHE_REDIS_URL")

    # CSRF
    WTF_CSRF_TIME_LIMIT = 3600 * 6  

    # ── 📧 Mail / SMTP 
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False

    # الإيميل اللي غادي يتصيفط منو
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = ("VigiFroid", MAIL_USERNAME)
