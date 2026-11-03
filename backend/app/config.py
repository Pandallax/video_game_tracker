from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    baserow_url: str
    baserow_api_token: str
    app_username: str
    app_password: str
    session_secret: str
    # Only needed by scripts/fetch_igdb_covers.py (Twitch developer app credentials).
    igdb_client_id: str = ""
    igdb_client_secret: str = ""


settings = Settings()
