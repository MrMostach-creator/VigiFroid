# vigi/cli_autoexport.py  ✅ FINAL
import click
from flask.cli import with_appcontext
import sys
from vigi.services.reports import run_monthly_auto_export


def register_cli(app):
    @app.cli.command("autoexport")
    @click.option(
        "--lang",
        default=None,
        type=click.Choice(["ar", "fr", "en"], case_sensitive=False),
        help="Override language for this run only (default comes from Export Settings).",
    )
    @with_appcontext
    def autoexport_cmd(lang):
        """
        Run monthly auto export (meant for Windows Task Scheduler / cron).
        It sends only if today == export_day and not already sent this month.
        """
        ok = run_monthly_auto_export(lang_code=lang)
        if ok:
            click.echo("Auto export: SENT")
            sys.exit(0)
        else:
            click.echo("Auto export: SKIPPED (disabled / wrong day / already sent / missing email)")
            sys.exit(0)
