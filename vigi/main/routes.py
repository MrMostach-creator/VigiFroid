# ─────────────────────────────────────────────────────────
# vigi/main/routes.py  —  FINAL
# ─────────────────────────────────────────────────────────
from datetime import date, timedelta
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from flask import (
    Blueprint, render_template, request, current_app,
    redirect, url_for, session, make_response, jsonify
)
from flask_login import current_user
from sqlalchemy import func, text
from flask_babel import get_locale as babel_get_locale

from models import Lot
from vigi.extensions import cache
from flask_babel import gettext as _


# Blueprint واحد فقط
main_bp = Blueprint("main", __name__)

# رجوع آمن لنفس الصفحة بعد تغيير اللغة
def _safe_referrer():
    ref = request.referrer or ""
    try:
        netloc = urlparse(ref).netloc
        if not ref or (netloc and netloc != request.host):
            return url_for("main.index")
    except Exception:
        return url_for("main.index")
    return ref

# الصفحة الرئيسية
@main_bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 48, type=int)

    today = date.today()

    # --------- الاستعلام الأساسي ---------
    query = Lot.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Lot.product_name.ilike(like)) |
            (Lot.pn.ilike(like)) |
            (Lot.lot_number.ilike(like))
        )

    if status == "valid":
        query = query.filter(Lot.expiry_date > today + timedelta(days=30))
    elif status == "warning":
        query = query.filter(
            Lot.expiry_date >= today,
            Lot.expiry_date <= today + timedelta(days=30)
        )
    elif status == "expired":
        query = query.filter(Lot.expiry_date < today)

    # --------- Pagination ---------
    pagination = query.order_by(Lot.expiry_date.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    lots = pagination.items
    total = pagination.total
    pages = pagination.pages

    # --------- حساب الحالات ---------
    base_q = Lot.query
    if q:
        like = f"%{q}%"
        base_q = base_q.filter(
            (Lot.product_name.ilike(like)) |
            (Lot.pn.ilike(like)) |
            (Lot.lot_number.ilike(like))
        )

    valid_count = base_q.filter(Lot.expiry_date > today + timedelta(days=30)).count()
    warning_count = base_q.filter(
        Lot.expiry_date >= today,
        Lot.expiry_date <= today + timedelta(days=30)
    ).count()
    expired_count = base_q.filter(Lot.expiry_date < today).count()

    # --------- تحديد status لكل lot ---------
    for lot in lots:
        if not lot.expiry_date:
            lot.temp_status = "unknown"
        elif lot.expiry_date < today:
            lot.temp_status = "expired"
        elif (lot.expiry_date - today).days <= 30:
            lot.temp_status = "warning"
        else:
            lot.temp_status = "valid"

    return render_template(
        "index.html",
        lots=lots,
        q=q,
        status=status,
        page=page,
        per_page=per_page,
        pages=pages,
        total=total,
        valid_count=valid_count,
        warning_count=warning_count,
        expired_count=expired_count,
        lang=str(babel_get_locale() or "fr")
    )



# تغيـير اللغة (الـendpoint بالاسم اللي كتناديه فـ base.html)

@main_bp.route("/change_language/<lang_code>", methods=["GET"], endpoint="change_language")
def change_language(lang_code):
    allowed = tuple(current_app.config.get("LANGUAGES", ["ar", "fr", "en"]))  # ✅ من الكونفيغ
    if lang_code not in allowed:
        lang_code = current_app.config.get("BABEL_DEFAULT_LOCALE", "fr")

    session["lang"] = lang_code
    session.permanent = True

    back = _safe_referrer()
    try:
        parts = urlparse(back)
        q = dict(parse_qsl(parts.query, keep_blank_values=True))
        q.pop("ts", None)                # ✅ إزالة الأثر القديم
        q["lang"] = lang_code
        q["ts"] = str(int(time.time()))  # ✅ بَسطر واحد كل مرة
        new_query = urlencode(q, doseq=False)
        back_clean = urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment))
    except Exception:
        back_clean = url_for("main.index", lang=lang_code, ts=int(time.time()))

    resp = make_response(redirect(back_clean))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

# ديباغ: باش نتاكد واش السشن كتتشجل وبابل كيقراها
@main_bp.get("/_locale")
def debug_locale():
    sess = session.get("lang")
    cur = str(babel_get_locale()) if babel_get_locale() else None
    return jsonify({"session": sess, "babel": cur})
