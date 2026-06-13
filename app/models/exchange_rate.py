from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, String

from app.models.base import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    currency = Column(String, primary_key=True)  # "USD" | "EUR"
    rate = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))
