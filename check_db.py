# check_db.py

from vigi import create_app
from vigi.extensions import db
from models import User, Lot, Log
from sqlalchemy import text

def main():
    app = create_app()

    with app.app_context():
        print("=== 🔌 DB ENGINE INFO ===")
        engine = db.engine
        print("URL :", engine.url)
        print("Dialect :", engine.name)          # خاصها تكون 'postgresql'
        print("Driver  :", engine.driver)        # psycopg2 مثلاً

        # تجربة اتصال بسيطة
        print("\n=== ✅ TEST SELECT 1 ===")
        try:
            result = db.session.execute(text("SELECT 1")).scalar()
            print("SELECT 1 ->", result)
        except Exception as e:
            print("❌ Error running SELECT 1:", e)
            return

        # إحصائيات بسيطة على الجداول
        print("\n=== 📊 COUNTS ===")
        try:
            users_count = User.query.count()
            lots_count = Lot.query.count()
            logs_count = Log.query.count()
            print("Users :", users_count)
            print("Lots  :", lots_count)
            print("Logs  :", logs_count)
        except Exception as e:
            print("❌ Error counting rows:", e)

        # نتحقق من أعمدة جدول users
        print("\n=== 🧱 USERS COLUMNS ===")
        cols = list(User.__table__.columns.keys())
        print("Columns:", cols)
        if "email" in cols:
            print("✔ 'email' column موجودة فجدول users")
        else:
            print("❌ 'email' column ما لقاهاش فجدول users")

        # نطبع أول user (إن وجد)
        print("\n=== 👤 FIRST USER ===")
        first_user = User.query.first()
        if first_user:
            print("id      :", first_user.id)
            print("username:", first_user.username)
            # نستعمل getattr باش ما يطيحش الخطأ إلى ما كانش email
            print("email   :", getattr(first_user, "email", "NO EMAIL ATTR"))
            print("role    :", first_user.role)
        else:
            print("⚠ لا يوجد أي user فقاعدة البيانات")

        print("\n✅ DB CHECK DONE")

if __name__ == "__main__":
    main()
