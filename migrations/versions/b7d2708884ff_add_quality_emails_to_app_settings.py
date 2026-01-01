"""add quality_emails to app_settings

Revision ID: b7d2708884ff
Revises: 3fdafcee75ab
Create Date: 2025-12-29
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b7d2708884ff"
down_revision = "3fdafcee75ab"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS quality_emails TEXT;")


def downgrade():
    op.execute("ALTER TABLE app_settings DROP COLUMN IF EXISTS quality_emails;")
