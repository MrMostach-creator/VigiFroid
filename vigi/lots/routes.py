# ────────────────────────────────
# vigi/lots/routes.py  ✅ CLEAN FINAL (safe + no duplicates + manual PDF = auto-export PDF)
# ────────────────────────────────

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timedelta

import pytz
from PIL import Image
from sqlalchemy.exc import IntegrityError

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_babel import force_locale, get_locale, gettext as _
from flask_login import current_user, login_required
from functools import wraps

from vigi.extensions import cache, db
from vigi.forms import AppSettingsForm, LotForm
from vigi.services.reports import build_lots_pdf_from_lots
from models import AppSettings, Log, Lot


lots_bp = Blueprint("lots", __name__, url_prefix="/lots")


# ────────────────────────────────
# Time helpers (safe)
# ────────────────────────────────
# إذا عندك vigi/utils_time.py فيه get_now/get_today_date → غادي نستعملوه
# وإلا fallback هنا باش ما يطيحش التطبيق.
try:
    from vigi.utils_time import get_now, get_today_date  # type: ignore
except Exception:
    def get_now(tz=None):
        if not tz:
            tz = pytz.timezone(current_app.config.get("BABEL_DEFAULT_TIMEZONE", "Africa/Casablanca"))
        return datetime.now(tz)

    def get_today_date():
        return get_now().date()


# ────────────────────────────────
# صلاحيات الأدمن
# ────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, "role", None) != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ────────────────────────────────
# عرض كل الـ Lots (Pagination + إحصائيات)
# ────────────────────────────────
@lots_bp.route("/")
def index():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()

    query = Lot.query.order_by(Lot.expiry_date.asc())

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Lot.product_name.ilike(like)) |
            (Lot.lot_number.ilike(like)) |
            (Lot.pn.ilike(like))
        )

    today = get_today_date()

    if status == "valid":
        query = query.filter(Lot.expiry_date > today + timedelta(days=30))
    elif status == "warning":
        query = query.filter(Lot.expiry_date <= today + timedelta(days=30), Lot.expiry_date >= today)
    elif status == "expired":
        query = query.filter(Lot.expiry_date < today)

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 48, type=int)
    if per_page not in (12, 24, 48):
        per_page = 48

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    lots = pagination.items
    total = pagination.total
    pages = pagination.pages

    # Debug فقط فـ mode debug
    if current_app.debug:
        print("🔍 DEBUG => total =", total)
        print("🔍 DEBUG => per_page =", per_page)
        print("🔍 DEBUG => pages =", pages)
        print("🔍 DEBUG => lots count on this page =", len(lots))

    # Base query للإحصائيات (نفس الفلاتر)
    base_q = query.session.query(Lot)
    if q:
        like = f"%{q}%"
        base_q = base_q.filter(
            (Lot.product_name.ilike(like)) |
            (Lot.lot_number.ilike(like)) |
            (Lot.pn.ilike(like))
        )

    if status == "valid":
        base_q = base_q.filter(Lot.expiry_date > today + timedelta(days=30))
    elif status == "warning":
        base_q = base_q.filter(Lot.expiry_date <= today + timedelta(days=30), Lot.expiry_date >= today)
    elif status == "expired":
        base_q = base_q.filter(Lot.expiry_date < today)

    # status مؤقت للـ UI
    for lot in lots:
        st = "unknown"
        if lot.expiry_date:
            if lot.expiry_date < today:
                st = "expired"
            elif lot.expiry_date <= today + timedelta(days=30):
                st = "warning"
            else:
                st = "valid"
        setattr(lot, "temp_status", st)

    valid_count = base_q.filter(Lot.expiry_date > today + timedelta(days=30)).count()
    warning_count = base_q.filter(Lot.expiry_date <= today + timedelta(days=30), Lot.expiry_date >= today).count()
    expired_count = base_q.filter(Lot.expiry_date < today).count()

    resp = make_response(render_template(
        "index.html",
        lots=lots,
        q=q,
        status=status,
        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        valid_count=valid_count,
        warning_count=warning_count,
        expired_count=expired_count,
        lang=str(get_locale() or "fr"),
    ))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ────────────────────────────────
