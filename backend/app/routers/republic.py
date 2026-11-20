import re
import threading
import time
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, engine, get_db
from ..deps import log, need, need_any
from ..models import RepublicReport, User
from ..services import republic as R
from ..services import telegram as tg

router = APIRouter(prefix="/republic", tags=["republic"])
MIME = {"pdf": "application/pdf", "orig": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
MAX_PDF = 40 * 1024 * 1024


def _dates(db: Session) -> list[RepublicReport]:
    return list(db.scalars(select(RepublicReport).order_by(RepublicReport.end_date.desc())))


@router.post("/upload")
def upload(file: UploadFile = File(...), user: User = Depends(need("data.upload")), db: Session = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Faqat PDF fayl qabul qilinadi")
    data = file.file.read(MAX_PDF + 1)
    if len(data) > MAX_PDF:
        raise HTTPException(400, "Fayl juda katta (40 MB dan oshmasin)")
    try:
        rep = R.parse_report(data)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "PDF o'qib bo'lmadi. Respublika dinamikasi PDF faylini yuklang")
    if not rep["pages"]:
        raise HTTPException(400, "PDF ichidan «Жами» (viloyat) qatori topilmadi — to'g'ri fayl ekanini tekshiring")
    end = rep["end"]
    if not end:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\D*$", re.sub(r"\.pdf$", "", file.filename or "", flags=re.I))
        end = date(int(m[3]), int(m[2]), int(m[1])) if m else None
    if not end:
        raise HTTPException(400, "PDF ichidan sana aniqlanmadi")
    payload = {"pages": rep["pages"]}
    row = db.scalar(select(RepublicReport).where(RepublicReport.end_date == end))
    replaced = bool(row)
    if row:
        row.data, row.start_date, row.filename, row.uploaded_by, row.uploaded_at = payload, rep["start"], file.filename or "", user.username, datetime.now()
    else:
        db.add(RepublicReport(end_date=end, start_date=rep["start"], filename=file.filename or "", data=payload,
                              uploaded_by=user.username))
    (settings.data_dir / "republic").mkdir(exist_ok=True)
    (settings.data_dir / "republic" / f"{end.isoformat()}.pdf").write_bytes(data)
    log(db, user.username, "respublika_yuklash", f"{file.filename} → {end.isoformat()}")
    db.commit()
    return {"end": end.isoformat(), "start": rep["start"].isoformat() if rep["start"] else None,
            "pages": len(rep["pages"]), "replaced": replaced}


@router.get("")
def listing(_: User = Depends(need_any("republic.view", "data.upload")), db: Session = Depends(get_db)):
    return [{"id": r.id, "end": r.end_date.isoformat(), "start": r.start_date.isoformat() if r.start_date else None,
             "filename": r.filename, "by": r.uploaded_by, "at": r.uploaded_at.isoformat(),
             "pages": len(r.data.get("pages", []))} for r in _dates(db)]


@router.delete("/{rid}")
def delete(rid: int, user: User = Depends(need("data.upload")), db: Session = Depends(get_db)):
    r = db.get(RepublicReport, rid)
    if not r:
        raise HTTPException(404, "Topilmadi")
    log(db, user.username, "respublika_ochirish", r.end_date.isoformat())
    db.delete(r)
    db.commit()
    return {"ok": True}


def _pick(db: Session, a: str | None, b: str | None):
    reps = _dates(db)
    if not reps:
        raise HTTPException(400, "Hali respublika PDF'i yuklanmagan")
    by = {r.end_date.isoformat(): r for r in reps}
    bb = by.get(b) if b else reps[0]
    if not bb:
        raise HTTPException(400, "Tanlangan sana topilmadi")
    if a:
        aa = by.get(a)
        if not aa:
            raise HTTPException(400, "Solishtiriladigan sana topilmadi")
    else:   # oldingi eng yaqin sana
        older = [r for r in reps if r.end_date < bb.end_date]
        aa = older[0] if older else None
    return aa, bb


def _build(db: Session, a: str | None, b: str | None):
    aa, bb = _pick(db, a, b)
    start = bb.start_date or date(bb.end_date.year, bb.end_date.month, 1)
    base_iso = (aa.end_date if aa else start).isoformat()
    pages = R.compare(aa.data if aa else None, bb.data, base_iso, bb.end_date.isoformat())
    return pages, (aa.end_date if aa else None), bb.end_date, start


@router.get("/compare")
def compare(a: str | None = None, b: str | None = None, _: User = Depends(need("republic.view")),
            db: Session = Depends(get_db)):
    pages, ad, bd, start = _build(db, a, b)
    return {"a": ad.isoformat() if ad else None, "b": bd.isoformat(), "start": start.isoformat(), "pages": pages,
            "dates": [r.end_date.isoformat() for r in _dates(db)]}


def upgrade_stored() -> int:
    """Eski yuklangan PDF'larni (faqat Jami qatori saqlangan) tuman qatorlari bilan qayta o'qiydi."""
    n = 0
    folder = settings.data_dir / "republic"
    with SessionLocal() as db:
        for r in _dates(db):
            if any(p.get("rows") for p in r.data.get("pages", [])):
                continue
            f = folder / f"{r.end_date.isoformat()}.pdf"
            if not f.exists():
                continue
            try:
                rep = R.parse_report(f.read_bytes())
            except Exception:  # noqa: BLE001
                continue
            if rep["pages"]:
                r.data = {"pages": rep["pages"]}
                n += 1
        db.commit()
    return n


def make_file(db: Session, fmt: str, a: str | None, b: str | None) -> tuple[str, bytes, str]:
    from ..services import reports as RP
    pages, ad, bd, start = _build(db, a, b)
    if fmt == "orig":
        f = settings.data_dir / "republic" / f"{bd.isoformat()}.pdf"
        if not f.exists():
            raise HTTPException(404, "Asl PDF fayl serverda topilmadi — shu sanani qayta yuklang")
        rep = db.scalar(select(RepublicReport).where(RepublicReport.end_date == bd))
        cap = f"📄 Respublika dinamikasi (asl nusxa)\n📅 {(bd.replace(day=1)):%d.%m.%Y} – {bd:%d.%m.%Y}"
        return (rep.filename if rep and rep.filename else f"Qashqadaryo_HETK_dynamic_{bd.isoformat()}.pdf"), f.read_bytes(), cap
    items = [(p["key"], {"rows": p["rows"], "total": {"cur": p["cur"], "base": p["base"]}, "base": p["from"], "to": p["to"]})
             for p in pages]
    blob = (RP.build_pdf if fmt == "pdf" else RP.build_xlsx)(items, RP.REGION_NAME, "Hudud nomi")
    name = f"Respublika_dinamikasi_{bd.isoformat()}.{fmt}"
    d0 = ad or start
    cap = f"📊 Respublika dinamikasi — Qashqadaryo hududiy filiali\n📅 {d0:%d.%m.%Y} – {bd:%d.%m.%Y}"
    return name, blob, cap


@router.get("/download")
def download(fmt: str = "pdf", a: str | None = None, b: str | None = None,
             _: User = Depends(need("republic.view")), user: User = Depends(need("report.download")),
             db: Session = Depends(get_db)):
    if fmt not in MIME:
        raise HTTPException(400, "Noto'g'ri format")
    name, blob, _c = make_file(db, fmt, a, b)
    from urllib.parse import quote
    return Response(blob, media_type=MIME[fmt],
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


class SendIn(BaseModel):
    fmts: list[str]
    chat_ids: list[int]
    a: str | None = None
    b: str | None = None
    ack: bool = True


def _run(job_id: int, fmts, chats, a, b, post_id: int = 0, pitems: dict | None = None, ack: bool = False):
    from ..services import posts as P
    pitems = pitems or {}
    chat_err: dict[str, str] = {}
    last_mid: dict[str, int | None] = {}
    lines, done, fails = [], 0, 0
    total = len(fmts) * len(chats)

    def flush(st="running"):
        with engine.begin() as c:
            c.execute(text("UPDATE send_jobs SET status=:s, progress=:p, log=:l WHERE id=:i"),
                      {"s": st, "p": round(100 * done / max(total, 1), 1), "l": "\n".join(lines)[-6000:], "i": job_id})
    try:
        for fmt in fmts:
            try:
                with SessionLocal() as db:
                    name, blob, cap = make_file(db, fmt, a, b)
            except HTTPException as e:
                lines.append(f"✗ {fmt}: {e.detail}")
                fails += len(chats); done += len(chats); flush()
                continue
            if post_id:
                P.add_file(post_id, name)
            is_last = fmt == fmts[-1]
            for chat_id, title in chats:
                iid = pitems.get(str(chat_id))
                try:
                    r = tg.send_file(chat_id, name, blob, cap, P.markup(iid) if (ack and is_last and iid) else None)
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
                time.sleep(3.2)
        for iid in pitems.values():
            with engine.connect() as c:
                st = c.execute(text("SELECT status FROM tg_post_items WHERE id=:i"), {"i": iid}).scalar()
            if st == "wait":
                P.item_done(iid, False, None, "Fayl tayyorlanmadi")
        flush("error" if fails and fails >= total else "done")
    except Exception as e:  # noqa: BLE001
        lines.append(f"✗ Kutilmagan xato: {e}")
        flush("error")


@router.post("/send")
def send(body: SendIn, user: User = Depends(need("telegram.send")), _p: User = Depends(need("republic.view")),
         db: Session = Depends(get_db)):
    if not body.fmts or any(f not in MIME for f in body.fmts):
        raise HTTPException(400, "Formatni tanlang (PDF / Excel)")
    if not body.chat_ids:
        raise HTTPException(400, "Kamida bitta kanal yoki guruhni tanlang")
    chats = [(r[0], r[1]) for r in db.execute(text("SELECT chat_id, title FROM tg_chats WHERE is_active=1 AND id IN :ids")
                                              .bindparams(bindparam("ids", expanding=True)), {"ids": body.chat_ids})]
    if not chats:
        raise HTTPException(400, "Tanlangan kanallar topilmadi")
    if not db.execute(text("SELECT 1 FROM kv WHERE k='tg_token'")).first():
        raise HTTPException(400, "Telegram bot sozlanmagan (Sozlamalar bo'limi)")
    _build(db, body.a, body.b)   # mavjudligini tekshiradi
    db.execute(text("INSERT INTO send_jobs (status,progress,log,created_by,created_at) VALUES ('running',0,'',:u,:t)"),
               {"u": user.username, "t": datetime.now()})
    job_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    log(db, user.username, "telegram_respublika", f"{', '.join(body.fmts)} → {', '.join(c[1] for c in chats)}")
    db.commit()
    from ..services import posts as P
    pid, pitems = P.create_post("respublika", "Respublika dinamikasi", "", [], body.ack, user.username, chats)
    threading.Thread(target=_run, daemon=True, args=(job_id, body.fmts, chats, body.a, body.b, pid, pitems, body.ack)).start()
    return {"id": job_id}
