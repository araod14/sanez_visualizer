"""Lectura de tasas de cambio para el endpoint público."""

from sqlalchemy.orm import Session

from app.models import ExchangeRate


def list_rates(db: Session) -> dict:
    rows = db.query(ExchangeRate).all()
    return {r.currency: {"rate": r.rate, "updated_at": r.updated_at} for r in rows}
