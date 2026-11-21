import mimetypes
import re
import shutil
import time
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..db import engine, get_db, upsert_kv
from ..config import settings
from ..services import sendjobs
from ..tasks import submit, task
from ..services.crypto import decrypt_text, encrypt_text
from ..deps import log, need, need_any, sadmin_only
from ..models import User
from ..services import posts as P
from ..services import telegram as tg

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _mask(t: str) -> str:
    return f"{t.split(':')[0]}:{'•' * 10}{t[-4:]}" if t else ""


def _kv(db: Session, k: str) -> str:
    return db.execute(text("SELECT v FROM kv WHERE k=:k"), {"k": k}).scalar() or ""


def _set_kv(db: Session, k: str, v: str) -> None:
    upsert_kv(db.connection(), k, v)


def _chats(db: Session, only_active: bool) -> list[dict]:
    q = "SELECT id, chat_id, title, kind, username, source, is_active, members, members_at FROM tg_chats"
    if only_active:
        q += " WHERE is_active=1"
    out = [dict(r) for r in db.execute(text(q + " ORDER BY kind, title")).mappings()]
    for r in out:
        r["members_at"] = r["members_at"].isoformat() if r["members_at"] else None
    if out and _kv(db, "tg_token"):
        tg.refresh_members_bg(30)
    return out


@router.get("")
def overview(_: User = Depends(need_any("settings.manage", "telegram.send", "telegram.message", "telegram.journal", "system.view", "backup.manage")), db: Session = Depends(get_db)):
    token = decrypt_text(_kv(db, "tg_token"))
    hb = _kv(db, "tg_poll_hb")
    return {"configured": bool(token), "token": _mask(token), "bot_username": _kv(db, "tg_bot_username"),
            "bot_name": _kv(db, "tg_bot_name"), "poll_alive": bool(hb and time.time() - int(hb) < 60),
            "chats": _chats(db, False)}


class TokenIn(BaseModel):
    token: str


