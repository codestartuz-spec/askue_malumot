"""PDF hisobotlar uchun umumiy router-fabrika: Respublika dinamikasi va AG dinamikasi bir xil jarayon.

Har bir tur `Kind` bilan tavsiflanadi (modeli, parseri, taqqoslash va chiqarish funksiyalari). Router
yuklash / ro'yxat / o'chirish / asl PDF / solishtirish / yuklab olish / Telegramga yuborishni o'zi yasaydi."""
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Callable
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, engine, get_db
from ..deps import has_perm, log, need, need_any
from ..models import User
from ..services import pdfcheck, sendjobs
from ..services import posts as P
from ..services import telegram as tg
from ..tasks import submit, task

MIME = {"pdf": "application/pdf", "orig": "application/pdf", "png": "image/png",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
KINDS: dict[str, "Kind"] = {}


@dataclass
class Parsed:
    end: date
    start: date | None
    payload: dict
    count: int


@dataclass
class Kind:
    key: str                              # "republic" | "ag"  (ruxsat prefiksi, papka, vazifa kaliti)
    model: type
    missing_msg: str                      # "Hali ... PDF'i yuklanmagan"
    audit: tuple[str, str, str]           # (yuklash, o'chirish, telegram)
    post_title: str
    parse: Callable[[dict, str], Parsed]  # izolyatsiya qilingan parser natijasi → Parsed
    count: Callable[[dict], int]
    default_start: Callable[[date], date]
    compare: Callable[[dict | None, dict, str, str], object]
    view: Callable[[object, date | None, date, date], dict]
    render: Callable[[object, str, date | None, date, date], tuple[str, bytes]]       # → (fayl nomi, mazmun)
    orig: Callable[[date, date, str | None], str]                                    # (bd, start, saqlangan_nom) → fayl nomi
    images: Callable | None = None        # (res, ad, bd, start) → [(fayl nomi, PNG)] — jadval rasmlari (ixtiyoriy)
    router: APIRouter = field(default=None)

    @property
    def folder(self):
        return settings.data_dir / self.key

    def file(self, end: date):
        return self.folder / f"{end.isoformat()}.pdf"

    def dates(self, db: Session):
        return list(db.scalars(select(self.model).order_by(self.model.end_date.desc())))

    def pick(self, db, a, b, mode):
        reps = self.dates(db)
        if not reps:
            raise HTTPException(400, self.missing_msg)
        by = {r.end_date.isoformat(): r for r in reps}
        bb = by.get(b) if b else reps[0]
        if not bb:
            raise HTTPException(400, "Tanlangan sana topilmadi")
        if a:
            aa = by.get(a)
            if not aa:
                raise HTTPException(400, "Solishtiriladigan sana topilmadi")
        elif mode == "oy":                       # PDF'ning o'z dinamikasi (boshlang'ich sanadan)
            aa = None
        else:                                    # kunlik: oldingi eng yaqin sana
            older = [r for r in reps if r.end_date < bb.end_date]
            aa = older[0] if older else None
        return aa, bb

    def build(self, db, a, b, mode):
        aa, bb = self.pick(db, a, b, mode)
        start = bb.start_date or self.default_start(bb.end_date)
        res = self.compare(aa.data if aa else None, bb.data, (aa.end_date if aa else start).isoformat(),
                           bb.end_date.isoformat())
        return res, (aa.end_date if aa else None), bb.end_date, start

    def make_images(self, db, a, b, mode="oy") -> list[tuple[str, bytes]]:
        if not self.images:
            raise HTTPException(400, "Bu bo'lim uchun rasm yo'q")
        res, ad, bd, start = self.build(db, a, b, mode)
        return self.images(res, ad, bd, start)

    def make_file(self, db, fmt, a, b, mode="oy") -> tuple[str, bytes]:
        res, ad, bd, start = self.build(db, a, b, mode)
        if fmt == "orig":
            f = self.file(bd)
            if not f.exists():
                raise HTTPException(404, "Asl PDF fayl serverda topilmadi — shu sanani qayta yuklang")
            rep = db.scalar(select(self.model).where(self.model.end_date == bd))
            return self.orig(bd, start, rep.filename if rep else None), f.read_bytes()
        return self.render(res, fmt, ad, bd, start)


class SendIn(BaseModel):
    fmts: list[str]
    chat_ids: list[int]
    a: str | None = None
    b: str | None = None
    mode: str = "oy"
    ack: bool = True


def _guard_orig(kind: Kind, user: User, fmts) -> None:
    if "orig" in fmts and not has_perm(user, f"{kind.key}.original"):
        raise HTTPException(403, "Asl PDF uchun ruxsat yo'q")


def make_router(kind: Kind) -> APIRouter:
    k = kind.key
    r = APIRouter(prefix=f"/{k}", tags=[k])

    @r.post("/upload")
    def upload(file: UploadFile = File(...), user: User = Depends(need(f"{k}.upload")), db: Session = Depends(get_db)):
        data = pdfcheck.read_upload(file)
        rep = kind.parse(pdfcheck.parse_isolated(k, data), file.filename or "")
        row = db.scalar(select(kind.model).where(kind.model.end_date == rep.end))
        replaced = bool(row)
        from datetime import datetime
        if row:
            row.data, row.start_date, row.filename = rep.payload, rep.start, file.filename or ""
            row.uploaded_by, row.uploaded_at = user.username, datetime.now()
        else:
            db.add(kind.model(end_date=rep.end, start_date=rep.start, filename=file.filename or "",
                              data=rep.payload, uploaded_by=user.username))
        kind.folder.mkdir(exist_ok=True)
        kind.file(rep.end).write_bytes(data)
        log(db, user.username, kind.audit[0], f"{file.filename} → {rep.end.isoformat()}")
        db.commit()
        return {"end": rep.end.isoformat(), "start": rep.start.isoformat() if rep.start else None,
                "pages": rep.count, "replaced": replaced}

    @r.get("")
    def listing(_: User = Depends(need_any(f"{k}.view", f"{k}.upload")), db: Session = Depends(get_db)):
        return [{"id": x.id, "end": x.end_date.isoformat(), "start": x.start_date.isoformat() if x.start_date else None,
                 "filename": x.filename, "by": x.uploaded_by, "at": x.uploaded_at.isoformat(),
                 "pages": kind.count(x.data), "has_file": kind.file(x.end_date).exists()} for x in kind.dates(db)]

    @r.delete("/{rid}")
    def delete(rid: int, user: User = Depends(need("data.delete")), db: Session = Depends(get_db)):
        x = db.get(kind.model, rid)
        if not x:
            raise HTTPException(404, "Topilmadi")
        log(db, user.username, kind.audit[1], x.end_date.isoformat())
        f = kind.file(x.end_date)
        db.delete(x)
        db.commit()
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass
        return {"ok": True}

    @r.get("/{rid}/file")
    def file(rid: int, inline: bool = False, user: User = Depends(need(f"{k}.original")), db: Session = Depends(get_db)):
        """Serverda saqlangan asl PDF: brauzerda ochish (inline) yoki yuklab olish."""
        x = db.get(kind.model, rid)
        if not x:
            raise HTTPException(404, "Topilmadi")
        f = kind.file(x.end_date)
        if not f.exists():
            raise HTTPException(404, "Fayl serverda topilmadi — shu sanani qayta yuklang")
        name = x.filename or f"{k}_{x.end_date.isoformat()}.pdf"
        return Response(f.read_bytes(), media_type="application/pdf",
                        headers={"Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(name)}"})

    @r.get("/compare")
    def compare(a: str | None = None, b: str | None = None, mode: str = "oy", _: User = Depends(need(f"{k}.view")),
                db: Session = Depends(get_db)):
        res, ad, bd, start = kind.build(db, a, b, mode)
        return {"mode": mode, "a": ad.isoformat() if ad else None, "b": bd.isoformat(), "start": start.isoformat(),
                **kind.view(res, ad, bd, start), "dates": [x.end_date.isoformat() for x in kind.dates(db)]}

    @r.get("/download")
    def download(fmt: str = "pdf", a: str | None = None, b: str | None = None, mode: str = "oy",
                 _: User = Depends(need(f"{k}.view")), user: User = Depends(need("report.download")),
                 db: Session = Depends(get_db)):
        if fmt not in MIME or (fmt == "png" and not kind.images):
            raise HTTPException(400, "Noto'g'ri format")
        _guard_orig(kind, user, [fmt])
        if fmt == "png":                                  # barcha jadval rasmlari bitta ZIP'da
            import io
            import zipfile
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
                for n_, b_ in kind.make_images(db, a, b, mode):
                    z.writestr(n_, b_)
            bd_ = kind.build(db, a, b, mode)[2]
            return Response(buf.getvalue(), media_type="application/zip", headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(f'{kind.key}_{bd_.isoformat()}_rasmlar.zip')}"})
        name, blob = kind.make_file(db, fmt, a, b, mode)
        return Response(blob, media_type=MIME[fmt],
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})

    @r.post("/send")
    def send(body: SendIn, user: User = Depends(need("telegram.send")), _p: User = Depends(need(f"{k}.view")),
             db: Session = Depends(get_db)):
        if not body.fmts or any(f not in MIME or (f == "png" and not kind.images) for f in body.fmts):
            raise HTTPException(400, "Formatni tanlang (PDF / Excel)")
        _guard_orig(kind, user, body.fmts)
        chats = sendjobs.chats_for(db, body.chat_ids)
        sendjobs.require_bot(db)
        kind.build(db, body.a, body.b, body.mode)     # mavjudligini tekshiradi
        job_id = sendjobs.create_job(db, user.username)
        log(db, user.username, kind.audit[2], f"{', '.join(body.fmts)} → {', '.join(c[1] for c in chats)}")
        db.commit()
        pid, pitems = P.create_post(k, kind.post_title, "", [], body.ack, user.username, chats)
        submit("pdfreport.send", k, job_id, body.fmts, chats, body.a, body.b, pid, pitems, body.ack, body.mode)
        return {"id": job_id}

    kind.router = r
    KINDS[k] = kind
    return r


