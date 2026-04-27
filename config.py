from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str = "ac7556a46145af09fd19773d3871f8c5041af32c4c86acc99abda77d487cc493"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: float = 60.0
    GEMINI_API_KEY: str = ""
    NEWS_API_KEY: str = ""

    # Pydantic V2 style for configuration
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()