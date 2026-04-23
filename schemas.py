from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


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


class UserCreate(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    fiat_balance: float
    created_at: datetime
    role: str


    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class TradeRequest(BaseModel):
    crypto_symbol: str
    quantity: float


class TradeResponse(BaseModel):
    id: int
    action: str
    crypto_symbol: str
    quantity: float
    execution_price: float
    total_cost: float
    fee: float
    profit_loss: Optional[float] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioResponse(BaseModel):
    id: int
    crypto_symbol: str
    quantity: float
    average_buy_price: float
    current_value: float
    profit_loss: float

    model_config = ConfigDict(from_attributes=True)


class PortfolioSummary(BaseModel):
    fiat_balance: float
    total_crypto_value: float
    total_net_worth: float
    total_profit_loss: float


class PortfolioFullResponse(BaseModel):
    summary: PortfolioSummary
    holdings: List[PortfolioResponse]


class LoanRequest(BaseModel):
    amount: float


class LoanResponse(BaseModel):
    approved: bool
    message: str
    new_fiat_balance: float
