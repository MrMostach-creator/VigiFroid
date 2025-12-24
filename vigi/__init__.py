# ────────────────────────────────
# 📁 vigi/__init__.py — 
# ────────────────────────────────

# vigi/__init__.py

import os
import random
import time
from flask import Flask, current_app, session, request, render_template, make_response
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from flask_babel import format_date, format_datetime, format_time
from .extensions import db, migrate, cache, babel, compress, login_manager, mail

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

    # إعدادات افتراضية
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("UPLOAD_FOLDER", os.path.join(app.root_path, "static", "images"))

    # تهيئة الإضافات
    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)
    mail.init_app(app)
    compress.init_app(app)

    # إعداد اللغة
    def get_locale():
        lang = session.get("lang")
        if lang:
            return lang
        langs = app.config.get("LANGUAGES", ["ar", "fr", "en"])
        return request.accept_languages.best_match(langs) or langs[0]

    babel.init_app(app, locale_selector=get_locale)

    # متغيّرات متاحة داخل القوالب
    @app.context_processor
    def inject_globals():
        return {
            "get_locale": get_locale,
            "format_date": format_date,
            "format_datetime": format_datetime,
            "format_time": format_time,
            "config": app.config,
        }

    # صفحة 403
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("403.html"), 403

    # Health check
    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    # ✅ PWA: manifest.json من الجذر
    @app.route("/manifest.json")
    def manifest():
        resp = current_app.send_static_file("manifest.json")
        resp.headers["Content-Type"] = "application/manifest+json"
        return resp

    # ✅ PWA: service-worker.js من الجذر
    @app.route("/service-worker.js")
    def service_worker():
        resp = make_response(render_template("service-worker.js"))
        resp.headers["Content-Type"] = "application/javascript"
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    # فحص الـ DB عند الإقلاع
    with app.app_context():
        try:
            engine = db.engine
            pool_name = type(engine.pool).__name__
            status = engine.pool.status() if hasattr(engine.pool, "status") else "N/A"
            app.logger.info(f"DB engine={engine.name}, pool={pool_name}, status={status}")
        except Exception as e:
            app.logger.warning(f"DB pool introspection failed: {e}")

    # Route اختبار الكاش
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

    # ✅ تسجيل الـ blueprints (كلشي داخل create_app)
    from vigi.main.routes import main_bp
    app.register_blueprint(main_bp)

    try:
        from vigi.auth.routes import auth_bp
        app.register_blueprint(auth_bp, url_prefix="/auth")
    except Exception as e:
        app.logger.warning(f"auth blueprint not registered: {e}")

    try:
        from vigi.lots.routes import lots_bp
        app.register_blueprint(lots_bp, url_prefix="/lots")
    except Exception as e:
        app.logger.warning(f"lots blueprint not registered: {e}")

    try:
        from vigi.logs.routes import logs_bp
        app.register_blueprint(logs_bp, url_prefix="/logs")
    except Exception as e:
        app.logger.warning(f"logs blueprint not registered: {e}")

    # ✅ Register CLI commands (autoexport)
    try:
        from vigi.cli_autoexport import register_cli
        register_cli(app)
        app.logger.info("✅ CLI autoexport registered")
    except Exception as e:
        app.logger.warning(f"CLI autoexport not registered: {e}")

    return app
