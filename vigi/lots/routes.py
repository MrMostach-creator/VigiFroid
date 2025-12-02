
# ────────────────────────────────
# vigi/lots/routes.py 
# ────────────────────────────────

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, session,
    abort, send_file, make_response, current_app, jsonify
)
from flask_login import login_required, current_user
from functools import wraps
from vigi.extensions import db, cache
from models import Lot, Log
from vigi.forms import LotForm
from datetime import datetime, timedelta
import csv
import io
import os
from PIL import Image
from sqlalchemy.exc import IntegrityError
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, landscape
from flask_babel import gettext as _, format_date, get_locale, force_locale
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# Arabic shaping 
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_SUPPORT = True
except Exception:
    arabic_reshaper = None
    get_display = None
    HAS_ARABIC_SUPPORT = False

lots_bp = Blueprint("lots", __name__, url_prefix="/lots")    

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
# عرض كل الـ Lots (مع Pagination + إحصائيات)
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

    today = datetime.utcnow().date()
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
    

    print("🔍 DEBUG => total =", total)
    print("🔍 DEBUG => per_page =", per_page)
    print("🔍 DEBUG => pages =", pages)
    print("🔍 DEBUG => lots count on this page =", len(lots))

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
        lots=lots, q=q, status=status, page=page, per_page=per_page, total=total, pages=pages,
        valid_count=valid_count, warning_count=warning_count, expired_count=expired_count,
        lang=str(get_locale() or "fr")
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
                lot_number=form.lot_number.data.strip(),
                product_name=form.product_name.data.strip(),
                type=form.type.data.strip(),
                expiry_date=form.expiry_date.data,
                pn=form.pn.data.strip(),
                quantity=form.quantity.data,
            )

            if form.image.data:
                image_file = form.image.data
                filename = f"img_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
                os.makedirs("static/images", exist_ok=True)
                image_path = os.path.join("static/images", filename)
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
            lot.lot_number = form.lot_number.data.strip()
            lot.product_name = form.product_name.data.strip()
            lot.type = form.type.data.strip()
            lot.pn = form.pn.data.strip()
            lot.quantity = form.quantity.data
            lot.expiry_date = form.expiry_date.data

            if form.image.data:
                image_file = form.image.data
                filename = f"img_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
                os.makedirs("static/images", exist_ok=True)
                image_path = os.path.join("static/images", filename)
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
# تصدير إلى CSV
# ────────────────────────────────
@lots_bp.route('/export', methods=['GET'])
@login_required
def export_csv():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    query = Lot.query.order_by(Lot.expiry_date.asc(), Lot.product_name.asc())

    if q:
        query = query.filter(
            (Lot.product_name.ilike(f"%{q}%")) |
            (Lot.lot_number.ilike(f"%{q}%")) |
            (Lot.pn.ilike(f"%{q}%"))
        )

    today = datetime.utcnow().date()
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
        writer = csv.writer(output, delimiter=';')

        writer.writerow([
            _('Product Name'), _('PN'), _('Lot Number'),
            _('Expiry Date'), _('Product Type')
        ])

        for lot in lots:
            writer.writerow([
                lot.product_name or '',
                lot.pn or '',
                lot.lot_number or '',
                lot.expiry_date.strftime("%Y-%m-%d") if lot.expiry_date else '',
                lot.type or ''
            ])

        output.seek(0)
        filename = f"VigiFroid_Export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        resp = send_file(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name=filename
        )
        resp.headers['Content-Language'] = cur_locale
        return resp

