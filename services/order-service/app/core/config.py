from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "order-service"
    service_version: str = "1.0.0"
    inventory_service_url: str = "http://localhost:8001"
    payment_service_url: str = "http://localhost:8002"
    request_timeout_seconds: float = 3.0
    failure_simulation_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
