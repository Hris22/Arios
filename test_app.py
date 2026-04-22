import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from app import app, get_db
from database import Base
import models
from services import get_password_hash

# Setup an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Mock the BackgroundScheduler so the scraper doesn't run during tests
@pytest.fixture(autouse=True)
def mock_scheduler():
    with patch("app.BackgroundScheduler"):
        yield

@pytest.fixture()
def db_session():
    # Create tables in the in-memory database
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    # Drop tables after the test runs to ensure a clean slate
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def client(db_session, monkeypatch):
    # Set a dummy secret key for JWT token creation during tests
    # This prevents tests from failing if .env is not set.
    monkeypatch.setattr("config.settings.SECRET_KEY", "test_secret_key_for_jwt")

    # Override the get_db dependency to use the test database
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Crypto API!"}

def test_register_user(client):
    response = client.post(
        "/api/register",
        json={"email": "test@example.com", "password": "password123"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data

def test_register_existing_user(client):
    # Register first time
    client.post("/api/register", json={"email": "duplicate@example.com", "password": "pass"})
    
    # Try to register again with the same email
    response = client.post("/api/register", json={"email": "duplicate@example.com", "password": "pass"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"

def test_login_user(client):
    # Register user to login
    client.post("/api/register", json={"email": "login@example.com", "password": "password123"})
    
    # OAuth2PasswordRequestForm expects form-encoded data, not JSON
    response = client.post(
        "/api/login",
        data={"username": "login@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_get_cryptos(client, db_session):
    # Seed testing database with a cryptocurrency
    crypto = models.Cryptocurrency(symbol="BTC", name="Bitcoin", current_price=50000.0)
    db_session.add(crypto)
    db_session.commit()

    response = client.get("/api/cryptos")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "BTC"
    assert data[0]["current_price"] == 50000.0

def test_admin_get_users(client, db_session):
    # Create an admin user directly in the database
    admin_user = models.User(
        email="admin@example.com",
        hashed_password=get_password_hash("adminpass"),
        role=models.RoleType.ADMIN
    )
    db_session.add(admin_user)
    db_session.commit()

    # Login to get admin token
    login_resp = client.post("/api/login", data={"username": "admin@example.com", "password": "adminpass"})
    token = login_resp.json()["access_token"]

    # Request users list as admin
    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["email"] == "admin@example.com"