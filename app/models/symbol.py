from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class Symbol(Base, TimestampMixin):
    __tablename__ = "symbols"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    additional_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self):
        return f"<Symbol(symbol={self.symbol}, name={self.name}, exchange={self.exchange})>"
