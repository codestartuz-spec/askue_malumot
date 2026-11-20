import re
import threading
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import SessionLocal, engine, get_db
from ..deps import has_perm, log, need
from ..models import User
from ..services import reports as R
from ..services import telegram as tg
from ..services.dyn import compute

router = APIRouter(prefix="/reports", tags=["reports"])

REGION = "Qashqadaryo hududiy filiali"
VIEW = {"konsentrator": "view.konsentrator", "aloqa": "view.aloqa", "obxod": "view.obxod"}
MIME = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def _slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", s.replace("‘", "").replace("’", "").replace("'", "")).strip("_") or "hisobot"


def allowed_tables(user: User) -> list[str]:
    t = [k for k, perm in VIEW.items() if has_perm(user, perm)]
    if not t:
        raise HTTPException(403, "Dinamika jadvallarini ko'rish uchun ruxsat yo'q")
    return t


def make_report(db: Session, kind: str, esp_id: int | None, fmt: str, df: str | None, dt: str | None,
                tables: list[str], can_cmp: bool) -> tuple[str, bytes, str]:
    if kind == "district":
        row = db.execute(text("SELECT label FROM esps WHERE id=:i"), {"i": esp_id}).first()
        if not row:
            raise HTTPException(404, "Tuman topilmadi")
        scope, first = row[0], "Brigada"
    else:
        esp_id, scope, first = None, REGION, "Hudud nomi"
    items = [(t, compute(db, esp_id, df, dt, can_cmp)) for t in tables]
    if not items[0][1]["rows"]:
        raise HTTPException(400, "Hali ma'lumot yuklanmagan")
    data = items[0][1]
    fn = R.build_pdf if fmt == "pdf" else R.build_xlsx
    blob = fn(items, scope, first)
    name = f"Dinamika_{_slug(scope)}_{data['to']}.{fmt}"
    caption = f"📊 {scope} — dinamika\n📅 {R.period(data)}"
    return name, blob, caption


@router.get("/download")
def download(kind: str = "region", fmt: str = "pdf", esp_id: int | None = None,
             date_from: str | None = None, date_to: str | None = None,
             user: User = Depends(need("report.download")), db: Session = Depends(get_db)):
    if fmt not in MIME or kind not in ("region", "district"):
        raise HTTPException(400, "Noto'g'ri so'rov")
    name, blob, _ = make_report(db, kind, esp_id, fmt, date_from, date_to, allowed_tables(user),
                                has_perm(user, "dynamics.compare"))
    return Response(blob, media_type=MIME[fmt], headers={"Content-Disposition": f'attachment; filename="{name}"'})


class SendItem(BaseModel):
    kind: str                  # region | district
    fmt: str                   # pdf | xlsx
    esp_id: int | None = None


class SendIn(BaseModel):
    items: list[SendItem]
    chat_ids: list[int]
    ack: bool = True
    date_from: str | None = None
    date_to: str | None = None


