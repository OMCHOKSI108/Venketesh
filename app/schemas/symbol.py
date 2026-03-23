from typing import Optional
from pydantic import BaseModel, Field


class SymbolBase(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    exchange: str
    instrument_type: str
    currency: str = "INR"
    is_active: bool = True
    additional_info: Optional[dict] = None


class SymbolCreate(SymbolBase):
    pass


class SymbolResponse(SymbolBase):
    class Config:
        from_attributes = True


class SymbolListResponse(BaseModel):
    symbols: list[SymbolResponse]
    count: int
