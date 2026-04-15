from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class CryptoBase(BaseModel):
    symbol: str
    name: str
    current_price: float
    change_1h: Optional[str] = None
    change_24h: Optional[str] = None
    change_7d: Optional[str] = None
    market_cap: Optional[str] = None
    volume_24h: Optional[str] = None


class CryptoResponse(CryptoBase):
    id: int
    last_updated: Optional[datetime] = None

    # This allows Pydantic to read data from SQLAlchemy models
    model_config = ConfigDict(from_attributes=True)
