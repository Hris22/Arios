from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List
from datetime import timedelta
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
import jwt

from src import scraper
from src.database import SessionLocal, engine
from src import models
from src import schemas
from src import services
from src.config import settings
from src import chatbot

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

# Ensure database tables are created
models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code here runs on application startup
    print("Starting background scraper...")
    scheduler = BackgroundScheduler()
    scheduler.add_job(scraper.scrape_data, 'interval', seconds=60)
    scheduler.start()
    
    yield # This yields control back to FastAPI to run the application
    
    # Code here runs on application shutdown
    print("Shutting down background scraper...")
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# Mount the 'static' directory to serve static files like images, css, etc.
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    user = services.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user

def get_current_admin_user(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleType.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@app.get("/profile")
def profile_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html")

@app.get("/admin")
def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")

@app.get("/components/profile_data")
def profile_data(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    portfolio = services.get_user_portfolio(db, current_user)
    transactions = services.get_user_transactions(db, current_user)
    return templates.TemplateResponse(request=request, name="components/profile_data.html", context={"user": current_user, "portfolio": portfolio, "transactions": transactions})

@app.get("/components/watchlist")
def get_watchlist(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user), edit_mode: bool = False):
    watchlist_items = db.query(models.Watchlist).filter(models.Watchlist.user_id == current_user.id).all()
    cryptos = [item.crypto for item in watchlist_items]
    return templates.TemplateResponse(request=request, name="components/watchlist.html", context={"cryptos": cryptos, "edit_mode": edit_mode})

from fastapi import Form

@app.post("/api/watchlist")
def add_to_watchlist(request: Request, symbol: str = Form(...), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    crypto = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == symbol.upper()).first()
    if not crypto:
        # Instead of 404, we can just return the watchlist unchanged, or maybe add an error message context.
        # But for simplicity, let's just return the watchlist.
        return get_watchlist(request, db, current_user, edit_mode=False)
    
    existing = db.query(models.Watchlist).filter(models.Watchlist.user_id == current_user.id, models.Watchlist.crypto_id == crypto.id).first()
    if not existing:
        new_item = models.Watchlist(user_id=current_user.id, crypto_id=crypto.id)
        db.add(new_item)
        db.commit()
        
    return get_watchlist(request, db, current_user, edit_mode=False)

@app.delete("/api/watchlist/{symbol}")
def remove_from_watchlist(symbol: str, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    crypto = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == symbol.upper()).first()
    if not crypto:
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")
        
    item = db.query(models.Watchlist).filter(models.Watchlist.user_id == current_user.id, models.Watchlist.crypto_id == crypto.id).first()
    if item:
        db.delete(item)
        db.commit()
        
    return get_watchlist(request, db, current_user, edit_mode=True)

@app.get("/components/stats")
def get_stats(request: Request, symbol: str = "BTC", db: Session = Depends(get_db)):
    crypto = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == symbol.upper()).first()
    return templates.TemplateResponse(request=request, name="components/stats.html", context={"crypto": crypto})

@app.get("/components/crypto_table")
def get_crypto_table(request: Request, db: Session = Depends(get_db)):
    cryptos = db.query(models.Cryptocurrency).all()
    return templates.TemplateResponse(request=request, name="components/crypto_table.html", context={"cryptos": cryptos})

@app.get("/api/cryptos", response_model=List[schemas.CryptoResponse])
def get_cryptos(db: Session = Depends(get_db)):
    cryptos = db.query(models.Cryptocurrency).all()
    return cryptos

@app.get("/api/chart/{symbol}")
async def get_chart_data(symbol: str, db: Session = Depends(get_db)):
    data = await services.get_real_candlestick_data(symbol, days=30)
    if not data:
        raise HTTPException(status_code=404, detail="Cryptocurrency data not found")
    return data

@app.post("/api/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = services.get_user_by_email(db, email=user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    return services.create_user(db=db, user=user)

@app.post("/api/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = services.authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = services.create_access_token(
        data={"sub": user.email, "role": user.role.value}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/admin/users", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin_user)):
    return services.get_all_users(db)

@app.delete("/api/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin_user)):
    user = services.get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    services.delete_user(db, user=user)
    return None

@app.post("/api/trade/buy", response_model=schemas.TradeResponse)
def buy_crypto_endpoint(request: schemas.TradeRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return services.buy_crypto(db, current_user, request.crypto_symbol, request.quantity)

@app.post("/api/trade/sell", response_model=schemas.TradeResponse)
def sell_crypto_endpoint(request: schemas.TradeRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return services.sell_crypto(db, current_user, request.crypto_symbol, request.quantity)

@app.get("/api/portfolio", response_model=schemas.PortfolioFullResponse)
def get_portfolio_endpoint(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return services.get_user_portfolio(db, current_user)

@app.get("/api/transactions", response_model=List[schemas.TradeResponse])
def get_transactions_endpoint(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return services.get_user_transactions(db, current_user)

@app.post("/api/loan", response_model=schemas.LoanResponse)
def request_loan_endpoint(request: schemas.LoanRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return services.request_loan(db, current_user, request.amount)

@app.post("/api/chat", response_model=schemas.ChatResponse)
def chat_with_consultant(request: schemas.ChatRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Notice we pass the db session so the chatbot's tools can read live crypto prices
    reply = chatbot.get_chat_response(db, current_user, request.message)
    return {"reply": reply}