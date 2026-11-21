"""Telegramga yuborish ishlari uchun umumiy yordamchilar (barcha routerlar shundan foydalanadi)."""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..db import engine, insert_id


def require_bot(db: Session) -> None:
    if not db.execute(text("SELECT 1 FROM kv WHERE k='tg_token'")).first():
        raise HTTPException(400, "Telegram bot sozlanmagan (Sozlamalar bo'limi)")


def chats_for(db: Session, chat_ids: list[int]) -> list[list]:
    """Tanlangan faol kanallar: [[chat_id, title], ...] (JSON-ga mos ko'rinishda)."""
    if not chat_ids:
        raise HTTPException(400, "Kamida bitta kanal yoki guruhni tanlang")
    rows = db.execute(text("SELECT chat_id, title FROM tg_chats WHERE is_active=1 AND id IN :ids")
                      .bindparams(bindparam("ids", expanding=True)), {"ids": list(chat_ids)})
    chats = [[r[0], r[1]] for r in rows]
    if not chats:
        raise HTTPException(400, "Tanlangan kanallar topilmadi")
    return chats


def create_job(db: Session, username: str) -> int:
    return int(db.execute(text("INSERT INTO send_jobs (status,progress,log,created_by,created_at) "
                               "VALUES ('running',0,'',:u,:t)"), {"u": username, "t": datetime.now()}).lastrowid)


def flush(job_id: int, status: str, done: int, total: int, lines: list[str]) -> None:
    with engine.begin() as c:
        c.execute(text("UPDATE send_jobs SET status=:s, progress=:p, log=:l WHERE id=:i"),
                  {"s": status, "p": round(100 * done / max(total, 1), 1), "l": "\n".join(lines)[-6000:], "i": job_id})
