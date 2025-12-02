# vigifroid_deduplicate.py

import os, shutil, sqlite3
from datetime import datetime

DB_PATH = "database.db"

def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"Database not found: {DB_PATH}")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"database_backup_{ts}.db"
    shutil.copy2(DB_PATH, backup)
    print(f"[OK] Backup created: {backup}")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    try:
        cur.execute("BEGIN")
        # حذف الدوبليكيات: نخلي أصغر id لكل lot_number
        cur.execute("""
            DELETE FROM lots
            WHERE id NOT IN (
              SELECT MIN(id) FROM lots GROUP BY lot_number
            )
        """)
        # منع التكرار مستقبلاً
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lots_lot_number ON lots(lot_number)")
        con.commit()
        print("[OK] Duplicates removed and unique index created.")
        # تأكد ما بقاو دوبليكيات
        cur.execute("SELECT lot_number, COUNT(*) FROM lots GROUP BY lot_number HAVING COUNT(*) > 1")
        dups = cur.fetchall()
        if dups:
            print("[WARN] Some duplicates remain:", dups)
        else:
            print("[OK] No duplicates remain.")
    except Exception as e:
        con.rollback()
        print("[ERR] Rolled back due to:", e)
        print(f"You can restore the backup: {backup}")
        raise
    finally:
        con.close()

if __name__ == "__main__":
    main()
