from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: float = 60.0
    GEMINI_API_KEY: str
    NEWS_API_KEY: str
    DATABASE_URL: str

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()