# ────────────────────────────────
# تصدير إلى PDF (عربي 100% بدون مربعات)
# ────────────────────────────────
# ---------- PDF EXPORT ----------
@lots_bp.route('/export/pdf', methods=['GET'])
@login_required
def export_pdf():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    force_lang = request.args.get("lang")

    cur_locale = force_lang if force_lang in ['ar','fr','en'] else str(get_locale() or "fr")
    session['lang'] = cur_locale
    is_ar = cur_locale.startswith("ar")

    # ---------- تسجيل الخطوط داخل الـ view ----------
    if is_ar:
        font_dir = os.path.join(current_app.static_folder, "fonts")
        reg_path  = os.path.join(font_dir, "NotoNaskhArabic-Regular.ttf")
        bold_path = os.path.join(font_dir, "NotoNaskhArabic-Bold.ttf")
        try:
            # ✅ فحص آمن لأسماء الخطوط المسجّلة بدل getFont(..)
            registered = set(pdfmetrics.getRegisteredFontNames())

            if "NotoNaskhArabic" not in registered:
                pdfmetrics.registerFont(TTFont("NotoNaskhArabic", reg_path))
            if "NotoNaskhArabic-Bold" not in registered:
                pdfmetrics.registerFont(TTFont("NotoNaskhArabic-Bold", bold_path))

            # ✅ تسجيل عائلة الخط لضمان تعيين الوزن العريض تلقائيًا
            pdfmetrics.registerFontFamily(
                "NotoNaskhArabic",
                normal="NotoNaskhArabic",
                bold="NotoNaskhArabic-Bold",
                italic="NotoNaskhArabic",
                boldItalic="NotoNaskhArabic-Bold"
            )

        except Exception as e:
            current_app.logger.error(f"Font registration failed: {e}")
            is_ar = False   # fallback إلى Helvetica فقط إذا فشلت القراءة فعلاً

    font_regular = "NotoNaskhArabic" if is_ar else "Helvetica"
    font_bold    = "NotoNaskhArabic-Bold" if is_ar else "Helvetica-Bold"

    # ---------- استعلام البيانات ----------
    query = Lot.query.order_by(Lot.expiry_date.asc(), Lot.product_name.asc())
    today = datetime.utcnow().date()
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

    # ---------- بناء الـ PDF ----------
    with force_locale(cur_locale):
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                                leftMargin=20, rightMargin=20,
                                topMargin=30, bottomMargin=20)
        elements = []
        styles = getSampleStyleSheet()

        def _p(text, font_name, size=9, align=0, bold=False):
            if is_ar and HAS_ARABIC_SUPPORT and text:
                text = get_display(arabic_reshaper.reshape(text))
            style = ParagraphStyle(
                name='Custom',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=size,
                alignment=align,
                leading=size+2,
                direction='RTL' if is_ar else 'LTR',
                rightIndent=4 if is_ar else 0,
                leftIndent=4 if not is_ar else 0,
                wordWrap='RTL' if is_ar else None   # ✅ تحسين التفاف النص العربي
            )
            tag = f"<font name='{font_bold}'><b>{text}</b></font>" if bold else text
            return Paragraph(tag.replace('&', '&amp;'), style)

        # عنوان
        elements.append(_p(_("VigiFroid Lots Report"), font_bold, size=16, align=1, bold=True))
        elements.append(Spacer(1, 12))

        # رؤوس الجدول
        headers = [_('Product Name'), _('PN'), _('Lot Number'), _('Expiry Date'), _('Product Type'), _('Status')]
        header_row = [_p(h, font_bold, bold=True, align=2 if is_ar else 1) for h in headers]
        data = [header_row]

        # الصفوف
        for lot in lots:
            state = _("Expired") if lot.expiry_date and lot.expiry_date < today else \
                    _("Warning") if lot.expiry_date and lot.expiry_date <= today + timedelta(days=30) else \
                    _("Valid")
            expiry = format_date(lot.expiry_date) if lot.expiry_date else ""
            row = [lot.product_name or "", lot.pn or "", lot.lot_number or "", expiry, lot.type or "", state]
            data.append([_p(cell, font_regular, align=2 if is_ar else 1) for cell in row])

        table = Table(data, repeatRows=1, colWidths=[140, 80, 90, 80, 75, 70])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.2, 0.4, 0.8)),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), font_bold),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('ALIGN', (0,1), (-1,-1), 'RIGHT' if is_ar else 'CENTER'),
            ('FONTNAME', (0,1), (-1,-1), font_regular),
        ]))

        # تلوين الصفوف حسب الحالة
        for i, lot in enumerate(lots, 1):
            col = colors.Color(1, 0.8, 0.8) if lot.expiry_date and lot.expiry_date < today else \
                  colors.Color(1, 1, 0.8)   if lot.expiry_date and lot.expiry_date <= today + timedelta(days=30) else \
                  colors.Color(0.8, 1, 0.8)
            table.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), col)]))

        elements.append(table)
        doc.build(elements)
        buf.seek(0)

        filename = f"VigiFroid_Report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(buf, mimetype="application/pdf",
                         as_attachment=True, download_name=filename)

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

    today = datetime.utcnow().date()
    if status == "valid":
        query = query.filter(Lot.expiry_date > today + timedelta(days=30))
    elif status == "warning":
        query = query.filter(Lot.expiry_date.between(today, today + timedelta(days=30)))
    elif status == "expired":
        query = query.filter(Lot.expiry_date < today)

    rows = query.with_entities(
        Lot.id, Lot.product_name, Lot.pn, Lot.lot_number, Lot.expiry_date, Lot.type, Lot.image
    ).all()

    def to_dict(r):
        return {
            "id": r.id,
            "product_name": r.product_name or "",
            "pn": r.pn or "",
            "lot_number": r.lot_number or "",
            "expiry_date": r.expiry_date.strftime("%Y-%m-%d") if r.expiry_date else "",
            "type": r.type or "",
            "image": r.image or ""
        }
    return jsonify([to_dict(r) for r in rows])


