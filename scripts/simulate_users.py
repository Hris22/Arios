import time
from decimal import Decimal
from src.database import SessionLocal
from src import models
from src import schemas
from src import services

def run_simulation():
    db = SessionLocal()
    print("Starting simulation...")

    try:
        # 1. Clear existing test data (Optional, but good for repeatable tests)
        # We will just rely on unique constraints and catch exceptions if we run it multiple times.
        
        # 2. Add Dummy Cryptocurrencies
        print("\n--- Populating Cryptocurrencies ---")
        cryptos = [
            {"symbol": "BTC", "name": "Bitcoin", "price": "65000.00"},
            {"symbol": "ETH", "name": "Ethereum", "price": "3500.00"},
            {"symbol": "SOL", "name": "Solana", "price": "140.00"}
        ]
        
        for c in cryptos:
            existing_crypto = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == c["symbol"]).first()
            if not existing_crypto:
                new_crypto = models.Cryptocurrency(
                    symbol=c["symbol"],
                    name=c["name"],
                    current_price=Decimal(c["price"]),
                    change_1h="0.5%",
                    change_24h="2.1%",
                    change_7d="-1.5%",
                    market_cap="1.2T",
                    volume_24h="30B"
                )
                db.add(new_crypto)
                print(f"Added crypto: {c['name']} ({c['symbol']}) at ${c['price']}")
        db.commit()

        # 3. Create Users
        print("\n--- Creating Users ---")
        users_data = [
            {"email": "trader1@example.com", "password": "password123"},
            {"email": "trader2@example.com", "password": "password456"}
        ]
        
        traders = []
        for ud in users_data:
            existing_user = db.query(models.User).filter(models.User.email == ud["email"]).first()
            if existing_user:
                traders.append(existing_user)
                print(f"User {ud['email']} already exists.")
            else:
                user_schema = schemas.UserCreate(email=ud["email"], password=ud["password"])
                new_user = services.create_user(db, user_schema)
                traders.append(new_user)
                print(f"Created user: {ud['email']} with starting balance ${new_user.fiat_balance}")

        trader1 = traders[0]
        trader2 = traders[1]

        # 4. Perform Trades
        print("\n--- Executing Trades ---")
        
        # Trader 1 Buys 0.1 BTC and 10 SOL
        print(f"Trader 1 buying 0.1 BTC...")
        services.buy_crypto(db, trader1, "BTC", Decimal("0.1"))
        print(f"Trader 1 buying 10 SOL...")
        services.buy_crypto(db, trader1, "SOL", Decimal("10.0"))
        
        # Trader 2 Buys 2 ETH
        print(f"Trader 2 buying 2 ETH...")
        services.buy_crypto(db, trader2, "ETH", Decimal("2.0"))
        
        # Simulate price changes to test profit/loss
        print("\nSimulating market price changes...")
        btc = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == "BTC").first()
        btc.current_price = Decimal("70000.00") # BTC goes up!
        db.commit()

        # Trader 1 Sells 0.05 BTC for profit
        print(f"Trader 1 selling 0.05 BTC at new price ${btc.current_price}...")
        services.sell_crypto(db, trader1, "BTC", Decimal("0.05"))

        # 5. Add to Watchlist
        print("\n--- Managing Watchlist ---")
        # Trader 2 watches SOL
        sol = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == "SOL").first()
        existing_watch = db.query(models.Watchlist).filter(
            models.Watchlist.user_id == trader2.id, models.Watchlist.crypto_id == sol.id
        ).first()
        if not existing_watch:
            watch = models.Watchlist(user_id=trader2.id, crypto_id=sol.id)
            db.add(watch)
            db.commit()
            print(f"Trader 2 added SOL to watchlist.")

        # 6. Output Portfolio and Transactions (Verification)
        print("\n--- Final Output Verification ---")
        for trader in traders:
            print(f"\n[ Portfolio for {trader.email} ]")
            # Refresh user from DB to get latest fiat balance
            db.refresh(trader)
            portfolio_data = services.get_user_portfolio(db, trader)
            
            print(f"  Fiat Balance: ${portfolio_data['summary']['fiat_balance']:.2f}")
            print(f"  Total Crypto Value: ${portfolio_data['summary']['total_crypto_value']:.2f}")
            print(f"  Total Net Worth: ${portfolio_data['summary']['total_net_worth']:.2f}")
            print(f"  Total P/L: ${portfolio_data['summary']['total_profit_loss']:.2f}")
            
            print("  Holdings:")
            for h in portfolio_data['holdings']:
                print(f"    - {h['quantity']} {h['crypto_symbol']} | Current Value: ${h['current_value']:.2f} | P/L: ${h['profit_loss']:.2f}")
            
            print("  Recent Transactions:")
            txs = services.get_user_transactions(db, trader)
            for tx in txs:
                pl_str = f" | P/L: ${tx['profit_loss']:.2f}" if tx['profit_loss'] else ""
                print(f"    - {tx['action']} {tx['quantity']} {tx['crypto_symbol']} at ${tx['execution_price']:.2f} (Fee: ${tx['fee']:.2f}){pl_str}")

        print("\nSimulation complete! All core functionalities successfully tested on PostgreSQL.")

    except Exception as e:
        print(f"\nSimulation Failed with error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_simulation()