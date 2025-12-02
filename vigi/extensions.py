# ────────────────────────────────
# 📁 vigi/extensions.py
# ────────────────────────────────


from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache
from flask_babel import Babel
from flask_compress import Compress
from flask_login import LoginManager
from flask_mail import Mail

# Instances (نربطها داخل create_app)
db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
babel = Babel()
compress = Compress()
login_manager = LoginManager()
mail = Mail()