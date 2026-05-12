from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import jwt
import bcrypt
from fastapi import HTTPException

import models
import schemas
from config import settings

def get_password_hash(password: str) -> str:
    # bcrypt requires bytes, so we encode the password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    # decode to return a string for storage in the DB
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


def buy_crypto(db: Session, user: models.User, crypto_symbol: str, quantity: float):
    crypto = get_crypto_by_symbol(db, crypto_symbol)
    if not crypto:
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")
    
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    price = float(crypto.current_price)
    
    value = price * quantity
    if value < 10:
        raise HTTPException(status_code=400, detail="Minimum trade size is $10")
    fee = value * 0.001  # 0.1% fee
    total_cost = value + fee
    
    if float(user.fiat_balance) < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient fiat balance")
        
    user.fiat_balance = float(user.fiat_balance) - total_cost
    
    portfolio = db.query(models.Portfolio).filter(
        models.Portfolio.user_id == user.id,
        models.Portfolio.crypto_id == crypto.id
    ).first()
    
    if portfolio:
        old_quantity = float(portfolio.quantity)
        old_avg_price = float(portfolio.average_buy_price)
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
        "quantity": float(transaction.quantity),
        "execution_price": float(transaction.execution_price),
        "total_cost": float(transaction.total_cost),
        "fee": float(transaction.fee),
        "profit_loss": None,
        "timestamp": transaction.timestamp
    }


def sell_crypto(db: Session, user: models.User, crypto_symbol: str, quantity: float):
    crypto = get_crypto_by_symbol(db, crypto_symbol)
    if not crypto:
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")
        
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    portfolio = db.query(models.Portfolio).filter(
        models.Portfolio.user_id == user.id,
        models.Portfolio.crypto_id == crypto.id
    ).first()
    
    if not portfolio or float(portfolio.quantity) < quantity:
        raise HTTPException(status_code=400, detail="Insufficient crypto balance")
        
    price = float(crypto.current_price)
    
    value = price * quantity
    if value < 10:
        raise HTTPException(status_code=400, detail="Minimum trade size is $10")
    fee = value * 0.001  # 0.1% fee
    total_payout = value - fee
    
    buy_cost_for_sold_tokens = float(portfolio.average_buy_price) * quantity
    profit_loss = total_payout - buy_cost_for_sold_tokens
    
    user.fiat_balance = float(user.fiat_balance) + total_payout
    
    portfolio.quantity = float(portfolio.quantity) - quantity
    if portfolio.quantity == 0:
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
        "quantity": float(transaction.quantity),
        "execution_price": float(transaction.execution_price),
        "total_cost": float(transaction.total_cost),
        "fee": float(transaction.fee),
        "profit_loss": float(transaction.profit_loss) if transaction.profit_loss else None,
        "timestamp": transaction.timestamp
    }


def get_user_portfolio(db: Session, user: models.User):
    portfolios = db.query(models.Portfolio).filter(models.Portfolio.user_id == user.id).all()
    
    portfolio_responses = []
    total_crypto_value = 0.0
    total_profit_loss = 0.0
    
    for p in portfolios:
        crypto = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.id == p.crypto_id).first()
        current_price = float(crypto.current_price) if crypto else 0.0
        quantity = float(p.quantity)
        avg_buy_price = float(p.average_buy_price)
        
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
        
    fiat_balance = float(user.fiat_balance)
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
            "quantity": float(t.quantity),
            "execution_price": float(t.execution_price),
            "total_cost": float(t.total_cost),
            "fee": float(t.fee),
            "profit_loss": float(t.profit_loss) if t.profit_loss is not None else None,
            "timestamp": t.timestamp
        })
    return transaction_responses

def request_loan(db: Session, user: models.User, amount: float):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Loan amount must be greater than 0")
        
    portfolio_data = get_user_portfolio(db, user)
    total_net_worth = portfolio_data["summary"]["total_net_worth"]
    
    if total_net_worth+amount >= 50000:
        return {
            "approved": False,
            "message": "Loan denied: Total net worth is 50,000 or more.",
            "new_fiat_balance": float(user.fiat_balance),
            "new_net_worth": total_net_worth
        }
        
    user.fiat_balance = float(user.fiat_balance) + amount
    db.commit()
    db.refresh(user)
    
    return {
        "approved": True,
        "message": f"Loan approved for {amount}. Added to your fiat balance.",
        "new_fiat_balance": float(user.fiat_balance),
        "new_net_worth": total_net_worth + amount
    }

import urllib.request
import json

def get_real_candlestick_data(symbol: str, days: int = 30):
    # Binance uses USDT pairs (e.g., BTCUSDT, ETHUSDT)
    binance_symbol = f"{symbol.upper()}USDT"
    url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval=1d&limit={days}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
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