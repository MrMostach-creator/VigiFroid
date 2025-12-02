# migrations/versions/31eaf7771755_add_composite_indexes_for_lots.py

from alembic import op
import sqlalchemy as sa

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "31eaf7771755"       # ← خليه كما هو
down_revision = "f3cfefd28517"  # ← حسب آخر ريفيجن عندك
branch_labels = None
depends_on = None

def upgrade():
    # فهرس مركّب: type + expiry_date
    op.create_index(
        "ix_lots_type_expiry_date",
        "lots",
        ["type", "expiry_date"],
        unique=False
    )

    # 🔁 كان partial index بـ CURRENT_DATE (سبب الخطأ)
    # نعوّضه بفهرس عادي على expiry_date
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_lots_expiry_date
        ON lots (expiry_date)
    """)

def downgrade():
    # نحذف الفهرس العادي
    op.execute("DROP INDEX IF EXISTS ix_lots_expiry_date")

    # نحذف الفهرس المركّب
    op.drop_index("ix_lots_type_expiry_date", table_name="lots")
