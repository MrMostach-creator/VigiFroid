# 📁 app.py — النسخة النهائية المصححة 100%
from flask import (
    flash, redirect, send_from_directory, request,
    render_template, url_for, current_app, make_response
)
import os, logging
from logging.handlers import RotatingFileHandler
from flask_login import current_user
from vigi import create_app
from vigi.extensions import db
from flask_wtf.csrf import CSRFError

# ==========================================================
# 🧩 إعداد نظام السجلات
# ==========================================================
def setup_logging(app):
    log_level = logging.DEBUG if app.debug else logging.INFO
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    fh = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=10)
    fh.setLevel(logging.ERROR)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s'))

    app.logger.addHandler(ch)
    app.logger.addHandler(fh)
    app.logger.setLevel(log_level)
    app.logger.info("Logging setup complete.")


# ==========================================================
# 🚀 إنشاء التطبيق
# ==========================================================
app = create_app("config.Config")
setup_logging(app)


# ==========================================================
# 🔐 Login redirection
# ==========================================================
@app.route("/login")
def redirect_to_login():
    return redirect(url_for("auth.login"))

@app.get("/__routes")
def __routes():
    return {"routes": [str(r) for r in app.url_map.iter_rules()]}



# ==========================================================
# 🎨 Favicon
# ==========================================================
@app.route('/favicon.ico')
def favicon():
    icon_dir = os.path.join(app.root_path, 'static', 'images')
    icon_path = os.path.join(icon_dir, 'favicon.ico')
    if not os.path.exists(icon_path):
        current_app.logger.warning(f"Favicon not found: {icon_path}")
        return "Favicon not found", 404
    return send_from_directory(icon_dir, 'favicon.ico', mimetype='image/vnd.microsoft.icon')


# ==========================================================
# ⚙️ Service Worker
# ==========================================================
@app.route('/service-worker.js')
def serve_service_worker():
    resp = make_response(render_template('service-worker.js'))
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp



# ==========================================================
# 📴 Offline page
# ==========================================================
@app.route('/offline.html')
def offline_page():
    offline_path = os.path.join(current_app.static_folder, 'offline.html')
    if not os.path.exists(offline_path):
        current_app.logger.error(f"Offline page not found at: {offline_path}")
        return "Offline page not found", 404

    resp = send_from_directory(current_app.static_folder, 'offline.html', mimetype='text/html')
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp


# ==========================================================
# 🪵 Logging requests
# ==========================================================
@app.after_request
def log_request(response):
    if request.path.startswith("/.well-known/appspecific"):
        return response
    user = current_user.username if current_user.is_authenticated else "Anonymous"
    current_app.logger.info(
        f"{request.method} {request.url} [{response.status_code}] "
        f"User: {user} | IP: {request.remote_addr} | UA: {request.user_agent}"
    )
    return response


# ==========================================================
# 🧱 Error Handlers
# ==========================================================
@app.errorhandler(404)
def not_found_error(error):
    current_app.logger.warning(f"404 Not Found: {request.url}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    try:
        db.session.rollback()
        current_app.logger.error(f"500 Internal Error at {request.url}: {error}")
    except Exception as e:
        current_app.logger.critical(f"Rollback failed: {e}")
    return render_template('500.html'), 500


# ==========================================================
# 🧩 CSRF Error
# ==========================================================
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash("⚠️ انتهت صلاحية الجلسة، المرجو إعادة المحاولة.", "danger")
    current_app.logger.warning(f"CSRF Error: {request.url}")
    return redirect(request.referrer or url_for("main.index"))


# ==========================================================
# ▶️ Run
# ==========================================================
if __name__ == "__main__":
    app.run(debug=True)