# إضافة Lot جديد
# ────────────────────────────────
@lots_bp.route("/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_lot():
    form = LotForm()
    if form.validate_on_submit():
        try:
            lot = Lot(
                lot_number=(form.lot_number.data or "").strip(),
                product_name=(form.product_name.data or "").strip(),
                type=(form.type.data or "").strip(),
                expiry_date=form.expiry_date.data,
                pn=(form.pn.data or "").strip(),
            )

            if form.image.data:
                image_file = form.image.data
                filename = f"img_{get_now().strftime('%Y%m%d%H%M%S')}.jpg"

                upload_dir = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.root_path, "static", "images")
                os.makedirs(upload_dir, exist_ok=True)

                image_path = os.path.join(upload_dir, filename)
                Image.open(image_file).convert("RGB").save(image_path, "JPEG", optimize=True, quality=80)
                lot.image = filename

            db.session.add(lot)
            db.session.flush()
            db.session.add(Log(action=f"Added lot {lot.lot_number}", user_id=current_user.id))
            db.session.commit()

            cache.delete("logs_page")
            cache.clear()

            flash(_("Product added successfully."), "success")
            resp = redirect(url_for("lots.index"))
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            return resp

        except IntegrityError:
            db.session.rollback()
            flash(_("LOT number or PN already exists."), "danger")
        except Exception as e:
            db.session.rollback()
            flash(_("Error while adding: %(err)s", err=str(e)), "danger")

    return render_template("add.html", form=form)


# ────────────────────────────────
# تعديل Lot
# ────────────────────────────────
@lots_bp.route("/edit/<int:lot_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_lot(lot_id):
    lot = Lot.query.get_or_404(lot_id)
    form = LotForm(obj=lot)
    formatted_expiry_date = lot.expiry_date.strftime("%Y-%m-%d") if lot.expiry_date else ""

    if form.validate_on_submit():
        try:
            lot.lot_number = (form.lot_number.data or "").strip()
            lot.product_name = (form.product_name.data or "").strip()
            lot.type = (form.type.data or "").strip()
            lot.pn = (form.pn.data or "").strip()
            lot.expiry_date = form.expiry_date.data

            if form.image.data:
                image_file = form.image.data
                filename = f"img_{get_now().strftime('%Y%m%d%H%M%S')}.jpg"

                upload_dir = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.root_path, "static", "images")
                os.makedirs(upload_dir, exist_ok=True)

                image_path = os.path.join(upload_dir, filename)
                Image.open(image_file).convert("RGB").save(image_path, "JPEG", optimize=True, quality=80)
                lot.image = filename

            db.session.add(Log(action=f"Edited lot {lot.lot_number}", user_id=current_user.id))
            db.session.commit()

            cache.delete("logs_page")
            cache.clear()

            flash(_("Product updated successfully."), "success")
            resp = redirect(url_for("lots.index"))
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            return resp

        except IntegrityError:
            db.session.rollback()
            flash(_("LOT number or PN already in use."), "danger")
        except Exception as e:
            db.session.rollback()
            flash(_("Error while editing: %(err)s", err=str(e)), "danger")

    return render_template("edit.html", form=form, lot=lot, formatted_expiry_date=formatted_expiry_date)


