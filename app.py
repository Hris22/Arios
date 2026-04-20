from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List
from datetime import timedelta
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

import scraper
from database import SessionLocal, engine
import models
import schemas
import services
from config import settings

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

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Crypto API!"}

@app.get("/api/cryptos", response_model=List[schemas.CryptoResponse])
def get_cryptos(db: Session = Depends(get_db)):
    cryptos = db.query(models.Cryptocurrency).all()
    return cryptos

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
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}