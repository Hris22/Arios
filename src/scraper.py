import urllib.request
import json
from src.database import SessionLocal
from src.models import Cryptocurrency

def scrape_data():
    # CoinGecko API endpoint for top 15 coins by market cap with 1h, 24h, and 7d changes
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd"
        "&order=market_cap_desc"
        "&per_page=15"
        "&page=1"
        "&sparkline=false"
        "&price_change_percentage=1h,24h,7d"
    )

    print("Fetching latest crypto data from CoinGecko API...")
    db = SessionLocal()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        for coin in data:
            symbol = coin.get('symbol', '').upper()
            name = coin.get('name', '')
            current_price = float(coin.get('current_price') or 0.0)
            
            c_1h = coin.get('price_change_percentage_1h_in_currency')
            change_1h = f"{c_1h:.2f}%" if c_1h is not None else "0.00%"
            
            c_24h = coin.get('price_change_percentage_24h_in_currency')
            change_24h = f"{c_24h:.2f}%" if c_24h is not None else "0.00%"
            
            c_7d = coin.get('price_change_percentage_7d_in_currency')
            change_7d = f"{c_7d:.2f}%" if c_7d is not None else "0.00%"
            
            mcap = coin.get('market_cap')
            market_cap = f"${mcap:,.0f}" if mcap is not None else "$0"
            
            vol = coin.get('total_volume')
            volume_24h = f"${vol:,.0f}" if vol is not None else "$0"

            # Query existing cryptocurrency or create a new one
            crypto = db.query(Cryptocurrency).filter(Cryptocurrency.symbol == symbol).first()
            if not crypto:
                crypto = Cryptocurrency(symbol=symbol, name=name)
                db.add(crypto)
            
            crypto.name = name
            crypto.current_price = current_price
            crypto.change_1h = change_1h
            crypto.change_24h = change_24h
            crypto.change_7d = change_7d
            crypto.market_cap = market_cap
            crypto.volume_24h = volume_24h
            
        db.commit()
        print("Successfully updated the database with the latest crypto data from CoinGecko.")
    except Exception as e:
        print(f"Database/API error: {e}")
        db.rollback()
    finally:
        db.close()