def _send_images(kind, job_id, chats, a, b, mode, post_id, pitems, with_ack, chat_err, last_mid, lines, flush) -> None:
    """Jadval rasmlari: 2–10 ta rasm bitta albom (karusel) bo'lib, har bir kanalga."""
    try:
        with SessionLocal() as db:
            imgs = kind.make_images(db, a, b, mode)
    except HTTPException as e:
        lines.append(f"✗ rasm: {e.detail}")
        for chat_id, _t in chats:
            chat_err[str(chat_id)] = str(e.detail)
        return
    if post_id:
        for n_, _b in imgs:
            P.add_file(post_id, n_)
    for chat_id, title in chats:
        iid = pitems.get(str(chat_id))
        try:
            mk = P.markup(iid) if (with_ack and iid) else None
            if len(imgs) == 1:
                res = tg.send_photo(chat_id, imgs[0][0], imgs[0][1], mk)
            else:
                res = tg.send_album(chat_id, imgs)
                if mk:                                    # albomga tugma qo'yib bo'lmaydi — tugma alohida xabarda
                    res = tg.send_text(chat_id, "Jadvallar yuborildi. Tanishib chiqqach tugmani bosing.", reply_markup=mk)
            last_mid[str(chat_id)] = res.get("message_id")
            lines.append(f"✓ {len(imgs)} ta jadval rasmi → {title}")
        except tg.TgError as e:
            lines.append(f"✗ jadval rasmlari → {title}: {e}")
            chat_err[str(chat_id)] = str(e)
        flush()
        time.sleep(settings.send_delay_sec)


