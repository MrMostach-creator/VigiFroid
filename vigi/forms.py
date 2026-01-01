# ────────────────────────────────
# 📁 vigi/forms.py — LotForm + AppSettingsForm (Clean)
# ────────────────────────────────

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    DateField,
    IntegerField,
    FileField,
    SubmitField,
    BooleanField,
    SelectField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Email,
    Optional,
    ValidationError,
)
from flask_babel import lazy_gettext as _l


class LotForm(FlaskForm):
    lot_number = StringField(
        _l("Lot Number"),
        validators=[DataRequired(message=_l("⚠️ LOT number is required.")), Length(min=1, max=50)]
    )

    product_name = StringField(
        _l("Product Name"),
        validators=[DataRequired(message=_l("⚠️ Product name is required.")), Length(min=2, max=100)]
    )

    type = StringField(
        _l("Product Type"),
        validators=[DataRequired(message=_l("⚠️ Product type is required.")), Length(min=2, max=50)]
    )

    expiry_date = DateField(
        _l("Expiry Date"),
        validators=[DataRequired(message=_l("⚠️ Expiry date is required."))]
    )

    pn = StringField(
        _l("PN"),
        validators=[DataRequired(message=_l("⚠️ PN is required.")), Length(min=1, max=50)]
    )

    image = FileField(_l("Image"))
    submit = SubmitField(_l("💾 Save"))


class AppSettingsForm(FlaskForm):
    """إعدادات التصدير الشهري إلى مسؤول الجودة (Admin only)."""

    export_enabled = BooleanField(_l("Enable monthly export to quality manager"))

    # Updated to support multiple emails
    quality_emails = TextAreaField(
        _l("Quality manager emails (one per line)"),
        validators=[Optional()]
    )

    export_day = IntegerField(
        _l("Day of month (1-28)"),
        validators=[
            Optional(),
            NumberRange(min=1, max=28, message=_l("⚠️ Please choose a day between 1 and 28."))
        ]
    )

    export_format = SelectField(
        _l("Report format"),
        choices=[("pdf", _l("PDF")), ("csv", _l("CSV"))],
        default="pdf",
        validators=[Optional()],
    )
    report_language = SelectField(
    _l("Report language"),
    choices=[("fr", "Français"), ("en", "English"), ("ar", "العربية")],
    default="fr",
    validators=[Optional()],
    )

    submit = SubmitField(_l("💾 Save"))

    # ✅ منطق: إلا كان ON خاص email + day
    def validate_quality_emails(self, field):
        if not self.export_enabled.data:
            return

        from vigi.utils import parse_emails
        raw = (field.data or "").strip()
        
        # 1. Require at least one email
        if not raw:
            raise ValidationError(_l("⚠️ At least one email is required when auto-export is enabled."))

        # 2. Validate format of all emails (parse_emails does basic check, but we want to ensure *everything* entered is valid-ish)
        # parse_emails returns only valid ones. If the user entered "foo", parse_emails might return [], 
        # or if we want strict validation, we should check line by line.
        # Let's rely on parse_emails to extract valid ones. 
        # If user entered garbage, parse_emails returns empty list => error.
        valid_list = parse_emails(raw)
        if not valid_list:
             raise ValidationError(_l("⚠️ Please enter valid email addresses."))

    def validate_export_day(self, field):
        if self.export_enabled.data and not field.data:
            raise ValidationError(_l("⚠️ Please choose the day of the month for auto-export."))
        


