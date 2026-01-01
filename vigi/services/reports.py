# vigi/services/reports.py  ✅ FINAL (dates dd/MM/YYYY + multi recipients + professional email)

from __future__ import annotations

from datetime import datetime, date, timedelta
import io
import csv
import os
from typing import Iterable, List, Optional

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


def _fmt_date(d: Optional[date]) -> str:
    """
    Unified date format across languages: dd/MM/YYYY
    Example: 29/12/2025
    """
    if not d:
        return ""
    # d can be date or datetime (date() works for both)
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%d/%m/%Y")


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


def _get_today_date() -> date:
    """
    Prefer app timezone helper if available; fallback to date.today().
    """
    try:
        from vigi.utils_time import get_today_date  # type: ignore
        return get_today_date()
    except Exception:
        return date.today()


def get_settings_row() -> AppSettings:
    """
    Singleton settings row.
    Uses AppSettings.get() if exists, else creates the first row.
    """
    getter = getattr(AppSettings, "get", None)
    if callable(getter):
        return getter()

    s = AppSettings.query.first()
    if not s:
        s = AppSettings()
        db.session.add(s)
        db.session.commit()
    return s


def _parse_emails_fallback(raw: str) -> List[str]:
    """
    Parse emails separated by newline/comma/semicolon.
    Fallback if vigi.utils.parse_emails is not available.
    """
    if not raw:
        return []
    parts = []
    for chunk in raw.replace(";", ",").split(","):
        parts.extend(chunk.splitlines())
    cleaned = []
    for e in [p.strip() for p in parts]:
        if e and "@" in e:
            cleaned.append(e)
    # de-dup while keeping order
    out = []
    seen = set()
    for e in cleaned:
        if e.lower() not in seen:
            seen.add(e.lower())
            out.append(e)
    return out


def _get_recipients(settings: AppSettings) -> List[str]:
    """
    Build recipients list from:
    - settings.quality_emails (multi)
    - plus settings.quality_email (legacy)
    Remove duplicates.
    """
    raw_multi = (getattr(settings, "quality_emails", None) or "").strip()
    legacy = (getattr(settings, "quality_email", None) or "").strip()

    try:
        from vigi.utils import parse_emails  # type: ignore
        lst = parse_emails(raw_multi) if raw_multi else []
    except Exception:
        lst = _parse_emails_fallback(raw_multi)

    if legacy:
        # ensure legacy is included
        if legacy.lower() not in {x.lower() for x in lst}:
            lst.append(legacy)

    # final de-dup
    out = []
    seen = set()
    for e in lst:
        k = e.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(e.strip())
    return out


# ────────────────────────────────
# CSV Builder (Reusable)
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

        today = _get_today_date()
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
                _fmt_date(lot.expiry_date),
                lot.type or "",
                state,
            ])

        return output.getvalue().encode("utf-8-sig")


# ────────────────────────────────
# PDF Builder (Reusable) ✅ with row colors + unified dates dd/MM/YYYY
# ────────────────────────────────
def build_lots_pdf_from_lots(lots: Iterable[Lot], lang_code: str, today: date = None) -> bytes:
    today = today or _get_today_date()

    lang_code = _normalize_lang(lang_code, current_app.config.get("BABEL_DEFAULT_LOCALE", "fr"))
    is_ar = lang_code.startswith("ar")

    # Fonts
    if is_ar:
        if not _ensure_arabic_fonts():
            is_ar = False  # fallback

    font_regular = "NotoNaskhArabic" if is_ar else "Helvetica"
    font_bold = "NotoNaskhArabic-Bold" if is_ar else "Helvetica-Bold"

    styles = getSampleStyleSheet()

    def _p(text: str, font_name: str, size: int = 9, align: int = 1, bold: bool = False) -> Paragraph:
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
            alignment=align,  # 2 = right, 1 = center, 0 = left
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
        header_align = 2 if is_ar else 1
        body_align = 2 if is_ar else 1

        data = [[_p(h, font_bold, bold=True, align=header_align) for h in headers]]

        status_keys: List[str] = []

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
                _fmt_date(lot.expiry_date),   # ✅ unified dd/MM/YYYY
                lot.type or "",
                state,
            ]
            data.append([_p(c, font_regular, align=body_align) for c in row])

        table = Table(data, repeatRows=1, colWidths=[160, 90, 110, 100, 110, 110])

        # Base styles
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.4, 0.8)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),

            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTNAME", (0, 1), (-1, -1), font_regular),

            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (0, 1), (-1, -1), "RIGHT" if is_ar else "CENTER"),
        ]

        # Row coloring
        bg_map = {
            "expired": colors.Color(1, 0.8, 0.8),  # light red
            "warning": colors.Color(1, 1, 0.8),    # light yellow
            "valid": colors.Color(0.8, 1, 0.8),    # light green
        }
        for i, key in enumerate(status_keys, start=1):
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg_map.get(key, colors.white)))

        table.setStyle(TableStyle(style_cmds))
        elements.append(table)

        doc.build(elements)
        return buf.getvalue()


