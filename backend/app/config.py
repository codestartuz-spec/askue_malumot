from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE / ".env", extra="ignore")

    database_url: str = "mysql+pymysql://root:root@127.0.0.1:3306/askue?charset=utf8mb4"
    secret_key: str = "o'zgartiring-bu-kalitni"
    token_hours: int = 12
    sadmin_username: str = "sadmin"
    sadmin_password: str = "Sadmin@2026"
    data_dir: Path = BASE / "data"
    telegram_api: str = "https://api.telegram.org"
    telegram_proxy: str = ""      # masalan: http://192.168.0.1:3128 (ofis tarmog'i uchun)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_dist: Path = BASE.parent / "frontend" / "dist"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
