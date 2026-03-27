"""Pydantic Settings — loads all configuration from .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL (Neon)
    database_url: str

    # Neo4j (Aura Cloud)
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str

    # LLM (OpenRouter)
    llm_base_url: str
    llm_api_key: str
    llm_choice: str
    ingestion_llm_choice: str

    # Embeddings
    embedding_base_url: str
    embedding_api_key: str
    embedding_model: str
    vector_dimension: int = 1536

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8058
    log_level: str = "INFO"

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 150


settings = Settings()
