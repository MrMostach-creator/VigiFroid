# vigifroid_images_dedupe.py

import os, sqlite3, hashlib, shutil
from datetime import datetime
from pathlib import Path

DB = Path("database.db")
IMG_DIR = Path("static/images")
ALLOWED_EXTS = {".png", ".jpg", ".jpeg"}
KEEP_PREFIXES = ("safran_icon", "vigifroid_icon")  # ما نمسّوش هاد الأيقونات
DELETE_UNUSED = True   # إذا بغيتي ما نحيدوش الصور الغير مستعملة، خليه False

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def canonical_name(h: str, ext: str) -> str:
    return f"img_{h[:16]}{ext.lower()}"

def main():
    if not DB.exists():
        raise SystemExit("❌ database.db غير موجود.")
    if not IMG_DIR.exists():
        raise SystemExit("❌ static/images غير موجود.")

    # 0) باكاپ للمجلد كامل
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = IMG_DIR.parent / f"images_backup_{ts}"
    shutil.copytree(IMG_DIR, backup_dir)
    print(f"[OK] Backup folder created: {backup_dir}")

    con = sqlite3.connect(DB)
    cur = con.cursor()

    # 1) لائحة الملفات المستعملة فعلاً فـ DB
    cur.execute("SELECT DISTINCT image FROM lots")
    used_files = {row[0] for row in cur.fetchall() if row[0]}

    # 2) حضّر خريطة hash -> files (غير للملفات المستعملة فعلاً)
    groups = {}  # {hash: [Path,...]}
    for name in used_files:
        p = IMG_DIR / name
        if not p.exists():
            print(f"[WARN] Missing image referenced in DB: {name}")
            continue
        ext = p.suffix.lower()
        if ext not in ALLOWED_EXTS:
            # حتى لو ماشي png/jpg/jpeg، نكمّل بها (احتمال امتداد ناقص)
            pass
        try:
            h = sha256_of(p)
        except Exception as e:
            print(f"[WARN] Cannot hash {name}: {e}")
            continue
        groups.setdefault((h, ext or ".jpg"), []).append(p)

    # 3) وحّد الأسماء إلى img_<hash>.<ext> وحدّث DB
    renamed = 0
    for (h, ext), files in groups.items():
        # اختار اسم موحّد
        canon = IMG_DIR / canonical_name(h, ext)
        # إذا كاين واحد أصلاً بهاذ الاسم فالمجموعة، خليه هو المرجع
        if canon not in files and canon.exists():
            # موجود ولكن DB قد تشير لأسماء أخرى → نحدّث DB فقط
            pass
        else:
            # إذا ما كاينش، نختار أول ملف ونبدّل سميتو للموحّد
            src = files[0]
            if src != canon:
                try:
                    if canon.exists():
                        # نكتفي بالتحديث فالـDB
                        pass
                    else:
                        src.rename(canon)
                        print(f"[REN] {src.name} -> {canon.name}")
                        renamed += 1
                        # نزّل من اللائحة باش ما نحاولش نحذفو من بعد
                        files[0] = canon
                except Exception as e:
                    print(f"[WARN] Rename failed {src.name} -> {canon.name}: {e}")

        # حدّث DB: كل أسماء هاد المجموعة تولّي تشير للاسم الموحّد
        for p in files:
            if p.name != canon.name:
                cur.execute("UPDATE lots SET image=? WHERE image=?", (canon.name, p.name))

    con.commit()
    print(f"[OK] DB updated. Renamed {renamed} files to canonical names.")

    # 4) حذف أي ملفات غير مستعملة بعد التوحيد (مع الحفاظ على الأيقونات)
    if DELETE_UNUSED:
        cur.execute("SELECT DISTINCT image FROM lots")
        still_used = {row[0] for row in cur.fetchall() if row[0]}
        deleted = 0
        for f in IMG_DIR.iterdir():
            if not f.is_file():
                continue
            # نحافظ على الأيقونات
            if f.stem.startswith(KEEP_PREFIXES):
                continue
            # نحذف فقط إذا الاسم غير مستعمل نهائياً
            if f.name not in still_used:
                try:
                    f.unlink()
                    deleted += 1
                    print(f"[DEL] {f.name}")
                except Exception as e:
                    print(f"[WARN] Could not delete {f.name}: {e}")
        print(f"[OK] Removed {deleted} unused files.")

    con.close()
    print("[DONE] Image de-duplication finished.")

if __name__ == "__main__":
    main()
