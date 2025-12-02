# ────────────────────────────────
# 📁 vigi/lots/utils.py
# ────────────────────────────────
import os
import uuid
from datetime import date
from flask import current_app
from sqlalchemy import func
from werkzeug.utils import secure_filename

# 🧠 نحاول نستخدم Pillow لضغط الصور إن وجدت
try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from models import Lot
except Exception:
    from models import Lot  # fallback إذا models.py فالجذر


def allowed_file(filename: str) -> bool:
    """تحديد ما إذا كان الملف صورة مسموح بها."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg"}


def _abs_upload_folder() -> str:
    """إرجاع المسار المطلق لمجلد الصور، وإنشاؤه إذا لم يكن موجوداً."""
    folder = current_app.config.get("UPLOAD_FOLDER", os.path.join("static", "images"))
    if not os.path.isabs(folder):
        folder = os.path.join(current_app.root_path, folder)
    os.makedirs(folder, exist_ok=True)
    return folder


def store_image(file_storage) -> str:
    """حفظ الصورة باسم فريد وضغطها لتسريع التحميل."""
    ext = os.path.splitext(file_storage.filename)[1].lower()
    filename = f"{uuid.uuid4().hex}{ext}"
    folder = _abs_upload_folder()
    path = os.path.join(folder, filename)

    # حفظ الصورة الأصلية
    file_storage.save(path)

    # 🧩 ضغط الصورة إذا كانت Pillow متوفرة
    if Image:
        try:
            img = Image.open(path)
            img = img.convert("RGB")
            img.save(path, optimize=True, quality=85)
            current_app.logger.info(f"Optimized image saved: {filename}")
        except Exception as e:
            current_app.logger.warning(f"⚠️ Image optimization skipped: {e}")

    return filename


def delete_image_if_unused(session, image_filename: str, exclude_lot_id: int | None = None) -> None:
    """حذف الصورة من المجلد إذا لم تعد مرتبطة بأي Lot."""
    if not image_filename:
        return
    q = session.query(func.count(Lot.id)).filter(Lot.image == image_filename)
    if exclude_lot_id:
        q = q.filter(Lot.id != exclude_lot_id)
    if (q.scalar() or 0) == 0:
        try:
            os.remove(os.path.join(_abs_upload_folder(), image_filename))
            current_app.logger.info(f"Deleted unused image: {image_filename}")
        except OSError:
            pass


def compute_status(expiry_date, warn_days: int = 30) -> str:
    """حساب حالة المنتج (منتهي، قريب، صالح)."""
    if not expiry_date:
        return "valid"
    d = (expiry_date - date.today()).days
    if d < 0:
        return "expired"
    if 0 <= d <= warn_days:
        return "warning"
    return "valid"