@task("pdfreport.send")
def run_send(kind_key: str, job_id: int, fmts, chats, a, b, post_id: int = 0, pitems: dict | None = None,
             ack: bool = False, mode: str = "oy") -> None:
    kind = KINDS[kind_key]
    pitems = pitems or {}
    chat_err: dict[str, str] = {}
    last_mid: dict[str, int | None] = {}
    lines: list[str] = []
    done = fails = 0
    total = len(fmts) * len(chats)

    def flush(st="running"):
        sendjobs.flush(job_id, st, done, total, lines)

    try:
        for fmt in fmts:
            is_last = fmt == fmts[-1]
            if fmt == "png":
                _send_images(kind, job_id, chats, a, b, mode, post_id, pitems, ack and is_last, chat_err, last_mid, lines, flush)
                done += len(chats)
                fails = len(chat_err)
                if is_last:
                    for chat_id, _t in chats:
                        iid = pitems.get(str(chat_id))
                        if iid:
                            P.item_done(iid, str(chat_id) not in chat_err, last_mid.get(str(chat_id)), chat_err.get(str(chat_id), ""))
                flush()
                continue
            try:
                with SessionLocal() as db:
                    name, blob = kind.make_file(db, fmt, a, b, mode)
            except HTTPException as e:
                lines.append(f"✗ {fmt}: {e.detail}")
                fails += len(chats)
                done += len(chats)
                flush()
                continue
            if post_id:
                P.add_file(post_id, name)
            for chat_id, title in chats:
                iid = pitems.get(str(chat_id))
                try:
                    res = tg.send_file(chat_id, name, blob, P.markup(iid) if (ack and is_last and iid) else None)
                    last_mid[str(chat_id)] = res.get("message_id")
                    lines.append(f"✓ {name} → {title}")
                except tg.TgError as e:
                    lines.append(f"✗ {name} → {title}: {e}")
                    chat_err[str(chat_id)] = str(e)
                    fails += 1
                if is_last and iid:
                    P.item_done(iid, str(chat_id) not in chat_err, last_mid.get(str(chat_id)), chat_err.get(str(chat_id), ""))
                done += 1
                flush()
                time.sleep(settings.send_delay_sec)
        for iid in pitems.values():
            with engine.connect() as c:
                st = c.execute(text("SELECT status FROM tg_post_items WHERE id=:i"), {"i": iid}).scalar()
            if st == "wait":
                P.item_done(iid, False, None, "Fayl tayyorlanmadi")
        flush("error" if fails and fails >= total else "done")
    except Exception as e:  # noqa: BLE001
        lines.append(f"✗ Kutilmagan xato: {e}")
        flush("error")