@router.put("/token")
def set_token(body: TokenIn, me: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    token = body.token.strip()
    try:
        bot = tg.call("getMe", token=token, timeout=20)
    except tg.TgError as e:
        raise HTTPException(400, f"Token tekshiruvdan o'tmadi: {e}") from e
    _set_kv(db, "tg_token", encrypt_text(token))
    _set_kv(db, "tg_bot_username", bot.get("username", ""))
    _set_kv(db, "tg_bot_name", bot.get("first_name", ""))
    log(db, me.username, "telegram_token", f"Bot ulandi: @{bot.get('username')}")
    db.commit()
    return {"ok": True, "bot_username": bot.get("username"), "bot_name": bot.get("first_name")}


@router.delete("/token")
def del_token(me: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    for k in ("tg_token", "tg_bot_username", "tg_bot_name", "tg_poll_hb"):
        db.execute(text("DELETE FROM kv WHERE k=:k"), {"k": k})
    log(db, me.username, "telegram_token", "Bot uzildi")
    db.commit()
    return {"ok": True}


class ChatIn(BaseModel):
    chat: str      # raqamli ID (-100...) yoki @kanal_nomi


@router.post("/chats")
def add_chat(body: ChatIn, me: User = Depends(need("settings.manage")), db: Session = Depends(get_db)):
    ref = body.chat.strip()
    if ref and not ref.startswith("@") and not ref.lstrip("-").isdigit():
        ref = "@" + ref.split("/")[-1]
    try:
        chat = tg.call("getChat", {"chat_id": ref}, timeout=20)
    except tg.TgError as e:
        raise HTTPException(400, f"Kanal topilmadi: {e}. Bot kanalga admin qilib qo'shilganini tekshiring") from e
    if chat.get("type") not in ("channel", "group", "supergroup"):
        raise HTTPException(400, "Bu kanal yoki guruh emas")
    warn = ""
    try:
        bot_id = tg.call("getMe", timeout=15)["id"]
        st = tg.call("getChatMember", {"chat_id": chat["id"], "user_id": bot_id}, timeout=15).get("status")
        if st not in ("administrator", "creator"):
            warn = "Diqqat: bot bu yerda admin emas — xabar yuborolmasligi mumkin"
    except tg.TgError:
        warn = "Botning huquqlarini tekshirib bo'lmadi"
    tg.upsert_chat(chat, source="manual")
    tg.refresh_members_bg(0)
    log(db, me.username, "telegram_kanal", f"Qo'shildi: {chat.get('title')} ({chat['id']})")
    db.commit()
    return {"ok": True, "title": chat.get("title"), "warning": warn}


@router.post("/chats/refresh")
def refresh_chats(_: User = Depends(need_any("settings.manage", "telegram.send", "telegram.message")), db: Session = Depends(get_db)):
    """A'zolar sonini hozir yangilash."""
    n = tg.refresh_members(0)
    return {"updated": n, "chats": _chats(db, False)}


@router.delete("/chats/{cid}")
def del_chat(cid: int, me: User = Depends(need("settings.manage")), db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM tg_chats WHERE id=:i"), {"i": cid})
    log(db, me.username, "telegram_kanal", f"O'chirildi #{cid}")
    db.commit()
    return {"ok": True}


@router.get("/chats")
def active_chats(_: User = Depends(need_any("telegram.send", "telegram.message", "settings.manage")), db: Session = Depends(get_db)):
    return _chats(db, True)


@router.get("/starters")
def starters(_: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    """Botga /start bosganlar: xodim profiliga chat ID kiritishda tanlash uchun."""
    return [dict(r) | {"last_seen": r["last_seen"].isoformat()} for r in db.execute(text(
        "SELECT chat_id, name, username, last_seen FROM tg_users ORDER BY last_seen DESC LIMIT 100")).mappings()]


MAX_FILE = 50 * 1024 * 1024
MAX_FILES = 10


@task("tg.message")
def _run_msg(job_id: int, chats: list, msg: str, file_meta: list, items: dict, ack: bool) -> None:
    """file_meta: [[nom, yo'l, mime], ...] — fayllar API va worker orasida umumiy data/outbox papkasi orqali uzatiladi."""
    lines: list[str] = []
    done = fails = 0
    files = [(n, Path(p).read_bytes(), m) for n, p, m in file_meta]

    def flush(status="running"):
        with engine.begin() as c:
            c.execute(text("UPDATE send_jobs SET status=:s, progress=:p, log=:l WHERE id=:i"),
                      {"s": status, "p": round(100 * done / max(len(chats), 1), 1), "l": "\n".join(lines)[-6000:], "i": job_id})

    try:
        for chat_id, title in chats:
            iid = items[str(chat_id)]
            try:
                mid = tg.send_post(chat_id, msg, files, P.markup(iid) if ack else None)
                P.item_done(iid, True, mid)
                lines.append(f"✓ {title}")
            except tg.TgError as e:
                P.item_done(iid, False, None, str(e))
                lines.append(f"✗ {title}: {e}")
                fails += 1
            done += 1
            flush()
            time.sleep(min(1.0, settings.send_delay_sec))
        flush("error" if fails >= len(chats) else "done")
    except Exception as e:  # noqa: BLE001
        lines.append(f"✗ Kutilmagan xato: {e}")
        flush("error")
    finally:
        shutil.rmtree(settings.data_dir / "outbox" / str(job_id), ignore_errors=True)


@router.post("/send")
async def send_message(chat_ids: str = Form(...), message: str = Form(""), ack: bool = Form(True), files: list[UploadFile] = File(default=[]),
                       me: User = Depends(need("telegram.message")), db: Session = Depends(get_db)):
    """Kanal / guruhlarga matn, rasm yoki video yuborish (fon rejimida, jarayon /reports/send/{id} orqali)."""
    ids = [int(x) for x in chat_ids.split(",") if x.strip().isdigit()]
    files = [f for f in files if f.filename]
    if not message.strip() and not files:
        raise HTTPException(400, "Xabar matnini kiriting yoki rasm/video tanlang")
    if not ids:
        raise HTTPException(400, "Kamida bitta kanal yoki guruhni tanlang")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"Bir vaqtda {MAX_FILES} tagacha fayl yuborish mumkin")
    blobs: list[tuple[str, bytes, str]] = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_FILE:
            raise HTTPException(400, f"«{f.filename}» hajmi 50 MB dan katta (Telegram cheklovi)")
        mime = f.content_type or mimetypes.guess_type(f.filename)[0] or "application/octet-stream"
        blobs.append((f.filename, data, mime))
    sendjobs.require_bot(db)
    chats = sendjobs.chats_for(db, ids)
    job_id = sendjobs.create_job(db, me.username)
    log(db, me.username, "telegram_xabar", f"→ {', '.join(c[1] for c in chats)}"
        + (f" ({len(blobs)} ta fayl)" if blobs else ""))
    db.commit()
    plain = re.sub(r"<[^>]+>", "", message).strip()
    title = (plain.split("\n")[0][:120] if plain else f"{len(blobs)} ta fayl")
    _pid, items = P.create_post("xabar", title, message, [b[0] for b in blobs], ack, me.username, chats)
    out = settings.data_dir / "outbox" / str(job_id)
    meta = []
    if blobs:
        out.mkdir(parents=True, exist_ok=True)
        for i, (n, data, mime) in enumerate(blobs):
            (out / str(i)).write_bytes(data)
            meta.append([n, str(out / str(i)), mime])
    submit("tg.message", job_id, chats, message, meta, items, ack)
    return {"id": job_id}
