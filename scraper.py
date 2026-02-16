from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import os


chrome_options = Options()
chrome_options.add_argument("--headless")
# This downloads the correct driver for your Chrome version automatically
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

url = "https://coinmarketcap.com/"

driver.get(url) 
time.sleep(5)

def scrape_data():
    driver.get(url) 
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    rows = soup.find("tbody").find_all("tr", limit=16)
    #print(f"Found {len(rows)} rows in the table.")

    data = []
    for row in rows[1:]: 
        cols = row.get_text(separator="|", strip=True).split("|")  
        data.append(cols[1:11]) 
        
    df = pd.DataFrame(data, columns=["Name", "Symbol", "", "Price", "1h %", "24h %","7d %",  "Market Cap","Volume","Circulating Supply"]) 
    #print(df) 
    df.to_csv("crypto_data.csv", index=False)
