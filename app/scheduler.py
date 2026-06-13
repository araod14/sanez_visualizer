"""Construcción del scheduler BCV (APScheduler). Se construye dentro de
`create_app` para no tener side-effects al importar el módulo."""

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Settings
from scrapers.tasks import fetch_and_save_rates


def build_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.scheduler_tz)
    scheduler.add_job(
        fetch_and_save_rates,
        "cron",
        hour=settings.scheduler_hour,
        minute=settings.scheduler_minute,
        id="bcv_rates",
    )
    return scheduler
