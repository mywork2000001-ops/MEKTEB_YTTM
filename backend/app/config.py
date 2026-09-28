"""Tətbiqin parametrləri – mühit dəyişənlərindən (.env) oxunur."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='MK_', extra='ignore')

    database_url: str = 'sqlite:///./data/app.db'        # prod: postgresql+psycopg://...
    secret_key: str = 'dev-secret-change-me'
    # Əlavə test bazası: işləyən viktorina saytı (suallar oradan avtomatik yenilənir)
    viktorina_url: str = 'https://hub-educat-on-6m58.vercel.app/viktorina.html'
    bank_sync_minutes: int = 60                          # 0 = avtomatik yeniləmə söndürülüb
    bank_exclude_sources: str = 'eduhub'                 # vergüllə; EduHub açar tələb edir
    chrome_path: str | None = None                       # lokal: C:/Program Files/Google/Chrome/Application/chrome.exe


@lru_cache
def settings() -> Settings:
    return Settings()
