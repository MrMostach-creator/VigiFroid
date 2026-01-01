# update_db.py
import os
import sys

sys.path.append(os.getcwd())

from sqlalchemy import text
from app import app
from vigi.extensions import db

def run_migration():
    print("Applying migration: add_quality_emails_column.sql")
    migration_file = os.path.join("migrations", "add_quality_emails_column.sql")

    if not os.path.exists(migration_file):
        print(f"Error: Migration file not found at {migration_file}")
        sys.exit(1)

    with open(migration_file, "r", encoding="utf-8") as f:
        sql = f.read().strip()

    with app.app_context():
        try:
            db.session.execute(text(sql))
            db.session.commit()
            print("Migration applied successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error applying migration: {e}")
            sys.exit(1)

if __name__ == "__main__":
    run_migration()
