import logging
from datetime import UTC, datetime

from app.db import SessionLocal
from app.models import ExchangeRate
from scrapers.bcv import ScraperError, fetch_bcv_rates

log = logging.getLogger(__name__)


def fetch_and_save_rates() -> None:
    """Fetch USD/EUR rates from BCV and upsert them into the database."""
    try:
        rates = fetch_bcv_rates()
    except ScraperError as e:
        log.error("BCV scraper falló: %s", e)
        return

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        for currency, rate in rates.items():
            row = db.get(ExchangeRate, currency)
            if row:
                row.rate = rate
                row.updated_at = now
            else:
                db.add(ExchangeRate(currency=currency, rate=rate, updated_at=now))
        db.commit()
        log.info("Tasas BCV guardadas: %s", rates)
    except Exception as e:
        db.rollback()
        log.error("Error al guardar tasas BCV: %s", e)
    finally:
        db.close()
