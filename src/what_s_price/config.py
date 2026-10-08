"""Configuration for the price prediction service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_path: str = "artifacts/model.joblib"
    model_name: str | None = None
    model_alias: str = "champion"
    mlflow_tracking_uri: str | None = None
    database_url: str | None = None
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
