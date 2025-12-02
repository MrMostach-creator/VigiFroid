# ────────────────────────────────
# 📁 test_cache_reset.py — اختبار آلي لتفريغ كاش /logs
# ────────────────────────────────

from vigi import create_app
from vigi.extensions import db, cache
from models import Lot, Log, User
from datetime import datetime

app = create_app("config.Config")

with app.app_context():
    print("\n===== 🚀 بدء اختبار تفريغ الكاش =====")

    # 🧹 نحذف أي كاش قديم
    cache.delete("logs_page")
    print("🔸 الكاش القديم تم حذفه بنجاح.\n")

    # 👤 نختار المستخدم الإداري الأول
    admin = User.query.filter_by(role="admin").first()
    if not admin:
        print("⚠️ لا يوجد مستخدم أدمن. أنشئ واحد عبر لوحة الدخول.")
    else:
        # ➕ نضيف منتج وهمي
        lot = Lot(
            lot_number=f"TEST-{datetime.utcnow().strftime('%H%M%S')}",
            product_name="CacheTest",
            type="test",
            expiry_date=datetime.utcnow().date(),
            pn=f"PN-{datetime.utcnow().strftime('%H%M%S')}",
            quantity=1,
        )
        db.session.add(lot)
        db.session.flush()

        log = Log(action=f"Added test lot {lot.lot_number}", user_id=admin.id)
        db.session.add(log)
        db.session.commit()

        # 🧠 نتحقق من وجود السجل في الكاش
        logs_cache_before = cache.get("logs_page")
        print(f"🧩 الكاش قبل الحذف = {logs_cache_before}")

        # 💥 نحذف الكاش الآن
        cache.delete("logs_page")
        logs_cache_after = cache.get("logs_page")

        print(f"✅ الكاش بعد الحذف = {logs_cache_after}\n")

        print("🎯 النتيجة المتوقعة: None (أي تم تفريغه بنجاح).")

    print("===== ✅ انتهى الاختبار =====\n")
