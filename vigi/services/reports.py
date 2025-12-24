# vigi/services/reports.py

from datetime import datetime, date, timedelta
import io
import csv
import os

from flask import current_app
from flask_mail import Message
from flask_babel import force_locale, gettext as _
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from vigi.extensions import mail, db
from models import Lot, AppSettings, Log
from xml.sax.saxutils import escape

# Arabic shaping (اختياري)
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_SUPPORT = True
except Exception:
    arabic_reshaper = None
    get_display = None
    HAS_ARABIC_SUPPORT = False


# ────────────────────────────────
# Helpers
# ────────────────────────────────
def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def get_settings_row():
    """Singleton settings row."""
    s = AppSettings.query.first()
    if not s:
        s = AppSettings()
        db.session.add(s)
        db.session.commit()
    return s


def _normalize_lang(lang_code: str, fallback: str = "fr") -> str:
    lang = (lang_code or "").strip().lower() or fallback
    return lang if lang in ("ar", "fr", "en") else fallback


def _ensure_arabic_fonts() -> bool:
    """
    Register Arabic fonts if possible.
    Returns True if fonts are usable, False if we should fallback to Helvetica.
    """
    try:
        font_dir = os.path.join(current_app.static_folder, "fonts")
        reg_path = os.path.join(font_dir, "NotoNaskhArabic-Regular.ttf")
        bold_path = os.path.join(font_dir, "NotoNaskhArabic-Bold.ttf")

        registered = set(pdfmetrics.getRegisteredFontNames())
        if "NotoNaskhArabic" not in registered:
            pdfmetrics.registerFont(TTFont("NotoNaskhArabic", reg_path))
        if "NotoNaskhArabic-Bold" not in registered:
            pdfmetrics.registerFont(TTFont("NotoNaskhArabic-Bold", bold_path))

        pdfmetrics.registerFontFamily(
            "NotoNaskhArabic",
            normal="NotoNaskhArabic",
            bold="NotoNaskhArabic-Bold",
            italic="NotoNaskhArabic",
            boldItalic="NotoNaskhArabic-Bold",
        )
        return True
    except Exception as e:
        current_app.logger.error(f"[REPORT] Font registration failed: {e}")
        return False


# ────────────────────────────────
# CSV Builder
# ────────────────────────────────
def build_lots_csv(lang_code: str) -> bytes:
    lang_code = _normalize_lang(lang_code, current_app.config.get("BABEL_DEFAULT_LOCALE", "fr"))

    with force_locale(lang_code):
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")

        writer.writerow([
            _("Product Name"),
            _("PN"),
            _("Lot Number"),
            _("Expiry Date"),
            _("Product Type"),
            _("Status"),
        ])

        today = date.today()
        lots = Lot.query.order_by(Lot.expiry_date.asc(), Lot.product_name.asc()).all()

        for lot in lots:
            if lot.expiry_date and lot.expiry_date < today:
                state = _("Expired")
            elif lot.expiry_date and lot.expiry_date <= today + timedelta(days=30):
                state = _("Warning")
            else:
                state = _("Valid")

            writer.writerow([
                lot.product_name or "",
                lot.pn or "",
                lot.lot_number or "",
                lot.expiry_date.isoformat() if lot.expiry_date else "",
                lot.type or "",
                state,
            ])

        return output.getvalue().encode("utf-8-sig")


