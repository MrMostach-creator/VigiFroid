# ────────────────────────────────────────────────
# 📁 vigi/auth/routes.py — نسخة موحدة مع PostgreSQL وSQLAlchemy
# ────────────────────────────────────────────────

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from vigi.extensions import db, mail
from flask_mail import Message
from models import User
from vigi import login_manager
from flask_babel import gettext as _


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# 🧩 تحميل المستخدم أثناء الجلسة
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 🔐 صفحة تسجيل الدخول
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("✅ Login successful.", "success")
            return redirect(url_for("main.index"))
        else:

            flash("❌ Invalid username or password.", "error")
    return render_template("login.html")

# 🚪 تسجيل الخروج
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("✅ Logged out successfully.", "success")
    return redirect(url_for("auth.login"))


# ────────────────────────────────────────────────
# 🔑 Forgot Password & Reset Flow
# ────────────────────────────────────────────────

def get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")

def generate_reset_token(user):
    s = get_serializer()
    return s.dumps(user.id)

def verify_reset_token(token, max_age=3600):
    s = get_serializer()
    try:
        user_id = s.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return User.query.get(user_id)

def send_reset_email(user, token):
    """
    إرسال إيميل إسترجاع كلمة السر باستعمال Flask-Mail.
    """
    reset_url = url_for("auth.reset_password", token=token, _external=True)

    # موضوع الرسالة
    subject = _("VigiFroid · Password reset")

    # النص العادي
    text_body = _(
        "Hello %(username)s,\n\n"
        "You requested to reset your VigiFroid password.\n"
        "To choose a new password, click the link below:\n\n"
        "%(url)s\n\n"
        "If you did not request this, you can ignore this email.",
        username=user.username,
        url=reset_url,
    )

    # النسخة HTML بسيطة
    html_body = f"""
    <p>{_('Hello')} <strong>{user.username}</strong>,</p>
    <p>{_('You requested to reset your VigiFroid password.')}</p>
    <p>{_('To choose a new password, click the button below:')}</p>
    <p>
      <a href="{reset_url}"
         style="display:inline-block;padding:10px 18px;
                background:#4179D9;color:#fff;text-decoration:none;
                border-radius:6px;font-weight:600;">
        {_('Reset password')}
      </a>
    </p>
    <p style="margin-top:16px;font-size:13px;color:#6b7280;">
      {_('If you did not request this, you can ignore this email.')}
    </p>
    """

    try:
        msg = Message(
            subject=subject,
            recipients=[user.email],
        )
        msg.body = text_body
        msg.html = html_body

        mail.send(msg)
        current_app.logger.info(f"[MAIL] Password reset email sent to {user.email}")
    except Exception as exc:
        # في حالة fallo فالإرسال، على الأقل يسجّل فـ log وما يطيحش التطبيق
        current_app.logger.error(f"[MAIL] Error sending reset email to {user.email}: {exc}")

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = generate_reset_token(user)
            send_reset_email(user, token)
        
        flash("If an account exists with this email, you will receive a reset link.", "info")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")

@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    user = verify_reset_token(token)
    if not user:
        flash("The reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            user.password = generate_password_hash(password)
            db.session.commit()
            flash("Your password has been reset. You can now log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)
