"""Tətbiqin parametrləri – mühit dəyişənlərindən (.env) oxunur."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='MK_', extra='ignore')

    database_url: str = 'sqlite:///./data/app.db'        # prod: postgresql+psycopg://... (postgres:// da qəbul olunur)
    secret_key: str = 'dev-secret-change-me'
    # Əlavə test bazası: işləyən viktorina saytı (suallar oradan avtomatik yenilənir)
    viktorina_url: str = 'https://hub-educat-on-6m58.vercel.app/viktorina.html'
    bank_sync_minutes: int = 60                          # 0 = avtomatik yeniləmə söndürülüb
    bank_exclude_sources: str = 'eduhub'                 # vergüllə; EduHub açar tələb edir
    bank_hook_token: str | None = None                   # viktorina deploy olunanda GitHub Action POST /api/bank/hook çağırır
    chrome_path: str | None = None                       # lokal: C:/Program Files/Google/Chrome/Application/chrome.exe
    admin_password: str | None = None                    # ilk açılış: baza boşdursa admin bu parolla yaradılır
    admin_login: str = 'M-001'                           # müəllimlər ID ilə daxil olur (M-001, M-002, …)
    cookie_secure: bool = False                          # HTTPS-də (Render) True
    upload_dir: str | None = None                        # çat faylları; boşdursa – bazanın yanında data/uploads
    # Render pulsuz planı 15 dəq trafiksiz qalanda yatır: server öz ünvanına müraciət edir (Bakı vaxtı ilə saatlar)
    keepalive_url: str | None = None                     # boşdursa RENDER_EXTERNAL_URL (Render özü verir)
    keepalive_hours: str = '7-23'                        # 07:00–23:00 oyaq; gecə yatır
    storage: str = 'local'                               # local | db | gdrive (hostinqdə: gdrive, qoşulana qədər db)
    gdrive_folder_id: str | None = None
    gdrive_client_id: str | None = None
    gdrive_client_secret: str | None = None
    gdrive_refresh_token: str | None = None


@lru_cache
def settings() -> Settings:
    return Settings()
