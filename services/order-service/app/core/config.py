from pydantic import BaseSettings

class Settings(BaseSettings):
    SERVICE_NAME: str = "order-service"
    SERVICE_VERSION: str = "1.0.0"
    DEBUG: bool = True

    class Config:
        env_file= ".env"

settings= Settings()

