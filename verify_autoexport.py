# verify_autoexport.py  ✅ FINAL (imports app from wsgi)
import os
import sys
import logging
from datetime import date

sys.path.append(os.getcwd())

from wsgi import app
from vigi.extensions import db
from models import AppSettings, Log
from vigi.services.reports import run_monthly_auto_export


try:
    from vigi.utils_time import get_today_date
except Exception:
    def get_today_date():
        return date.today()


def verify_autoexport():
    print("--- Starting Verification ---")

    with app.app_context():
        # Don't actually send emails during test
        app.config["MAIL_SUPPRESS_SEND"] = True

        logging.basicConfig(level=logging.INFO)
        app.logger.setLevel(logging.INFO)

        settings = AppSettings.get()
        print(f"Original Settings: enabled={settings.auto_export_enabled}, legacy_email={settings.quality_email}")

        # Enable + set multi emails
        settings.auto_export_enabled = True
        settings.quality_emails = "user1@test.com\nuser2@test.com, user3@test.com"
        settings.quality_email = "legacy@test.com"  # legacy still exists

        today = get_today_date()
        settings.export_day = min(today.day, 28)  # safe for constraint 1..28
        settings.last_export_month = None
        settings.last_export_at = None

        db.session.add(settings)
        db.session.commit()

        recipients = settings.get_recipients()
        print(f"Updated Settings: enabled={settings.auto_export_enabled}, recipients={recipients}, day={settings.export_day}")

        print("Running run_monthly_auto_export()...")
        success = run_monthly_auto_export(today=today)
        print(f"Result: {success}")

        if not success:
            print("FAILED: run_monthly_auto_export returned False")
            sys.exit(1)

        log = Log.query.order_by(Log.id.desc()).first()
        if not log:
            print("FAILURE: No Log row found after sending.")
            sys.exit(1)

        print(f"Last Log: {log.action}")

        expected = ["user1@test.com", "user2@test.com", "user3@test.com", "legacy@test.com"]
        missing = [e for e in expected if e not in (log.action or "")]

        if missing:
            print(f"FAILURE: Missing emails in log: {missing}")
            sys.exit(1)

        print("SUCCESS: Log contains all emails.")
        print("\nALL TESTS PASSED ✅")


if __name__ == "__main__":
    verify_autoexport()
