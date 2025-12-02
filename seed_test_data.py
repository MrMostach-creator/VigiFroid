# ────────────────────────────────
# 📁 seed_test_data.py
# ────────────────────────────────
"""
🔹 سكريبت صغير لإضافة منتجات تجريبية (25 منتج)
باش نختبرو Pagination فـ VigiFroid
"""

from vigi import create_app
from vigi.extensions import db
from models import Lot
from datetime import datetime, timedelta
import random

# إنشاء التطبيق داخل السياق
app = create_app("config.Config")

with app.app_context():
    print("🚀 بدء إضافة بيانات تجريبية إلى قاعدة البيانات...")

    products = [
        "Loctite", "Graisse", "Vernelec", "WD40", "Lubrifiant",
        "Nettoyant", "Adhésif", "Résine", "Colle", "Solvant"
    ]
    types = ["loctite", "graisse", "vernelec", "general"]

    for i in range(25):
        product = random.choice(products)
        lot = Lot(
            lot_number=f"LOT{i+1:04d}",
            product_name=f"{product} Test {i+1}",
            type=random.choice(types),
            expiry_date=datetime.utcnow().date() + timedelta(days=random.randint(-60, 180)),
            pn=f"PN{i+1:04d}",
            quantity=random.randint(1, 10),
            image=None
        )
        db.session.add(lot)

    db.session.commit()
    print("✅ تمت إضافة 25 منتجًا تجريبيًا بنجاح!")
