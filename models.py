# 📁 models.py
# ───────────────────────────────

from datetime import datetime, date

from sqlalchemy import CheckConstraint
from flask_login import UserMixin
from typing import List
from vigi.extensions import db
from vigi.utils import parse_emails

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)  # مهم للقيود و reset
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="employee")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Lot(db.Model):
    __tablename__ = "lots"

    id = db.Column(db.Integer, primary_key=True)
    lot_number = db.Column(db.String(255), nullable=False, unique=True)
    product_name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(100), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    pn = db.Column(db.String(255), nullable=False, unique=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    image = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<Lot {self.lot_number} - {self.product_name} (PN: {self.pn})>"

    @property
    def status(self):
        if not self.expiry_date:
            return "unknown"
        days_left = (self.expiry_date - date.today()).days
        if days_left < 0:
            return "expired"
        elif days_left <= 30:
            return "warning"
        return "valid"


class Log(db.Model):
    __tablename__ = "logs"

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = db.relationship("User", backref=db.backref("logs", lazy=True))

    def __repr__(self):
        return f"<Log {self.action} at {self.timestamp}>"


class AppSettings(db.Model):
    __tablename__ = "app_settings"

    __table_args__ = (
        CheckConstraint("export_day >= 1 AND export_day <= 28", name="ck_app_settings_export_day"),
        CheckConstraint("export_format IN ('pdf','csv')", name="ck_app_settings_export_format"),
        CheckConstraint("report_language IN ('ar','fr','en')", name="ck_app_settings_report_language"),
    )

    id = db.Column(db.Integer, primary_key=True)

    # legacy
    quality_email = db.Column(db.String(255), nullable=True)

    # new multi
    quality_emails = db.Column(db.Text, nullable=True)

    auto_export_enabled = db.Column(db.Boolean, nullable=False, default=False)
    export_day = db.Column(db.Integer, nullable=False, default=1)
    export_format = db.Column(db.String(10), nullable=False, default="pdf")
    report_language = db.Column(db.String(5), nullable=False, default="fr")

    last_export_month = db.Column(db.String(7), nullable=True)
    last_export_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<AppSettings enabled={self.auto_export_enabled}, "
            f"day={self.export_day}, fmt={self.export_format}, "
            f"lang={self.report_language}, "
            f"legacy={self.quality_email}, multi={'yes' if self.quality_emails else 'no'}>"
        )

    def get_recipients(self) -> List[str]:
        """
        Returns a clean unique list of recipient emails.
        Merge: quality_emails (multi) + quality_email (legacy).
        """
        recipients: List[str] = []

        # 1) multi-field (safe even if None)
        recipients += parse_emails(self.quality_emails or "")

        # 2) legacy (merge)
        legacy = (self.quality_email or "").strip().lower()
        if legacy:
            recipients.append(legacy)

        # unique preserve order
        seen = set()
        clean: List[str] = []
        for e in recipients:
            if e and e not in seen:
                seen.add(e)
                clean.append(e)

        return clean

    @property
    def recipients(self) -> List[str]:
        return self.get_recipients()

    @classmethod
    def get(cls):
        instance = cls.query.first()
        if not instance:
            instance = cls()
            db.session.add(instance)
            db.session.commit()
        return instance
