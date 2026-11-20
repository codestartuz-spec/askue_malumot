"""Birinchi o'rnatishda .env faylini yaratadi (tasodifiy maxfiy kalit bilan)."""
import secrets
from pathlib import Path

root = Path(__file__).parent
env, example = root / ".env", root / ".env.example"
if env.exists():
    print(".env allaqachon mavjud — o'zgartirilmadi")
else:
    text = example.read_text(encoding="utf-8").replace("uzun-tasodifiy-matn-kiriting", secrets.token_urlsafe(48))
    env.write_text(text, encoding="utf-8")
    print(".env yaratildi. MySQL parolini shu fayldagi DATABASE_URL qatorida tekshiring.")
