from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # LLM — Gemini
    app_name: str = "Operational Claims Intelligence Agent"   # ← add this
    gemini_api_key: str = "dummy-key-for-dev"
    gemini_model: str = "gemini-1.5-flash"
    llm_timeout: int = 10

    # Database
    database_url: str = "sqlite:///./claims.db"

    # App
    app_env: str = "development"
    app_port: int = 8000
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()