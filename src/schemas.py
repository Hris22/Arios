from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional, List
from decimal import Decimal


class CryptoBase(BaseModel):
    symbol: str
    name: str
    current_price: Decimal
    change_1h: Optional[str] = None
    change_24h: Optional[str] = None
    change_7d: Optional[str] = None
    market_cap: Optional[str] = None
    volume_24h: Optional[str] = None


class CryptoResponse(CryptoBase):
    id: int
    last_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    fiat_balance: Decimal
    created_at: datetime
    role: str


    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[EmailStr] = None


class TradeRequest(BaseModel):
    crypto_symbol: str
    quantity: Decimal


class TradeResponse(BaseModel):
    id: int
    action: str
    crypto_symbol: str
    quantity: Decimal
    execution_price: Decimal
    total_cost: Decimal
    fee: Decimal
    profit_loss: Optional[Decimal] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioResponse(BaseModel):
    id: int
    crypto_symbol: str
    quantity: Decimal
    average_buy_price: Decimal
    current_value: Decimal
    profit_loss: Decimal

    model_config = ConfigDict(from_attributes=True)


class PortfolioSummary(BaseModel):
    fiat_balance: Decimal
    total_crypto_value: Decimal
    total_net_worth: Decimal
    total_profit_loss: Decimal


class PortfolioFullResponse(BaseModel):
    summary: PortfolioSummary
    holdings: List[PortfolioResponse]


class LoanRequest(BaseModel):
    amount: Decimal


class LoanResponse(BaseModel):
    approved: bool
    message: str
    new_fiat_balance: Decimal
    new_net_worth: Decimal


class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
