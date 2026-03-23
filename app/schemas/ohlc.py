from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import MetaInfo


class OHLCBase(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    timestamp: datetime
    timeframe: str = Field(..., pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$")
    open: Decimal = Field(..., ge=0)
    high: Decimal = Field(..., ge=0)
    low: Decimal = Field(..., ge=0)
    close: Decimal = Field(..., ge=0)
    volume: Optional[int] = Field(default=None, ge=0)
    source: str
    is_closed: bool = False

    @field_validator("high")
    @classmethod
    def high_gte_low(cls, v, info):
        if "low" in info.data and v < info.data["low"]:
            raise ValueError("high must be >= low")
        return v

    @field_validator("low")
    @classmethod
    def low_lte_high(cls, v, info):
        if "high" in info.data and v > info.data["high"]:
            raise ValueError("low must be <= high")
        return v

    @field_validator("open", "close")
    @classmethod
    def within_range(cls, v, info):
        if "low" in info.data and "high" in info.data:
            low = info.data["low"]
            high = info.data["high"]
            if not (low <= v <= high):
                raise ValueError("open/close must be within low-high range")
        return v


class OHLCCreate(OHLCBase):
    pass


class OHLCDataResponse(OHLCBase):
    class Config:
        from_attributes = True


class OHLCDataItem(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None
    is_closed: bool = False
    source: Optional[str] = None

    class Config:
        from_attributes = True


class OHLCDataListResponse(BaseModel):
    symbol: str
    timeframe: str
    data: list[OHLCDataItem]
    meta: MetaInfo


class OHLCLatestResponse(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None
    is_closed: bool = False
    source: str


class WebSocketMessage(BaseModel):
    type: str
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    data: Optional[dict] = None
    timestamp: Optional[datetime] = None
    message: Optional[str] = None
    code: Optional[str] = None
