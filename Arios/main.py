import scraper
import time
from database import engine, Base
import models

# This command connects to the database and creates all the tables
# defined in models.py if they don't already exist.
print("Initializing database...")
Base.metadata.create_all(bind=engine)
print("Database initialized successfully.")

while True:
    scraper.scrape_data()
    print("Waiting 60 seconds before next scrape...")
    time.sleep(60)
