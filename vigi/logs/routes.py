# ────────────────────────────────────────────────
# 📁 vigi/logs/routes.py — نسخة نهائية ومستقرة
# تعمل مع PostgreSQL وSQLAlchemy وFlask-Caching
# ────────────────────────────────────────────────

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from vigi.extensions import cache
from models import Log, User
from datetime import datetime

logs_bp = Blueprint("logs", __name__, url_prefix="/logs")

@logs_bp.route("/")
@login_required
@cache.cached(timeout=60, key_prefix="logs_page")  # ✅ تحديث كل دقيقة
def logs():
    # 👑 فقط الأدمن يمكنه الوصول
    if current_user.role != "admin":
        flash("❌ Unauthorized access.", "danger")
        return redirect(url_for("main.index"))

    # 🧾 جلب السجلات الأخيرة
    logs = (
        Log.query.join(User, Log.user_id == User.id)
        .add_columns(Log.action, Log.timestamp, User.username)
        .order_by(Log.timestamp.desc())
        .all()
    )

    # 🔄 تحويل النتائج إلى قائمة من dicts
    logs_data = [
        {
            "action": log.action,
            "timestamp": log.timestamp or datetime.utcnow(),
            "username": log.username
        }
        for log in logs
    ]

    # ⚠️ إذا لا توجد سجلات
    if not logs_data:
        flash("⚠️ لا توجد سجلات حالياً.", "info")

    return render_template("logs.html", logs=logs_data)
