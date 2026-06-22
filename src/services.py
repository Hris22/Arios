from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import jwt
import bcrypt
from fastapi import HTTPException
from decimal import Decimal

from src import models
from src import schemas
from src.config import settings

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_all_users(db: Session) -> List[models.User]:
    return db.query(models.User).all()

def delete_user(db: Session, user: models.User):
    db.delete(user)
    db.commit()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    hashed_password = get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def get_crypto_by_symbol(db: Session, symbol: str) -> Optional[models.Cryptocurrency]:
    return db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == symbol.upper()).first()


def buy_crypto(db: Session, user: models.User, crypto_symbol: str, quantity: Decimal):
    crypto = get_crypto_by_symbol(db, crypto_symbol)
    if not crypto:
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")
    
    if quantity <= Decimal('0'):
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    price = Decimal(str(crypto.current_price))
    
    value = price * quantity
    if value < Decimal('10'):
        raise HTTPException(status_code=400, detail="Minimum trade size is $10")
    fee = value * Decimal('0.001')  # 0.1% fee
    total_cost = value + fee
    
    if Decimal(str(user.fiat_balance)) < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient fiat balance")
        
    user.fiat_balance = Decimal(str(user.fiat_balance)) - total_cost
    
    portfolio = db.query(models.Portfolio).filter(
        models.Portfolio.user_id == user.id,
        models.Portfolio.crypto_id == crypto.id
    ).first()
    
    if portfolio:
        old_quantity = Decimal(str(portfolio.quantity))
        old_avg_price = Decimal(str(portfolio.average_buy_price))
        new_quantity = old_quantity + quantity
        portfolio.average_buy_price = ((old_quantity * old_avg_price) + value) / new_quantity
        portfolio.quantity = new_quantity
    else:
        portfolio = models.Portfolio(
            user_id=user.id,
            crypto_id=crypto.id,
            quantity=quantity,
            average_buy_price=price
        )
        db.add(portfolio)
        
    transaction = models.Transaction(
        user_id=user.id,
        crypto_id=crypto.id,
        action=models.ActionType.BUY,
        quantity=quantity,
        execution_price=price,
        total_cost=total_cost,
        fee=fee
    )
    db.add(transaction)
    
    db.commit()
    db.refresh(transaction)
    
    return {
        "id": transaction.id,
        "action": transaction.action.value,
        "crypto_symbol": crypto.symbol,
        "quantity": transaction.quantity,
        "execution_price": transaction.execution_price,
        "total_cost": transaction.total_cost,
        "fee": transaction.fee,
        "profit_loss": None,
        "timestamp": transaction.timestamp
    }


def sell_crypto(db: Session, user: models.User, crypto_symbol: str, quantity: Decimal):
    crypto = get_crypto_by_symbol(db, crypto_symbol)
    if not crypto:
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")
        
    if quantity <= Decimal('0'):
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    portfolio = db.query(models.Portfolio).filter(
        models.Portfolio.user_id == user.id,
        models.Portfolio.crypto_id == crypto.id
    ).first()
    
    if not portfolio or Decimal(str(portfolio.quantity)) < quantity:
        raise HTTPException(status_code=400, detail="Insufficient crypto balance")
        
    price = Decimal(str(crypto.current_price))
    
    value = price * quantity
    if value < Decimal('10'):
        raise HTTPException(status_code=400, detail="Minimum trade size is $10")
    fee = value * Decimal('0.001')  # 0.1% fee
    total_payout = value - fee
    
    buy_cost_for_sold_tokens = Decimal(str(portfolio.average_buy_price)) * quantity
    profit_loss = total_payout - buy_cost_for_sold_tokens
    
    user.fiat_balance = Decimal(str(user.fiat_balance)) + total_payout
    
    portfolio.quantity = Decimal(str(portfolio.quantity)) - quantity
    if portfolio.quantity == Decimal('0'):
        db.delete(portfolio)
        
    transaction = models.Transaction(
        user_id=user.id,
        crypto_id=crypto.id,
        action=models.ActionType.SELL,
        quantity=quantity,
        execution_price=price,
        total_cost=total_payout,
        fee=fee,
        profit_loss=profit_loss
    )
    db.add(transaction)
    
    db.commit()
    db.refresh(transaction)
    
    return {
        "id": transaction.id,
        "action": transaction.action.value,
        "crypto_symbol": crypto.symbol,
        "quantity": transaction.quantity,
        "execution_price": transaction.execution_price,
        "total_cost": transaction.total_cost,
        "fee": transaction.fee,
        "profit_loss": transaction.profit_loss if transaction.profit_loss else None,
        "timestamp": transaction.timestamp
    }


