from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://tourist:tourist@localhost:5432/tourist"
    jwt_secret: str = "change-me"
    jwt_minutes: int = 60 * 24 * 7
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"
    google_places_api_key: str = ""
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384
    embed_cache: str = ".models"


settings = Settings()