# ────────────────────────────────
# PDF Builder (Reusable)  ✅ with row colors
# ────────────────────────────────
def build_lots_pdf_from_lots(lots, lang_code: str, today: date = None) -> bytes:
    if today is None:
        today = date.today()

    lang_code = _normalize_lang(lang_code, current_app.config.get("BABEL_DEFAULT_LOCALE", "fr"))
    is_ar = lang_code.startswith("ar")

    # Fonts
    if is_ar:
        if not _ensure_arabic_fonts():
            is_ar = False  # fallback

    font_regular = "NotoNaskhArabic" if is_ar else "Helvetica"
    font_bold = "NotoNaskhArabic-Bold" if is_ar else "Helvetica-Bold"

    styles = getSampleStyleSheet()

    def _p(text, font_name, size=9, align=1, bold=False):
        raw = text or ""

        # Arabic shaping
        if is_ar and HAS_ARABIC_SUPPORT and raw:
            raw = get_display(arabic_reshaper.reshape(raw))

        safe_text = escape(raw)

        style = ParagraphStyle(
            name="Custom",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=size,
            leading=size + 2,
            alignment=align,
            direction="RTL" if is_ar else "LTR",
            wordWrap="RTL" if is_ar else None,
        )

        if bold:
            return Paragraph(f"<font name='{font_bold}'><b>{safe_text}</b></font>", style)
        return Paragraph(safe_text, style)

    with force_locale(lang_code):
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            leftMargin=20,
            rightMargin=20,
            topMargin=30,
            bottomMargin=20,
        )

        elements = []
        elements.append(_p(_("VigiFroid Lots Report"), font_bold, size=16, align=1, bold=True))
        elements.append(Spacer(1, 12))

        headers = [
            _("Product Name"),
            _("PN"),
            _("Lot Number"),
            _("Expiry Date"),
            _("Product Type"),
            _("Status"),
        ]
        data = [[_p(h, font_bold, bold=True, align=2 if is_ar else 1) for h in headers]]

        # Track status per row to color it
        status_keys = []

        for lot in lots:
            if lot.expiry_date and lot.expiry_date < today:
                status_keys.append("expired")
                state = _("Expired")
            elif lot.expiry_date and lot.expiry_date <= today + timedelta(days=30):
                status_keys.append("warning")
                state = _("Warning")
            else:
                status_keys.append("valid")
                state = _("Valid")

            row = [
                lot.product_name or "",
                lot.pn or "",
                lot.lot_number or "",
                lot.expiry_date.strftime("%Y-%m-%d") if lot.expiry_date else "",
                lot.type or "",
                state,
            ]
            data.append([_p(c, font_regular, align=2 if is_ar else 1) for c in row])

        table = Table(data, repeatRows=1, colWidths=[160, 90, 110, 100, 110, 90])

        # Base styles
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.4, 0.8)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTNAME", (0, 1), (-1, -1), font_regular),
        ]

        # Row coloring (like manual export)
        bg_map = {
            "expired": colors.Color(1, 0.8, 0.8),  # light red
            "warning": colors.Color(1, 1, 0.8),    # light yellow
            "valid": colors.Color(0.8, 1, 0.8),    # light green
        }
        # rows start at index 1 (index 0 is header)
        for i, key in enumerate(status_keys, start=1):
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg_map.get(key, colors.white)))

        table.setStyle(TableStyle(style_cmds))
        elements.append(table)

        doc.build(elements)
        return buf.getvalue()


def build_lots_pdf(lang_code: str) -> bytes:
    """Auto-export uses this."""
    lots = Lot.query.order_by(Lot.expiry_date.asc(), Lot.product_name.asc()).all()
    return build_lots_pdf_from_lots(lots, lang_code)


# ────────────────────────────────
# Auto Export
# ────────────────────────────────
def run_monthly_auto_export(lang_code: str = None, today: date = None) -> bool:
    """
    Used by CLI/Task Scheduler.
    Sends report only if today == export_day and not already sent this month.
    """
    settings = get_settings_row()

    if not settings.auto_export_enabled:
        current_app.logger.info("[AUTOEXPORT] disabled")
        return False

    if not settings.quality_email:
        current_app.logger.warning("[AUTOEXPORT] missing quality_email")
        return False

    if today is None:
        today = date.today()

    # Only on export_day
    if int(today.day) != int(settings.export_day):
        current_app.logger.info(
            f"[AUTOEXPORT] not today (today={today.day}, export_day={settings.export_day})"
        )
        return False

    # Prevent duplicate in same month
    mk = _month_key(today)
    if settings.last_export_month == mk:
        current_app.logger.info(f"[AUTOEXPORT] already sent for {mk}")
        return False

    # ✅ Language priority: CLI override > Export Settings (report_language) > default
    default_lang = current_app.config.get("BABEL_DEFAULT_LOCALE", "fr")
    if lang_code:
        lang_code = _normalize_lang(lang_code, default_lang)
    else:
        lang_code = _normalize_lang(getattr(settings, "report_language", None), default_lang)

    current_app.logger.info(f"[AUTOEXPORT] using lang_code={lang_code} (report_language={getattr(settings, 'report_language', None)})")

    # Format
    fmt = (settings.export_format or "pdf").strip().lower()
    if fmt not in ("pdf", "csv"):
        fmt = "pdf"

    # Build file
    if fmt == "csv":
        file_bytes = build_lots_csv(lang_code)
        filename = f"VigiFroid_Report_{mk}.csv"
        mimetype = "text/csv; charset=utf-8"
    else:
        file_bytes = build_lots_pdf(lang_code)  # ✅ now colored
        filename = f"VigiFroid_Report_{mk}.pdf"
        mimetype = "application/pdf"

    # Localized email
    with force_locale(lang_code):
        subject = _("VigiFroid · Monthly lots report")
        body = _("Please find attached the monthly lots export from VigiFroid.")

    msg = Message(subject=subject, recipients=[settings.quality_email])
    msg.body = body
    msg.attach(filename, mimetype, file_bytes)

    try:
        mail.send(msg)

        # Update anti-duplicate fields
        settings.last_export_month = mk
        settings.last_export_at = datetime.utcnow()
        db.session.add(settings)

        # Log
        db.session.add(Log(action=f"Auto export sent ({fmt}) to {settings.quality_email}", user_id=None))

        db.session.commit()

        current_app.logger.info(f"[AUTOEXPORT] sent to {settings.quality_email} ({fmt})")
        return True

    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"[AUTOEXPORT] send failed: {exc}")
        return False
