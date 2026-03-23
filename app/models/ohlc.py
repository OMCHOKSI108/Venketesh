from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, String, DateTime, Numeric, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class OHLCData(Base, TimestampMixin):
    __tablename__ = "ohlc_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("idx_ohlc_symbol_time", "symbol", "timestamp"),
        Index("idx_ohlc_timeframe", "timeframe", "timestamp"),
    )

    def __repr__(self):
        return f"<OHLCData(symbol={self.symbol}, timestamp={self.timestamp}, timeframe={self.timeframe})>"
