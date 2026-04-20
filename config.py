from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config: 
        env_file = ".env" # This will allow you to override with a .env file 

settings = Settings()