def build_lots_pdf(lang_code: str) -> bytes:
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

    if not getattr(settings, "auto_export_enabled", False):
        current_app.logger.info("[AUTOEXPORT] disabled")
        return False

    recipients = _get_recipients(settings)
    if not recipients:
        current_app.logger.warning("[AUTOEXPORT] missing recipients (quality_emails/quality_email)")
        return False

    today = today or _get_today_date()

    export_day = int(getattr(settings, "export_day", 1) or 1)

    # Only on export_day
    if int(today.day) != export_day:
        current_app.logger.info(
            f"[AUTOEXPORT] not today (today={today.day}, export_day={export_day})"
        )
        return False

    # Prevent duplicate in same month
    mk = _month_key(today)
    if getattr(settings, "last_export_month", None) == mk:
        current_app.logger.info(f"[AUTOEXPORT] already sent for {mk}")
        return False

    # Language priority: CLI override > settings.report_language > default
    default_lang = current_app.config.get("BABEL_DEFAULT_LOCALE", "fr")
    if lang_code:
        lang_code = _normalize_lang(lang_code, default_lang)
    else:
        lang_code = _normalize_lang(getattr(settings, "report_language", None), default_lang)

    # Format
    fmt = (getattr(settings, "export_format", None) or "pdf").strip().lower()
    if fmt not in ("pdf", "csv"):
        fmt = "pdf"

    # Build file
    if fmt == "csv":
        file_bytes = build_lots_csv(lang_code)
        filename = f"VigiFroid_Report_{mk}.csv"
        mimetype = "text/csv; charset=utf-8"
    else:
        file_bytes = build_lots_pdf(lang_code)
        filename = f"VigiFroid_Report_{mk}.pdf"
        mimetype = "application/pdf"

    # Localized email (Subject + Body) ✅ Professional + legend
    with force_locale(lang_code):
        subject = _("VigiFroid · Monthly Lots Report — %(month)s", month=mk)

        body = _(
            "Dear Quality Manager,\n"
            "\n"
            "Please find attached the monthly lots report generated by VigiFroid.\n"
            "Kindly review the report and take any necessary actions for lots that are expired or nearing expiry.\n"
            "\n"
            "Status legend:\n"
            "- 🟥 Expired (past expiry date)\n"
            "- 🟨 Warning (expires within 30 days)\n"
            "- 🟩 Valid (more than 30 days remaining)\n"
            "\n"
            "If you have any questions or need clarification, please contact the administrator.\n"
            "\n"
            "Best regards,\n"
            "VigiFroid System"
        )

    msg = Message(subject=subject, recipients=recipients)
    msg.body = body
    msg.attach(filename, mimetype, file_bytes)

    try:
    # Update anti-duplicate fields FIRST (idempotency)
        settings.last_export_month = mk
        settings.last_export_at = datetime.utcnow()
        db.session.add(settings)

    # Log recipients list
        rec_str = ", ".join(recipients)
        db.session.add(Log(action=f"Auto export sent ({fmt}) to: {rec_str}", user_id=None))

    # Commit BEFORE sending email
        db.session.commit()

    # Send email AFTER commit
        mail.send(msg)

        current_app.logger.info(f"[AUTOEXPORT] sent to {rec_str} ({fmt})")
        return True


    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"[AUTOEXPORT] send failed: {exc}")
        return False
