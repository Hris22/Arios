import enum
from sqlalchemy import (Column, Integer, String, Numeric, DateTime, ForeignKey,
                        UniqueConstraint, Enum)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ActionType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class RoleType(str, enum.Enum):
    TRADER = "TRADER"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    fiat_balance = Column(Numeric(precision=15, scale=2), nullable=False, default=10000.00)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    role = Column(Enum(RoleType), nullable=False, default=RoleType.TRADER)

    # A user can have many portfolio entries
    portfolios = relationship("Portfolio", back_populates="owner")
    # A user can have many transactions
    transactions = relationship("Transaction", back_populates="user")


class Cryptocurrency(Base):
    __tablename__ = "cryptocurrencies"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    current_price = Column(Numeric(precision=20, scale=8), nullable=False)
    # Storing these as strings as they come from the scraper with '%' and '$'
    change_1h = Column(String)
    change_24h = Column(String)
    change_7d = Column(String)
    market_cap = Column(String)
    volume_24h = Column(String)
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (UniqueConstraint('user_id', 'crypto_id', name='_user_crypto_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    crypto_id = Column(Integer, ForeignKey("cryptocurrencies.id"), nullable=False)
    quantity = Column(Numeric(precision=20, scale=8), nullable=False)
    average_buy_price = Column(Numeric(precision=20, scale=8), nullable=False)

    owner = relationship("User", back_populates="portfolios")
    crypto = relationship("Cryptocurrency")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    crypto_id = Column(Integer, ForeignKey("cryptocurrencies.id"), nullable=False)
    action = Column(Enum(ActionType), nullable=False)
    quantity = Column(Numeric(precision=20, scale=8), nullable=False)
    execution_price = Column(Numeric(precision=20, scale=8), nullable=False)
    total_cost = Column(Numeric(precision=20, scale=4), nullable=False)
    fee = Column(Numeric(precision=20, scale=4), nullable=False, default=0)
    profit_loss = Column(Numeric(precision=20, scale=4), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")
    crypto = relationship("Cryptocurrency")


class HistoricalPrice(Base):
    __tablename__ = "historical_prices"

    id = Column(Integer, primary_key=True, index=True)
    crypto_id = Column(Integer, ForeignKey("cryptocurrencies.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    open = Column(Numeric(precision=20, scale=8), nullable=False)
    high = Column(Numeric(precision=20, scale=8), nullable=False)
    low = Column(Numeric(precision=20, scale=8), nullable=False)
    close = Column(Numeric(precision=20, scale=8), nullable=False)