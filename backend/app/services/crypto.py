"""Shifrlash: zaxira fayllari va maxfiy qiymatlar (Telegram tokeni) uchun.

Kalit BACKUP_KEY'dan (bo'lmasa SECRET_KEY'dan HKDF bilan) olinadi. Fernet (AES-128-CBC + HMAC-SHA256).
Zaxirani ochish: python -m app.tools.decrypt_backup fayl.sql.gz.enc"""
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..config import settings

PREFIX = "enc1:"
MAGIC = b"ASKB1\n"          # shifrlangan zaxira fayli boshi


def _fernet(purpose: str) -> Fernet:
    src = (settings.backup_key or settings.secret_key).encode()
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"askue-malumot", info=purpose.encode()).derive(src)
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_bytes(data: bytes) -> bytes:
    return MAGIC + _fernet("backup").encrypt(data)


def decrypt_bytes(blob: bytes) -> bytes:
    if not blob.startswith(MAGIC):
        return blob     # eski, shifrlanmagan zaxira
    try:
        return _fernet("backup").decrypt(blob[len(MAGIC):])
    except InvalidToken as e:
        raise ValueError("Kalit noto'g'ri yoki fayl shikastlangan (BACKUP_KEY / SECRET_KEY ni tekshiring)") from e


def encrypt_text(v: str) -> str:
    return v if not v or v.startswith(PREFIX) else PREFIX + _fernet("secret").encrypt(v.encode()).decode()


def decrypt_text(v: str) -> str:
    if not v or not v.startswith(PREFIX):
        return v        # eski, ochiq saqlangan qiymat
    try:
        return _fernet("secret").decrypt(v[len(PREFIX):].encode()).decode()
    except InvalidToken:
        return ""
