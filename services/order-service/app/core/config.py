from pydantic_settings import BaseSettings

#configuration settings for the order service 
class Settings(BaseSettings):
    SERVICE_NAME: str = "order-service"
    SERVICE_VERSION: str = "1.0.0"
    DEBUG: bool = True

    class Config:
        env_file= ".env"

settings= Settings()

