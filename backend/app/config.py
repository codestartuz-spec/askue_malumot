import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE = Path(__file__).resolve().parent.parent

_WEAK_KEYS = {"", "o'zgartiring-bu-kalitni", "changeme", "secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE / ".env", extra="ignore")

    env: str = "local"                     # local | production | test  (ASKUE_ENV emas, ENV)
    database_url: str = "mysql+pymysql://root:root@127.0.0.1:3306/askue?charset=utf8mb4"
    sql_mode_strict: bool = True           # MySQL 8 sql_mode (ONLY_FULL_GROUP_BY...) ni MariaDB'da ham majburlaydi
    secret_key: str = ""                   # bo'sh bo'lsa data/secret.key da bir marta tasodifiy yaratiladi
    backup_key: str = ""                   # bo'sh bo'lsa SECRET_KEY'dan hosil qilinadi
    token_hours: int = 12
    sadmin_username: str = "sadmin"
    sadmin_password: str = ""              # bo'sh bo'lsa birinchi ishga tushishda tasodifiy yaratiladi
    data_dir: Path = BASE / "data"
    telegram_api: str = "https://api.telegram.org"
    telegram_proxy: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_dist: Path = BASE.parent / "frontend" / "dist"

    # Redis. Bo'sh bo'lsa — xotira rejimi (bitta jarayon uchun; mahalliy kompyuter)
    redis_url: str = ""
    # CF-Connecting-IP / X-Forwarded-For'ga faqat shu tarmoqlardan kelgan so'rovlardagina ishoniladi
    trusted_proxies: str = "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12"
    # Yuklanadigan PDF cheklovlari
    max_pdf_mb: int = 15
    max_pdf_pages: int = 12
    pdf_parse_timeout: int = 60
    # Login cheklovi
    login_window_sec: int = 900
    login_limit_pair: int = 6              # login+IP juftligi
    login_limit_ip: int = 30               # bitta IP
    login_limit_user: int = 60             # bitta login (turli IPlardan)
    # Katta fayllar (Area/Details): yuklash va ochilgan hajm chegaralari
    max_upload_mb: int = 800
    max_unzipped_mb: int = 6000
    # Bo'laklab yuklash (Details ~5 MB lik .csv.gz bo'laklar): bitta bo'lak chegarasi
    max_part_mb: int = 20
    stale_upload_hours: int = 24           # tugallanmagan bo'laklab yuklash seansi shuncha soatdan keyin tozalanadi
    send_delay_sec: float = 3.2            # Telegram chegarasi: guruhga daqiqasiga ~20 xabar
    # Audit jurnali saqlash muddati (kun). 0 — o'chirmaslik
    audit_keep_days: int = 365


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "uploads").mkdir(parents=True, exist_ok=True)


def _bootstrap_secret() -> None:
    """SECRET_KEY berilmagan yoki zaif bo'lsa — data/secret.key ga bir marta tasodifiy kalit yozadi."""
    if settings.secret_key not in _WEAK_KEYS:
        return
    if settings.env == "production":
        raise RuntimeError("SECRET_KEY o'rnatilmagan. .env ga uzun tasodifiy qiymat yozing (deploy.sh buni o'zi qiladi).")
    f = settings.data_dir / "secret.key"
    if not f.exists():
        f.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        try:
            f.chmod(0o600)
        except OSError:
            pass
    settings.secret_key = f.read_text(encoding="utf-8").strip()


_bootstrap_secret()
