# ────────────────────────────────
# 📁 vigi/forms.py — نسخة مصححة
# ────────────────────────────────
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, IntegerField, FileField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange
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
        "PN",
        validators=[DataRequired(message=_l("⚠️ PN is required.")), Length(min=1, max=50)]
    )



    image = FileField(_l("Image"))
    submit = SubmitField(_l("💾 Save"))
