from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL
    database_url: str = "postgresql://ecommerce:ecommerce@localhost:5432/ecommerce"
    # MongoDB
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "ecommerce"
    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    es_index: str = "orders"
    es_products_index: str = "products"
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Sync: "dual_write", "polling", or "celery" (recommended async strategy)
    sync_strategy: str = "dual_write"
    poll_interval_seconds: int = 15
    # Celery / RabbitMQ (used when sync_strategy == "celery")
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "rpc://"
    # Frontend
    vite_api_url: str = "http://localhost:8000"


settings = Settings()