def _run_send(job_id: int, items: list[SendItem], chats: list[tuple[str, str]], df, dt, tables, can_cmp,
              post_id: int = 0, pitems: dict | None = None, ack: bool = False):
    from ..services import posts as P
    pitems = pitems or {}
    chat_err: dict[str, str] = {}
    last_mid: dict[str, int | None] = {}
    lines: list[str] = []
    total = len(items) * max(len(chats), 1)
    done = 0
    fails = 0

    def flush(status="running"):
        with engine.begin() as c:
            c.execute(text("UPDATE send_jobs SET status=:s, progress=:p, log=:l WHERE id=:i"),
                      {"s": status, "p": round(100 * done / max(total, 1), 1), "l": "\n".join(lines)[-6000:], "i": job_id})

    try:
        for it in items:
            try:
                with SessionLocal() as db:
                    name, blob, caption = make_report(db, it.kind, it.esp_id, it.fmt, df, dt, tables, can_cmp)
            except HTTPException as e:
                lines.append(f"✗ {it.kind} {it.esp_id or ''} {it.fmt}: {e.detail}")
                fails += len(chats)
                done += len(chats)
                flush()
                continue
            if post_id:
                P.add_file(post_id, name)
            is_last = it is items[-1]
            for chat_id, title in chats:
                iid = pitems.get(str(chat_id))
                try:
                    r = tg.send_file(chat_id, name, blob, caption, P.markup(iid) if (ack and is_last and iid) else None)
                    last_mid[str(chat_id)] = r.get("message_id")
                    lines.append(f"✓ {name} → {title}")
                except tg.TgError as e:
                    lines.append(f"✗ {name} → {title}: {e}")
                    chat_err[str(chat_id)] = str(e)
                    fails += 1
                if is_last and iid:
                    P.item_done(iid, str(chat_id) not in chat_err, last_mid.get(str(chat_id)), chat_err.get(str(chat_id), ""))
                done += 1
                flush()
                time.sleep(3.2)     # Telegram chegarasi: guruhga daqiqasiga ~20 xabar
        for cid, iid in pitems.items():      # fayl yaratib bo'lmagan holat
            with engine.connect() as c:
                st = c.execute(text("SELECT status FROM tg_post_items WHERE id=:i"), {"i": iid}).scalar()
            if st == "wait":
                P.item_done(iid, False, None, "Fayl tayyorlanmadi")
        flush("error" if fails and fails >= total else "done")
    except Exception as e:  # noqa: BLE001
        lines.append(f"✗ Kutilmagan xato: {e}")
        flush("error")


@router.post("/send")
def send(body: SendIn, user: User = Depends(need("telegram.send")), db: Session = Depends(get_db)):
    if not body.items:
        raise HTTPException(400, "Nimani yuborishni tanlang")
    if not body.chat_ids:
        raise HTTPException(400, "Kamida bitta kanal yoki guruhni tanlang")
    for it in body.items:
        if it.fmt not in MIME or it.kind not in ("region", "district") or (it.kind == "district" and not it.esp_id):
            raise HTTPException(400, "Noto'g'ri tanlov")
    tables = allowed_tables(user)
    chats = [(r[0], r[1]) for r in db.execute(text("SELECT chat_id, title FROM tg_chats WHERE is_active=1 "
                                                   "AND id IN :ids").bindparams(
        __import__("sqlalchemy").bindparam("ids", expanding=True)), {"ids": body.chat_ids})]
    if not chats:
        raise HTTPException(400, "Tanlangan kanallar topilmadi")
    if not db.execute(text("SELECT 1 FROM kv WHERE k='tg_token'")).first():
        raise HTTPException(400, "Telegram bot sozlanmagan (Sozlamalar bo'limi)")
    db.execute(text("INSERT INTO send_jobs (status,progress,log,created_by,created_at) VALUES ('running',0,'',:u,:t)"),
               {"u": user.username, "t": datetime.now()})
    job_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    log(db, user.username, "telegram_hisobot", f"{len(body.items)} ta fayl → {', '.join(c[1] for c in chats)}")
    db.commit()
    from ..services import posts as P
    pid, pitems = P.create_post("hisobot", f"Kunlik dinamika — {len(body.items)} ta fayl", "", [], body.ack,
                                user.username, chats)
    threading.Thread(target=_run_send, daemon=True,
                     args=(job_id, body.items, chats, body.date_from, body.date_to, tables,
                           has_perm(user, "dynamics.compare"), pid, pitems, body.ack)).start()
    return {"id": job_id}


@router.get("/send/{job_id}")
def send_status(job_id: int, _: User = Depends(need("telegram.send")), db: Session = Depends(get_db)):
    r = db.execute(text("SELECT id, status, progress, log FROM send_jobs WHERE id=:i"), {"i": job_id}).mappings().first()
    if not r:
        raise HTTPException(404, "Topilmadi")
    return dict(r)
