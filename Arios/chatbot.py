import google.generativeai as genai
from sqlalchemy.orm import Session

from config import settings
import services
import models

# Configure the Gemini API globally
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are Arios, an expert cryptocurrency investing consultant.
Your job is to provide market insights, brief overviews of specific coins, and summarize recent news.
You must decline any requests that are not related to cryptocurrencies, investing, or the user's portfolio.
When asked about a specific coin, always use your tools to fetch the latest data and news before answering.
When asked about the user's portfolio, use your tool to fetch their current holdings and balances.
Be concise, professional, and helpful.
"""

def get_chat_response(db: Session, current_user: models.User, user_message: str) -> str:
    if not settings.GEMINI_API_KEY:
        return "System Error: Gemini API Key is not configured."

    # 1. Define the tools (functions) Gemini can use
    def get_crypto_price_and_stats(symbol: str) -> dict:
        """Fetches the current price and market stats for a specific cryptocurrency symbol (e.g., BTC, ETH)."""
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
        """Fetches the most recent news headlines for a specific cryptocurrency."""
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
        """Fetches the current user's cryptocurrency portfolio, fiat balance, and total net worth."""
        return services.get_user_portfolio(db, current_user)

    # 2. Initialize the model with the tools and persona
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-live",
        system_instruction=SYSTEM_PROMPT,
        tools=[get_crypto_price_and_stats, get_recent_crypto_news, get_user_portfolio]
    )

    # 3. Start chat with automatic function calling enabled, and send the message
    chat = model.start_chat(enable_automatic_function_calling=True)
    response = chat.send_message(user_message)
    
    return response.text