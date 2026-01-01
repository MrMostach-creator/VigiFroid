from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "3fdafcee75ab"
down_revision = "cf13197306e5"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in cols


def upgrade():
    # If column doesn't exist -> add it safely with default
    if not _has_column("app_settings", "report_language"):
        with op.batch_alter_table("app_settings", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "report_language",
                    sa.String(length=5),
                    nullable=False,
                    server_default="fr",  # مهم باش ما يطيحش إلا كانت rows قديمة
                )
            )

        # remove server_default after creation (optional but clean)
        with op.batch_alter_table("app_settings", schema=None) as batch_op:
            batch_op.alter_column(
                "report_language",
                existing_type=sa.String(length=5),
                server_default=None,
                nullable=False,
            )
    else:
        # Column already exists -> just ensure data + NOT NULL
        op.execute("UPDATE app_settings SET report_language='fr' WHERE report_language IS NULL")

        with op.batch_alter_table("app_settings", schema=None) as batch_op:
            batch_op.alter_column(
                "report_language",
                existing_type=sa.String(length=5),
                nullable=False,
            )


def downgrade():
    # Drop only if exists (avoid crash)
    if _has_column("app_settings", "report_language"):
        with op.batch_alter_table("app_settings", schema=None) as batch_op:
            batch_op.drop_column("report_language")
