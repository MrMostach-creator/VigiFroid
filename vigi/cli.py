# vigi/cli.py
import click
from flask import current_app
from flask.cli import with_appcontext

from vigi.services.reports import run_monthly_auto_export


@click.command("auto-export")
@click.option("--lang", default=None, help="Language for the email content (ar/fr/en).")
@with_appcontext
def auto_export_cmd(lang):
    """
    Run monthly auto export if today matches settings.export_day
    and auto-export is enabled. Safe to run daily.
    """
    try:
        ok = run_monthly_auto_export(lang_code=lang)
        if ok:
            click.echo("✅ Auto-export: report sent.")
        else:
            click.echo("ℹ️ Auto-export: nothing to do (disabled / not today / already sent / missing email).")
    except Exception as e:
        current_app.logger.exception(f"[AUTOEXPORT] CLI failed: {e}")
        raise SystemExit(1)
