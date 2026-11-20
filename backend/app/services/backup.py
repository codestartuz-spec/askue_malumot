"""Zaxira nusxa: muhim jadvallar SQL (gzip) ko'rinishida. Hisoblagichlar (meters) va TP ro'yxati kiritilmaydi —
ular Area/Details fayllaridan qayta tiklanadi; TP'larning brigadaga biriktirilishi esa saqlanadi."""
import gzip
import io
import threading
import time
import traceback
from datetime import datetime

from pymysql.converters import escape_string
from sqlalchemy import select, text

from ..config import settings
from ..db import SessionLocal, engine
from ..models import Backup, User
from . import telegram as tg

TABLES = ["users", "esps", "brigades", "brigade_members", "snapshots", "kv", "tg_chats", "tg_users", "audit",
          "republic_reports", "backups"]
TG_LIMIT = 49 * 1024 * 1024
_lock = threading.Lock()


def _lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    if hasattr(v, "isoformat"):
        return "'" + v.isoformat(sep=" ") + "'" if hasattr(v, "hour") else "'" + v.isoformat() + "'"
    if isinstance(v, (dict, list)):
        import json
        v = json.dumps(v, ensure_ascii=False)
    return "'" + escape_string(str(v)) + "'"


def make_dump() -> bytes:
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6) as gz:
        def w(s: str):
            gz.write(s.encode("utf-8"))
        w(f"-- ASKUE ma'lumot zaxira nusxasi • {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        w("-- Tiklash: gunzip -c fayl.sql.gz | mysql -u root -p askue   (avval ilovani to'xtating)\n")
        w("-- Hisoblagichlar va TP ro'yxati kiritilmagan: Area/Details fayllarini qayta yuklang.\n")
        w("SET NAMES utf8mb4; SET FOREIGN_KEY_CHECKS=0;\n")
        with engine.connect().execution_options(stream_results=True) as c:
            for t in TABLES:
                try:
                    res = c.execute(text(f"SELECT * FROM `{t}`"))
                except Exception:  # noqa: BLE001
                    continue
                cols = list(res.keys())
                w(f"\n-- {t}\nDELETE FROM `{t}`;\n")
                head = f"INSERT INTO `{t}` (" + ",".join(f"`{x}`" for x in cols) + ") VALUES\n"
                batch = []
                for row in res:
                    batch.append("(" + ",".join(_lit(v) for v in row) + ")")
                    if len(batch) >= 300:
                        w(head + ",\n".join(batch) + ";\n")
                        batch = []
                if batch:
                    w(head + ",\n".join(batch) + ";\n")
            w("\n-- TP'larning brigadaga biriktirilishi\n")
            for r in c.execute(text("SELECT esp_id, tr_code, brigade_id, manual FROM trs WHERE brigade_id IS NOT NULL")):
                w(f"UPDATE trs SET brigade_id={int(r[2])}, manual={int(bool(r[3]))} WHERE esp_id={int(r[0])} AND tr_code={_lit(r[1])};\n")
        w("\nSET FOREIGN_KEY_CHECKS=1;\n")
    return raw.getvalue()


def _kv(k: str, default: str = "") -> str:
    with engine.connect() as c:
        v = c.execute(text("SELECT v FROM kv WHERE k=:k"), {"k": k}).scalar()
    return v if v is not None else default


def _set(k: str, v: str) -> None:
    with engine.begin() as c:
        c.execute(text("INSERT INTO kv (k,v) VALUES (:k,:v) ON DUPLICATE KEY UPDATE v=VALUES(v)"), {"k": k, "v": v})


def settings_get() -> dict:
    return {"enabled": _kv("backup_enabled", "1") == "1", "time": _kv("backup_time", "01:00"),
            "keep": int(_kv("backup_keep", "14") or 14), "last_auto": _kv("backup_last_auto", "")}


def sadmin_chats() -> list[tuple[str, str]]:
    with SessionLocal() as db:
        return [(u.chat_id, u.username) for u in db.scalars(select(User).where(User.is_super.is_(True), User.is_active.is_(True)))
                if u.chat_id]


def _bdir():
    d = settings.data_dir / "backups"
    d.mkdir(exist_ok=True)
    return d


def run_backup(kind: str = "auto") -> dict:
    """Zaxira nusxa oladi, faylga saqlaydi va sadminga Telegram orqali yuboradi."""
    with _lock:
        name = f"askue_zaxira_{datetime.now():%Y-%m-%d_%H%M}.sql.gz"
        rec = Backup(kind=kind, filename=name)
        try:
            blob = make_dump()
            (_bdir() / name).write_bytes(blob)
            rec.size, rec.status = len(blob), "ok"
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            rec.status, rec.note = "error", f"Nusxa olinmadi: {e}"[:390]
            blob = b""
        if blob:
            rec.sent, rec.note = send_to_sadmin(name, blob, kind)
        with SessionLocal() as db:
            db.add(rec)
            db.commit()
            db.refresh(rec)
            rid = rec.id
        cleanup()
        return {"id": rid, "filename": name, "size": rec.size, "status": rec.status, "sent": rec.sent, "note": rec.note}


def send_to_sadmin(name: str, blob: bytes, kind: str = "auto") -> tuple[bool, str]:
    chats = sadmin_chats()
    if not tg.get_token():
        return False, "Telegram bot sozlanmagan — fayl faqat serverda saqlandi"
    if not chats:
        return False, "Sadminning Telegram chat ID si kiritilmagan (Xodimlar → sadmin) — fayl faqat serverda saqlandi"
    if len(blob) > TG_LIMIT:
        return False, f"Fayl {len(blob) // 1048576} MB — Telegram chegarasidan (50 MB) katta, faqat serverda saqlandi"
    ok, errs = 0, []
    cap = f"🗄 ASKUE zaxira nusxasi\n📅 {datetime.now():%d.%m.%Y %H:%M} • {len(blob) / 1048576:.1f} MB • {'avtomatik' if kind == 'auto' else 'qo`lda'}"
    for cid, who in chats:
        try:
            tg.send_file(cid, name, blob, cap)
            ok += 1
        except tg.TgError as e:
            errs.append(f"{who}: {e}")
    return ok > 0, ("; ".join(errs))[:390]


def cleanup() -> None:
    keep = max(1, settings_get()["keep"])
    with SessionLocal() as db:
        rows = list(db.scalars(select(Backup).where(Backup.status == "ok").order_by(Backup.id.desc())))
        for r in rows[keep:]:
            try:
                (_bdir() / r.filename).unlink(missing_ok=True)
            except OSError:
                pass
            db.delete(r)
        db.commit()


def _loop() -> None:
    while True:
        try:
            cfg = settings_get()
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if cfg["enabled"] and cfg["last_auto"] != today and now.strftime("%H:%M") >= cfg["time"]:
                _set("backup_last_auto", today)     # avval belgilaymiz — bir kunda ikki marta ishlamasligi uchun
                print(f"Zaxira nusxa olinmoqda ({today})", flush=True)
                run_backup("auto")
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        time.sleep(30)


def start_scheduler() -> None:
    threading.Thread(target=_loop, daemon=True, name="backup").start()
