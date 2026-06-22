from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from src.config import settings
from src import services
from src import models

client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

SYSTEM_PROMPT = """
You are Arios, an expert cryptocurrency investing consultant.
Your job is to provide market insights, brief overviews of specific coins, and summarize recent news.
You must decline any requests that are not related to cryptocurrencies, investing, or the user's portfolio.
When asked about a specific coin, always use your tools to fetch the latest data and news before answering.
When asked about the user's portfolio, use your tool to fetch their current holdings and balances.
Be concise, professional, and helpful.
"""

def get_chat_response(db: Session, current_user: models.User, user_message: str) -> str:
    if not client:
        return "System Error: Gemini API Key is not configured."

    def get_crypto_price_and_stats(symbol: str) -> dict:
        crypto = services.get_crypto_by_symbol(db, symbol)
        if not crypto:
            return {"error": f"Could not find cryptocurrency with symbol {symbol} in our database."}
        return {
            "symbol": crypto.symbol,
            "name": crypto.name,
            "current_price": float(crypto.current_price),
            "change_24h": crypto.change_24h,
            "market_cap": crypto.market_cap
        }

    def get_recent_crypto_news(symbol: str) -> str:
        if not settings.NEWS_API_KEY:
            return f"News API key not configured. Cannot fetch recent news for {symbol}."

        try:
            import httpx
            # We use NewsAPI here to fetch the top 3 recent articles
            url = f"https://newsapi.org/v2/everything?q={symbol}+crypto&sortBy=publishedAt&language=en&pageSize=3&apiKey={settings.NEWS_API_KEY}"
            response = httpx.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            articles = data.get("articles", [])
            if not articles:
                return f"No recent news found for {symbol}."

            headlines = [f"- {article['title']}: {article['description']}" for article in articles]
            return "\n".join(headlines)
        except Exception as e:
            return f"Error fetching news for {symbol}: {str(e)}"
            
    def get_user_portfolio() -> dict:
        portfolio = services.get_user_portfolio(db, current_user)
        from decimal import Decimal
        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert_decimals(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimals(item) for item in obj]
            return obj
        return convert_decimals(portfolio)

    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[get_crypto_price_and_stats, get_recent_crypto_news, get_user_portfolio],
        )
    )

    response = chat.send_message(user_message)
    
    return response.text