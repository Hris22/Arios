from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import os
from database import SessionLocal
from models import Cryptocurrency


chrome_options = Options()
chrome_options.add_argument("--headless")
# This downloads the correct driver for your Chrome version automatically
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

url = "https://coinmarketcap.com/"

driver.get(url) 
time.sleep(5)

def scrape_data():
    driver.get(url) 
    time.sleep(5) # Wait for the page to load
    soup = BeautifulSoup(driver.page_source, "html.parser")

    rows = soup.find("tbody").find_all("tr", limit=16)
    #print(f"Found {len(rows)} rows in the table.")

    db = SessionLocal()
    try:
        for row in rows[1:]: 
            cols = row.get_text(separator="|", strip=True).split("|")  
            data_row = cols[1:11]
            
            if len(data_row) < 10:
                continue
                
            name = data_row[0]
            symbol = data_row[1]
            price_str = data_row[3]
            
            # Clean price string (e.g., "$69,897.16" -> 69897.16) to store as Numeric
            try:
                clean_price = float(price_str.replace('$', '').replace(',', ''))
            except ValueError:
                clean_price = 0.0

            # Query existing cryptocurrency or create a new one
            crypto = db.query(Cryptocurrency).filter(Cryptocurrency.symbol == symbol).first()
            if not crypto:
                crypto = Cryptocurrency(symbol=symbol, name=name)
                db.add(crypto)
            
            # Update the fields
            crypto.current_price = clean_price
            crypto.change_1h = data_row[4]
            crypto.change_24h = data_row[5]
            crypto.change_7d = data_row[6]
            crypto.market_cap = data_row[7]
            crypto.volume_24h = data_row[8]
            
        db.commit()
        print("Successfully updated the database with the latest crypto data.")
    except Exception as e:
        print(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()
