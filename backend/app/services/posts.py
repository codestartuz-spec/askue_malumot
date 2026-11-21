"""Telegram xabarlar jurnali: xabar, uning kanal nusxalari va «Tanishdim» bosganlar."""
import json
from datetime import datetime

from sqlalchemy import text

from ..db import engine, insert_id


def create_post(kind: str, title: str, body: str, files: list[str], ack: bool, by: str,
                chats: list[tuple[str, str]]) -> tuple[int, dict[str, int]]:
    """Post va har bir kanal uchun element yaratadi. Qaytaradi: (post_id, {chat_id: item_id})."""
    with engine.begin() as c:
        pid = insert_id(c, "INSERT INTO tg_posts (kind,title,body,files,ack,created_by,created_at) "
                           "VALUES (:k,:t,:b,:f,:a,:u,:n)",
                        {"k": kind, "t": title[:250], "b": body, "f": json.dumps(files, ensure_ascii=False), "a": ack,
                         "u": by, "n": datetime.now()})
        items = {}
        for chat_id, ttl in chats:
            items[str(chat_id)] = insert_id(
                c, "INSERT INTO tg_post_items (post_id,chat_id,chat_title,status,error) VALUES (:p,:c,:t,'wait','')",
                {"p": pid, "c": str(chat_id), "t": ttl[:200]})
    return pid, items


def add_file(post_id: int, name: str) -> None:
    with engine.begin() as c:
        cur = c.execute(text("SELECT files FROM tg_posts WHERE id=:i"), {"i": post_id}).scalar()
        arr = json.loads(cur) if isinstance(cur, str) else (cur or [])
        if name not in arr:
            arr.append(name)
        c.execute(text("UPDATE tg_posts SET files=:f WHERE id=:i"),
                  {"f": json.dumps(arr, ensure_ascii=False), "i": post_id})


def item_done(item_id: int, ok: bool, message_id: int | None = None, err: str = "") -> None:
    with engine.begin() as c:
        c.execute(text("UPDATE tg_post_items SET status=:s, message_id=:m, error=:e, sent_at=:t WHERE id=:i"),
                  {"s": "ok" if ok else "err", "m": message_id, "e": err[:1000], "t": datetime.now(), "i": item_id})


def markup(item_id: int, count: int = 0) -> str:
    label = "✅ Tanishdim" + (f" · {count}" if count else "")
    return json.dumps({"inline_keyboard": [[{"text": label, "callback_data": f"ack:{item_id}"}]]})
