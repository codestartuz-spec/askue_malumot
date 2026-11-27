"""Telegramga yuborilgan xabarlar jurnali."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import need
from ..models import User

router = APIRouter(prefix="/posts", tags=["posts"])


def _files(v) -> list:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return []
    return v or []


@router.get("")
def listing(kind: str = "", page: int = 1, size: int = 25, _: User = Depends(need("telegram.journal")),
            db: Session = Depends(get_db)):
    size = max(5, min(size, 100))
    where, params = "", {"lim": size, "off": (max(page, 1) - 1) * size}
    if kind in ("xabar", "hisobot", "respublika", "republic", "nation", "ag"):
        where, params["k"] = "WHERE p.kind=:k", kind
    total = db.execute(text(f"SELECT COUNT(*) FROM tg_posts p {where}"), params).scalar() or 0
    rows = db.execute(text(
        "SELECT p.id, p.kind, p.title, p.body, p.files, p.ack, p.created_by, p.created_at, "
        "(SELECT COUNT(*) FROM tg_post_items i WHERE i.post_id=p.id) AS chats, "
        "(SELECT COUNT(*) FROM tg_post_items i WHERE i.post_id=p.id AND i.status='ok') AS ok, "
        "(SELECT COUNT(*) FROM tg_post_items i WHERE i.post_id=p.id AND i.status='err') AS err, "
        "(SELECT COUNT(*) FROM tg_acks a JOIN tg_post_items i ON i.id=a.item_id WHERE i.post_id=p.id) AS acks "
        f"FROM tg_posts p {where} ORDER BY p.id DESC LIMIT :lim OFFSET :off"), params).mappings().all()
    items = [dict(r) | {"files": _files(r["files"]), "created_at": r["created_at"].isoformat(),
                        "body": (r["body"] or "")[:300]} for r in rows]
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/{pid}")
def detail(pid: int, _: User = Depends(need("telegram.journal")), db: Session = Depends(get_db)):
    p = db.execute(text("SELECT id, kind, title, body, files, ack, created_by, created_at FROM tg_posts WHERE id=:i"),
                   {"i": pid}).mappings().first()
    if not p:
        raise HTTPException(404, "Topilmadi")
    items = []
    for i in db.execute(text("SELECT id, chat_title, status, error, sent_at FROM tg_post_items WHERE post_id=:i "
                             "ORDER BY id"), {"i": pid}).mappings():
        acks = [{"name": a["name"], "username": a["username"], "at": a["acked_at"].isoformat()}
                for a in db.execute(text("SELECT name, username, acked_at FROM tg_acks WHERE item_id=:i "
                                         "ORDER BY acked_at"), {"i": i["id"]}).mappings()]
        items.append({"id": i["id"], "chat": i["chat_title"], "status": i["status"], "error": i["error"],
                      "sent_at": i["sent_at"].isoformat() if i["sent_at"] else None, "acks": acks})
    return {**dict(p), "files": _files(p["files"]), "created_at": p["created_at"].isoformat(), "items": items}
