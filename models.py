# 📁 models.py — نسخة أصلية مصححة (بدون أي تغيير في البنية)
# ───────────────────────────────

from datetime import datetime, date
from vigi.extensions import db
from flask_login import UserMixin


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)  # 👈 مهم للقيود و reset

    password = db.Column(db.String(200), nullable=False)

    role = db.Column(db.String(20), default="employee")  # غادي نزيدو عليه CHECK فـ PostgreSQL

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"



class Lot(db.Model):
    __tablename__ = "lots"

    id = db.Column(db.Integer, primary_key=True)
    # ✅ الإصلاح: استعمال String(100) بدل Text لتفادي تعارض PostgreSQL مع unique
    lot_number = db.Column(db.String(255), nullable=False, unique=True)
    product_name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(100), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    pn = db.Column(db.String(255), nullable=False, unique=True)  # ✅
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
