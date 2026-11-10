from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Career Command Center"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/career_command_center"
    cors_origins: list[str] = ["http://localhost:5173"]
    # Single-user JWT login, off locally. Wired up in a later step.
    auth_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