# ────────────────────────────────
# حذف Lot
# ────────────────────────────────
@lots_bp.route("/delete/<int:lot_id>", methods=["POST"])
@login_required
@admin_required
def delete_lot(lot_id):
    try:
        lot = Lot.query.get_or_404(lot_id)
        db.session.add(Log(action=f"Deleted lot {lot.lot_number}", user_id=current_user.id))
        db.session.delete(lot)
        db.session.commit()

        cache.delete("logs_page")
        cache.clear()
        flash(_("Product deleted successfully."), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error while deleting: %(err)s", err=str(e)), "danger")

    resp = redirect(url_for("lots.index"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# ────────────────────────────────
# إعدادات التصدير الشهري (Admin فقط)
# ────────────────────────────────
@lots_bp.route("/export-settings", methods=["GET", "POST"])
@login_required
@admin_required
def export_settings():
    settings = AppSettings.get()
    form = AppSettingsForm(obj=settings)

    # Backward compatibility: on GET, if multi empty show legacy email
    if request.method == "GET":
        if not (form.quality_emails.data or "").strip() and (settings.quality_email or "").strip():
            form.quality_emails.data = settings.quality_email

    if form.validate_on_submit():
        enabled = bool(form.export_enabled.data)

        # Always keep language saved (even if disabled)
        lang_value = (form.report_language.data or settings.report_language or "fr").strip().lower()
        if lang_value not in {"ar", "fr", "en"}:
            lang_value = settings.report_language or "fr"

        settings.report_language = lang_value
        settings.auto_export_enabled = enabled

        # If auto-export is ON, update dependent fields
        if enabled:
            emails_value = (form.quality_emails.data or "").strip()
            day_value = form.export_day.data
            fmt_value = (form.export_format.data or "pdf").strip().lower()

            if fmt_value not in {"pdf", "csv"}:
                fmt_value = "pdf"

            # Save multi emails
            settings.quality_emails = emails_value

            # Keep legacy (first email) for backward compatibility
            from vigi.utils import parse_emails
            valid_list = parse_emails(emails_value)
            settings.quality_email = valid_list[0] if valid_list else None

            # Extra safety: avoid None / bad int (form should already validate)
            settings.export_day = int(day_value) if day_value else settings.export_day
            settings.export_format = fmt_value

        # ✅ Commit with safety (prevents 500 on DB errors)
        try:
            db.session.add(settings)
            db.session.commit()
            flash(_("Settings updated successfully."), "success")
            return redirect(url_for("lots.export_settings"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[EXPORT_SETTINGS] DB commit failed: {e}")
            flash(_("Error saving settings. Please try again."), "danger")
            return redirect(url_for("lots.export_settings"))

    return render_template("export_settings.html", form=form, settings=settings)

# ────────────────────────────────
# تصدير إلى CSV
# ────────────────────────────────
@lots_bp.route("/export", methods=["GET"])
@login_required
def export_csv():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()

    query = Lot.query.order_by(Lot.expiry_date.asc(), Lot.product_name.asc())

    if q:
        query = query.filter(
            (Lot.product_name.ilike(f"%{q}%")) |
            (Lot.lot_number.ilike(f"%{q}%")) |
            (Lot.pn.ilike(f"%{q}%"))
        )

    today = get_today_date()
    if status == "valid":
        query = query.filter(Lot.expiry_date > today + timedelta(days=30))
    elif status == "warning":
        query = query.filter(Lot.expiry_date <= today + timedelta(days=30), Lot.expiry_date >= today)
    elif status == "expired":
        query = query.filter(Lot.expiry_date < today)

    lots = query.yield_per(100)
    cur_locale = str(get_locale() or "fr")

    with force_locale(cur_locale):
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")

        writer.writerow([_("Product Name"), _("PN"), _("Lot Number"), _("Expiry Date"), _("Product Type")])

        for lot in lots:
            writer.writerow([
                lot.product_name or "",
                lot.pn or "",
                lot.lot_number or "",
                lot.expiry_date.strftime("%Y-%m-%d") if lot.expiry_date else "",
                lot.type or "",
            ])

        output.seek(0)
        filename = f"VigiFroid_Export_{get_now().strftime('%Y%m%d_%H%M%S')}.csv"
        resp = send_file(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name=filename,
        )
        resp.headers["Content-Language"] = cur_locale
        return resp


# ────────────────────────────────
# تصدير إلى PDF ✅ (Manual PDF = Auto-export PDF 100%)
# ────────────────────────────────
@lots_bp.route("/export/pdf", methods=["GET"])
@login_required
def export_pdf():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    force_lang = request.args.get("lang")

    cur_locale = force_lang if force_lang in ["ar", "fr", "en"] else str(get_locale() or "fr")
    session["lang"] = cur_locale

    today = get_today_date()
    query = Lot.query.order_by(Lot.expiry_date.asc(), Lot.product_name.asc())

    if q:
        query = query.filter(
            (Lot.product_name.ilike(f"%{q}%")) |
            (Lot.lot_number.ilike(f"%{q}%")) |
            (Lot.pn.ilike(f"%{q}%"))
        )

    if status == "valid":
        query = query.filter(Lot.expiry_date > today + timedelta(days=30))
    elif status == "warning":
        query = query.filter(Lot.expiry_date <= today + timedelta(days=30), Lot.expiry_date >= today)
    elif status == "expired":
        query = query.filter(Lot.expiry_date < today)

    lots = query.all()

    pdf_bytes = build_lots_pdf_from_lots(lots, lang_code=cur_locale, today=today)
    buf = io.BytesIO(pdf_bytes)
    buf.seek(0)

    filename = f"VigiFroid_Report_{get_now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)


# ────────────────────────────────
# API JSON للـ Lots (للاستخدام الداخلي)
# ────────────────────────────────
@lots_bp.get("/api.json")
@login_required
def api_json():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()

    query = Lot.query.order_by(Lot.expiry_date.asc(), Lot.product_name.asc())

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Lot.product_name.ilike(like)) |
            (Lot.lot_number.ilike(like)) |
            (Lot.pn.ilike(like))
        )

    today = get_today_date()
    if status == "valid":
        query = query.filter(Lot.expiry_date > today + timedelta(days=30))
    elif status == "warning":
        query = query.filter(Lot.expiry_date.between(today, today + timedelta(days=30)))
    elif status == "expired":
        query = query.filter(Lot.expiry_date < today)

    rows = query.with_entities(
        Lot.id,
        Lot.product_name,
        Lot.pn,
        Lot.lot_number,
        Lot.expiry_date,
        Lot.type,
        Lot.image,
    ).all()

    def to_dict(r):
        return {
            "id": r.id,
            "product_name": r.product_name or "",
            "pn": r.pn or "",
            "lot_number": r.lot_number or "",
            "expiry_date": r.expiry_date.strftime("%Y-%m-%d") if r.expiry_date else "",
            "type": r.type or "",
            "image": r.image or "",
        }

    return jsonify([to_dict(r) for r in rows])
