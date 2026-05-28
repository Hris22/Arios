import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from src.main import app, get_db
from src.database import Base
from src import models
from src.services import get_password_hash

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
    with patch("src.main.BackgroundScheduler"):
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
    monkeypatch.setattr("src.config.settings.SECRET_KEY", "test_secret_key_for_jwt")

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
    assert "text/html" in response.headers.get("content-type", "")

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
    assert float(data[0]["current_price"]) == 50000.0

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

@pytest.fixture()
def regular_user_token(client, db_session):
    user = models.User(
        email="trader@example.com",
        hashed_password=get_password_hash("password123"),
        fiat_balance=10000.0,
        role=models.RoleType.TRADER
    )
    db_session.add(user)
    db_session.commit()
    login_resp = client.post("/api/login", data={"username": "trader@example.com", "password": "password123"})
    return login_resp.json()["access_token"]

def test_buy_crypto_minimum_trade(client, db_session, regular_user_token):
    crypto = models.Cryptocurrency(symbol="BTC", name="Bitcoin", current_price=50000.0)
    db_session.add(crypto)
    db_session.commit()

    # Try to buy for less than $10 (0.0001 BTC = $5)
    response = client.post(
        "/api/trade/buy",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"crypto_symbol": "BTC", "quantity": 0.0001}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Minimum trade size is $10"

def test_buy_crypto_success(client, db_session, regular_user_token):
    crypto = models.Cryptocurrency(symbol="ETH", name="Ethereum", current_price=2000.0)
    db_session.add(crypto)
    db_session.commit()

    # Buy 1 ETH
    response = client.post(
        "/api/trade/buy",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"crypto_symbol": "ETH", "quantity": 1.0}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["crypto_symbol"] == "ETH"
    assert data["action"] == "BUY"
    assert float(data["quantity"]) == 1.0
    assert float(data["execution_price"]) == 2000.0
    assert float(data["fee"]) == 2.0 # 0.1% of $2000
    assert float(data["total_cost"]) == 2002.0

def test_sell_crypto_minimum_trade(client, db_session, regular_user_token):
    crypto = models.Cryptocurrency(symbol="ADA", name="Cardano", current_price=1.0)
    db_session.add(crypto)
    db_session.commit()
    
    user = db_session.query(models.User).filter(models.User.email == "trader@example.com").first()
    portfolio = models.Portfolio(user_id=user.id, crypto_id=crypto.id, quantity=100, average_buy_price=1.0)
    db_session.add(portfolio)
    db_session.commit()
    
    # Try to sell 5 ADA = $5
    response = client.post(
        "/api/trade/sell",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"crypto_symbol": "ADA", "quantity": 5.0}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Minimum trade size is $10"

def test_request_loan_success(client, db_session, regular_user_token):
    response = client.post(
        "/api/loan",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"amount": 5000.0}
    )
    assert response.status_code == 200
    assert response.json()["approved"] is True
    assert float(response.json()["new_fiat_balance"]) == 15000.0 # Started with 10000

def test_request_loan_denied_high_net_worth(client, db_session, regular_user_token):
    user = db_session.query(models.User).filter(models.User.email == "trader@example.com").first()
    user.fiat_balance = 55000.0 # Over 50000
    db_session.commit()

    response = client.post(
        "/api/loan",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"amount": 5000.0}
    )
    assert response.status_code == 200
    assert response.json()["approved"] is False
    assert float(response.json()["new_fiat_balance"]) == 55000.0

def test_chatbot_eth_info(client, db_session, regular_user_token):
    crypto = models.Cryptocurrency(symbol="ETH", name="Ethereum", current_price=3000.0)
    db_session.add(crypto)
    db_session.commit()

    response = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"message": "Can you give me some information and the current price of ETH?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "ETH" in data["reply"].upper()

def test_chatbot_portfolio_context(client, db_session, regular_user_token):
    crypto = models.Cryptocurrency(symbol="ETH", name="Ethereum", current_price=3000.0)
    db_session.add(crypto)
    
    # Increase user's fiat balance so they can buy 20 ETH
    user = db_session.query(models.User).filter(models.User.email == "trader@example.com").first()
    user.fiat_balance = 100000.0
    db_session.commit()

    # Buy 20 ETH
    buy_resp = client.post(
        "/api/trade/buy",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"crypto_symbol": "ETH", "quantity": 20.0}
    )
    assert buy_resp.status_code == 200

    # Ask the chatbot about ETH news and portfolio
    chat_resp = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"message": "I want to know about ETH news and how much ETH I currently own in my portfolio."}
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert "reply" in data
    # Check if the chatbot mentions the 20 ETH
    assert "20" in data["reply"]

def test_chatbot_invalid_crypto(client, db_session, regular_user_token):
    # Ask the chatbot about an invalid coin named HRISCOIN
    chat_resp = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"message": "Can you give me the price of HRISCOIN?"}
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert "reply" in data
    # The chatbot should gracefully handle the missing coin and mention it in the reply
    assert "HRISCOIN" in data["reply"].upper()

@patch("src.chatbot.client")
def test_chatbot_mocked_api(mock_chatbot_client, client, db_session, regular_user_token):
    # Setup the mock so that calling client.chats.create().send_message() returns our fake response
    mock_chat = mock_chatbot_client.chats.create.return_value
    mock_chat.send_message.return_value.text = "This is a fast, mocked response from Arios."

    # Send a message to the chatbot
    chat_resp = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={"message": "Tell me about the crypto market."}
    )

    assert chat_resp.status_code == 200
    data = chat_resp.json()

    # Verify the response matches our mock
    assert data["reply"] == "This is a fast, mocked response from Arios."

    # Verify that the Gemini API methods were actually called
    mock_chatbot_client.chats.create.assert_called_once()
    mock_chat.send_message.assert_called_once_with("Tell me about the crypto market.")