def get_user_portfolio(db: Session, user: models.User):
    portfolios = db.query(models.Portfolio).filter(models.Portfolio.user_id == user.id).all()
    
    portfolio_responses = []
    total_crypto_value = Decimal('0.0')
    total_profit_loss = Decimal('0.0')
    
    for p in portfolios:
        crypto = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.id == p.crypto_id).first()
        current_price = Decimal(str(crypto.current_price)) if crypto else Decimal('0.0')
        quantity = Decimal(str(p.quantity))
        avg_buy_price = Decimal(str(p.average_buy_price))
        
        current_value = current_price * quantity
        total_buy_cost = avg_buy_price * quantity
        profit_loss = current_value - total_buy_cost
        
        total_crypto_value += current_value
        total_profit_loss += profit_loss
        
        portfolio_responses.append({
            "id": p.id,
            "crypto_symbol": crypto.symbol if crypto else "UNKNOWN",
            "quantity": quantity,
            "average_buy_price": avg_buy_price,
            "current_value": current_value,
            "profit_loss": profit_loss
        })
        
    fiat_balance = Decimal(str(user.fiat_balance))
    total_net_worth = fiat_balance + total_crypto_value
    
    return {
        "summary": {
            "fiat_balance": fiat_balance,
            "total_crypto_value": total_crypto_value,
            "total_net_worth": total_net_worth,
            "total_profit_loss": total_profit_loss
        },
        "holdings": portfolio_responses
    }

def get_user_transactions(db: Session, user: models.User):
    transactions = db.query(models.Transaction).filter(models.Transaction.user_id == user.id).order_by(models.Transaction.timestamp.desc()).all()
    
    transaction_responses = []
    for t in transactions:
        crypto = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.id == t.crypto_id).first()
        transaction_responses.append({
            "id": t.id,
            "action": t.action.value,
            "crypto_symbol": crypto.symbol if crypto else "UNKNOWN",
            "quantity": t.quantity,
            "execution_price": t.execution_price,
            "total_cost": t.total_cost,
            "fee": t.fee,
            "profit_loss": t.profit_loss if t.profit_loss is not None else None,
            "timestamp": t.timestamp
        })
    return transaction_responses

def request_loan(db: Session, user: models.User, amount: Decimal):
    if amount <= Decimal('0'):
        raise HTTPException(status_code=400, detail="Loan amount must be greater than 0")
        
    portfolio_data = get_user_portfolio(db, user)
    total_net_worth = portfolio_data["summary"]["total_net_worth"]
    
    if total_net_worth+amount >= Decimal('50000'):
        return {
            "approved": False,
            "message": "Loan denied: Total net worth is 50,000 or more.",
            "new_fiat_balance": user.fiat_balance,
            "new_net_worth": total_net_worth
        }
        
    user.fiat_balance = Decimal(str(user.fiat_balance)) + amount
    db.commit()
    db.refresh(user)
    
    return {
        "approved": True,
        "message": f"Loan approved for {amount}. Added to your fiat balance.",
        "new_fiat_balance": user.fiat_balance,
        "new_net_worth": total_net_worth + amount
    }

import httpx

async def get_real_candlestick_data(symbol: str, days: int = 30):
    # Binance uses USDT pairs (e.g., BTCUSDT, ETHUSDT)
    binance_symbol = f"{symbol.upper()}USDT"
    url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval=1d&limit={days}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            data = response.json()
            
        chart_data = []
        for kline in data:
            chart_data.append({
                "x": kline[0], # Open time in ms
                "y": [
                    float(kline[1]), # Open
                    float(kline[2]), # High
                    float(kline[3]), # Low
                    float(kline[4])  # Close
                ]
            })
        return chart_data
    except Exception as e:
        print(f"Error fetching chart data from Binance: {e}")
        return []