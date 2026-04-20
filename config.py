from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = "ac7556a46145af09fd19773d3871f8c5041af32c4c86acc99abda77d487cc493"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env" # This will allow you to override with a .env file

settings = Settings()