# vigi/__init__.py  ✅ FINAL (+ unified dd/MM/YYYY date helper)
import os
import random
import time

from flask import Flask, current_app, session, request, render_template, make_response, send_from_directory, url_for, abort
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from flask_babel import format_date, format_datetime, format_time
from dotenv import load_dotenv
from flask_talisman import Talisman

from .extensions import db, migrate, cache, babel, compress, login_manager, mail, limiter

load_dotenv()
csrf = CSRFProtect()


def create_app(config_class="config.Config"):
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app = Flask(
        __name__,
        instance_relative_config=False,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    # ✅ uploads always in instance/uploads (public via /uploads/<file>)
    app.config["UPLOAD_FOLDER"] = os.path.join(base_dir, "instance", "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ── 🔐 Security Headers / CSP ───────────────────────
    csp = {
        "default-src": ["'self'"],

        "connect-src": [
            "'self'",
            "https://cdn.jsdelivr.net",
            "https://fonts.googleapis.com",
            "https://fonts.gstatic.com",
        ],

        "script-src": [
            "'self'",
            "'unsafe-inline'",
            "https://cdn.jsdelivr.net",
        ],
        "style-src": [
            "'self'",
            "'unsafe-inline'",
            "https://cdn.jsdelivr.net",
            "https://fonts.googleapis.com",
        ],
        "font-src": [
            "'self'",
            "data:",
            "https://fonts.gstatic.com",
        ],
        "img-src": [
            "'self'",
            "data:",
            "blob:",
        ],
    }

    Talisman(
        app,
        content_security_policy=csp,
        force_https=True,
        strict_transport_security=True,
    )

    # ✅ Public uploads endpoint (safe)
    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename):
        filename = os.path.basename(str(filename))

        ext = os.path.splitext(filename)[1].lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
            abort(404)

        resp = send_from_directory(app.config["UPLOAD_FOLDER"], filename)
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    def uploaded_url(filename):
        if not filename:
            return ""
        filename = os.path.basename(str(filename))
        return url_for("uploaded_file", filename=filename)

    # init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)
    mail.init_app(app)
    compress.init_app(app)

    # locale selector
    def get_locale():
        lang = session.get("lang")
        if lang:
            return lang
        langs = app.config.get("LANGUAGES", ["ar", "fr", "en"])
        return request.accept_languages.best_match(langs) or langs[0]

    babel.init_app(app, locale_selector=get_locale)

    # ✅ helper: force date format dd/MM/YYYY everywhere in templates
    def fmt_date_dmy(d):
        if not d:
            return ""
        return d.strftime("%d/%m/%Y")

    @app.context_processor
    def inject_globals():
        return {
            "get_locale": get_locale,
            "format_date": format_date,
            "format_datetime": format_datetime,
            "format_time": format_time,
            "fmt_date": fmt_date_dmy,
            "uploaded_url": uploaded_url,  # ✅ needed by templates
            "config": app.config,
        }

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("403.html"), 403

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    @app.route("/manifest.json")
    def manifest():
        resp = current_app.send_static_file("manifest.json")
        resp.headers["Content-Type"] = "application/manifest+json"
        return resp

    @app.route("/service-worker.js")
    def service_worker():
        resp = make_response(render_template("service-worker.js"))
        resp.headers["Content-Type"] = "application/javascript"
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    # DB pool check
    with app.app_context():
        try:
            engine = db.engine
            pool_name = type(engine.pool).__name__
            status = engine.pool.status() if hasattr(engine.pool, "status") else "N/A"
            app.logger.info(f"DB engine={engine.name}, pool={pool_name}, status={status}")
        except Exception as e:
            app.logger.warning(f"DB pool introspection failed: {e}")

    @app.get("/__pool")
    def pool_check():
        t0 = time.perf_counter()
        db.session.execute(text("SELECT 1"))
        db.session.commit()
        dt = round((time.perf_counter() - t0) * 1000, 2)
        try:
            engine = db.engine
            pool = type(engine.pool).__name__
            status = engine.pool.status() if hasattr(engine.pool, "status") else "N/A"
        except Exception as e:
            pool, status = "N/A", str(e)
        return {"ok": True, "latency_ms": dt, "pool": pool, "status": status}, 200

    @app.get("/__cache_test")
    @cache.cached(timeout=15)
    def cache_test():
        n = random.randint(1000, 9999)
        time.sleep(1)
        return {"random_number": n, "cached_for": "15 seconds"}

    # ✅ Register blueprints
    from vigi.main.routes import main_bp
    app.register_blueprint(main_bp)

    try:
        from vigi.auth.routes import auth_bp
        app.register_blueprint(auth_bp)
    except Exception as e:
        app.logger.warning(f"auth blueprint not registered: {e}")

    try:
        from vigi.lots.routes import lots_bp
        app.register_blueprint(lots_bp)
    except Exception as e:
        app.logger.warning(f"lots blueprint not registered: {e}")

    try:
        from vigi.logs.routes import logs_bp
        app.register_blueprint(logs_bp)
    except Exception as e:
        app.logger.warning(f"logs blueprint not registered: {e}")

    # CLI
    try:
        from vigi.cli_autoexport import register_cli
        register_cli(app)
        app.logger.info("✅ CLI autoexport registered")
    except Exception as e:
        app.logger.warning(f"CLI autoexport not registered: {e}")

    return app
