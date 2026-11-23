"""Kunlik topshiriq: 5 ta Excel fayl → jadvallar va xodimlar bo'yicha topshiriq fayli (alohida bo'lim).

Yuklash → fon vazifasi (parse, hisoblash, Excel fayllar) → arxiv; Telegramga yuborish mavjud bot va kanallar orqali.
Asl fayllar serverda saqlanadi (data/daily/<sana>/orig), tayyor fayllar — (data/daily/<sana>/out)."""
import io
import shutil
import time
import traceback
import uuid
import zipfile
from datetime import date, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, engine, get_db
from ..deps import has_perm, log, need, need_any
from ..models import DailyBatch, User
from ..services import daily as D
from ..services import posts as P
from ..services import sendjobs
from ..services import telegram as tg
from ..tasks import submit, task
from .telegram import _chats

router = APIRouter(prefix="/daily", tags=["daily"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GROUPS = ("t1", "t2", "task")
MIME = {"xlsx": XLSX, "png": "image/png"}
LIMIT = D.MAX_XLSX_MB * 1048576


def _dir(end: date):
    return D.folder(end)


def _row(b: DailyBatch, full: bool = False) -> dict:
    d = {"id": b.id, "date": b.task_date.isoformat(), "status": b.status, "progress": round(b.progress or 0, 1),
         "message": b.message, "files": b.files or {}, "counts": b.counts or {}, "by": b.uploaded_by,
         "at": b.uploaded_at.isoformat(), "finished_at": b.finished_at.isoformat() if b.finished_at else None,
         "ready": b.status == "done"}
    if full:
        d["ask"] = b.ask or []
        d["tables"] = (b.data or {}).get("tables", [])
        d["outs"] = [{"k": x["k"], "title": x["title"], "ext": x["ext"], "default": x["default"], "group": x["group"],
                      "rows": (b.counts or {}).get(x["k"])} for x in D.out_specs(D.load_settings())
                     if (_dir(b.task_date) / "out" / f"{x['k']}.{x['ext']}").exists()]
        d["region"] = (b.data or {}).get("region", "")
    return d


def _get(db: Session, bid: int) -> DailyBatch:
    b = db.get(DailyBatch, bid)
    if not b:
        raise HTTPException(404, "Topilmadi")
    return b


# ----------------------------------------------------------------------------------------- yuklash
def _save_stream(f: UploadFile, dest) -> None:
    n = 0
    with open(dest, "wb") as out:
        while chunk := f.file.read(1 << 20):
            n += len(chunk)
            if n > LIMIT:
                raise HTTPException(400, f"«{f.filename}» juda katta ({D.MAX_XLSX_MB} MB dan oshmasin)")
            out.write(chunk)
    with open(dest, "rb") as chk:
        if chk.read(2) != b"PK":
            raise HTTPException(400, f"«{f.filename}» — Excel (.xlsx) fayl emas")


@router.post("/upload")
def upload(files: list[UploadFile] = File(...), day: str = Form(""), user: User = Depends(need("daily.upload")),
           db: Session = Depends(get_db)):
    try:
        end = date.fromisoformat(day) if day.strip() else date.today()
    except ValueError:
        raise HTTPException(400, "Sana noto'g'ri")
    if len(files) != len(D.KINDS):
        raise HTTPException(400, f"Aynan {len(D.KINDS)} ta fayl kerak: " + ", ".join(D.LABEL.values()))
    tmp = settings.data_dir / "daily" / f"_tmp_{uuid.uuid4().hex}"
    tmp.mkdir(parents=True)
    try:
        found: dict[str, tuple] = {}
        for i, f in enumerate(files):
            if not (f.filename or "").lower().endswith(".xlsx"):
                raise HTTPException(400, f"«{f.filename}» — faqat .xlsx fayl qabul qilinadi")
            p = tmp / f"{i}.xlsx"
            _save_stream(f, p)
            try:
                kind, _h = D.detect(p, f.filename or "")
            except D.DailyError as e:
                raise HTTPException(400, str(e))
            if kind in found:
                raise HTTPException(400, f"Ikkita «{D.LABEL[kind]}» fayli yuklandi: «{found[kind][1]}» va «{f.filename}»")
            found[kind] = (p, f.filename or "", p.stat().st_size)
        miss = [D.LABEL[k] for k in D.KINDS if k not in found]
        if miss:
            raise HTTPException(400, "Yetishmayotgan fayl: " + ", ".join(miss))
        folder = _dir(end)
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
        (folder / "orig").mkdir(parents=True)
        for k, (p, _n, _s) in found.items():
            shutil.move(str(p), folder / "orig" / f"{k}.xlsx")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    meta = {k: {"name": v[1], "size": v[2]} for k, v in found.items()}
    b = db.scalar(select(DailyBatch).where(DailyBatch.task_date == end))
    replaced = bool(b)
    if not b:
        b = DailyBatch(task_date=end)
        db.add(b)
    b.status, b.progress, b.message, b.files, b.ask, b.data, b.counts = "queued", 0, "", meta, [], {}, {}
    b.uploaded_by, b.uploaded_at, b.finished_at = user.username, datetime.now(), None
    log(db, user.username, "kunlik_yuklash", f"{end.isoformat()} ({'qayta ' if replaced else ''}5 ta fayl)")
    db.commit()
    submit("daily.process", b.id)
    return {"id": b.id, "date": end.isoformat(), "replaced": replaced}


# ----------------------------------------------------------------------------------------- ishlov berish
def _set(bid: int, **kw) -> None:
    with SessionLocal() as db:
        b = db.get(DailyBatch, bid)
        if b:
            for k, v in kw.items():
                setattr(b, k, v)
            db.commit()


@task("daily.process")
def process(bid: int) -> None:
    with SessionLocal() as db:
        b = db.get(DailyBatch, bid)
        if not b:
            return
        end, meta = b.task_date, dict(b.files or {})
    _set(bid, status="running", progress=3, message="Fayllar o'qilmoqda…", ask=[])
    try:
        s = D.load_settings()
        data = {}
        for i, k in enumerate(D.KINDS):
            _set(bid, progress=5 + i * 12, message=f"{D.LABEL[k]} o'qilmoqda…")
            data[k] = D.read(_dir(end) / "orig" / f"{k}.xlsx", k)
            meta[k] = {**meta.get(k, {}), "rows": len(data[k])}
        unk = D.unknown_types(data["nometer"], s["types"])
        if unk:     # iste'molchi turi tushunarsiz: foydalanuvchidan bir marta so'raymiz (javob saqlanadi)
            _set(bid, status="ask", progress=65, files=meta, ask=unk,
                 message="Iste'molchi turlarini belgilang")
            return
        _set(bid, progress=70, message="Jadvallar hisoblanmoqda…")
        res = D.compute(end, data, s)
        out = _dir(end) / "out"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        for tb in res["tables"]:
            (out / f"{tb['key']}.xlsx").write_bytes(D.table_xlsx(tb, s["region"], end))
        _set(bid, progress=78, message="Jadvallar rasmga olinmoqda…")
        for i, tb in enumerate(res["tables"], 1):
            (out / f"img{i}.png").write_bytes(D.table_png(tb, s["region"], end))
        _set(bid, progress=85, message="Nomma-nom ro'yxatlar tayyorlanmoqda…")
        blob, _legacy = D.task_xlsx(end, data, s)
        (out / "task.xlsx").write_bytes(blob)
        files, counts = D.list_files(end, data, s)
        for k, bl in files.items():
            (out / f"{k}.xlsx").write_bytes(bl)
        _set(bid, status="done", progress=100, message="", files=meta, data=res, counts=counts,
             finished_at=datetime.now())
    except D.DailyError as e:
        _set(bid, status="error", message=str(e)[:490])
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        _set(bid, status="error", message=f"Kutilmagan xato: {e}"[:490])


def _requeue(db: Session, b: DailyBatch) -> None:
    b.status, b.progress, b.message, b.ask, b.finished_at = "queued", 0, "", [], None
    db.commit()
    submit("daily.process", b.id)


@router.post("/{bid}/recompute")
def recompute(bid: int, user: User = Depends(need("daily.upload")), db: Session = Depends(get_db)):
    b = _get(db, bid)
    if b.status in ("queued", "running"):
        raise HTTPException(400, "Hozir ishlanmoqda")
    if not (_dir(b.task_date) / "orig").exists():
        raise HTTPException(400, "Asl fayllar serverda topilmadi — qayta yuklang")
    log(db, user.username, "kunlik_qayta_hisoblash", b.task_date.isoformat())
    _requeue(db, b)
    return {"ok": True}


class TypesIn(BaseModel):
    map: dict[str, str]


@router.post("/{bid}/types")
def set_types(bid: int, body: TypesIn, user: User = Depends(need("daily.upload")), db: Session = Depends(get_db)):
    """Tushunarsiz iste'molchi turlarining javobi: saqlanadi va keyingi yuklashlarda qayta so'ralmaydi."""
    b = _get(db, bid)
    if not body.map or any(v not in D.CATS for v in body.map.values()):
        raise HTTPException(400, "Har bir tur uchun Aholi / Ulgurji / Balans dan birini tanlang")
    s = D.load_settings()
    s["types"] = {**s["types"], **{k: v for k, v in body.map.items() if k.strip()}}
    D.save_settings(s)
    log(db, user.username, "kunlik_turlar", ", ".join(f"{k}={v}" for k, v in body.map.items())[:500])
    _requeue(db, b)
    return {"ok": True}


# ----------------------------------------------------------------------------------------- ro'yxat, fayllar
@router.get("")
def listing(_: User = Depends(need("daily.view")), db: Session = Depends(get_db)):
    return [_row(b) for b in db.scalars(select(DailyBatch).order_by(DailyBatch.task_date.desc()))]


@router.get("/settings")
def get_settings(_: User = Depends(need("daily.view"))):
    s = D.load_settings()
    return {**s, "placeholders": D.PLACEHOLDERS, "examples": D.names_example(s), "labels": D.edge_labels(s["time_edges"]),
            "defaults": D.DEFAULTS}


class SettingsIn(BaseModel):
    region: str
    t1_title: str
    t2_title: str
    task_title: str
    offline_days: int
    time_edges: list[int]
    esp_order: list[str]
    types: dict[str, str] = {}
    fn_t1: str
    fn_t2: str
    fn_task: str
    chats: dict[str, list[int]] = {}


@router.put("/settings")
def put_settings(body: SettingsIn, user: User = Depends(need("daily.settings")), db: Session = Depends(get_db)):
    s = {**D.load_settings(), **body.model_dump()}
    s["esp_order"] = [e.strip() for e in s["esp_order"] if e.strip()]
    s["chats"] = {k: list(dict.fromkeys(s["chats"].get(k, []))) for k in GROUPS}
    for k in ("region", "t1_title", "t2_title", "task_title", "fn_t1", "fn_t2", "fn_task"):
        s[k] = s[k].strip()
    err = D.validate_settings(s)
    if err:
        raise HTTPException(400, err)
    D.save_settings(s)
    log(db, user.username, "kunlik_sozlama", "o'zgartirildi")
    db.commit()
    return {**s, "examples": D.names_example(s), "labels": D.edge_labels(s["time_edges"])}


@router.get("/chats")
def chats(_: User = Depends(need_any("daily.send", "daily.settings")), db: Session = Depends(get_db)):
    return _chats(db, True)


@router.get("/{bid}")
def detail(bid: int, _: User = Depends(need("daily.view")), db: Session = Depends(get_db)):
    b = _get(db, bid)
    # Eski versiyada tayyorlangan kun (rasm va 7 ta fayl yo'q) — asl fayllar bor bo'lsa, o'zi qayta tayyorlanadi
    if b.status == "done" and not (_dir(b.task_date) / "out" / "img1.png").exists() and (_dir(b.task_date) / "orig").exists():
        _requeue(db, b)
    return _row(b, True)


def _out_file(b: DailyBatch, which: str) -> tuple[str, bytes, str]:
    s = D.load_settings()
    sp = D.spec_of(s, which)
    if not sp:
        raise HTTPException(404, "Noma'lum fayl")
    f = _dir(b.task_date) / "out" / f"{which}.{sp['ext']}"
    if b.status != "done" or not f.exists():
        raise HTTPException(404, "Fayl hali tayyor emas")
    return D.file_name(s, which, b.task_date), f.read_bytes(), sp["ext"]


def _attach(name: str, blob: bytes, mime: str = XLSX) -> Response:
    return Response(blob, media_type=mime, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/{bid}/file/{which}")
def get_file(bid: int, which: str, user: User = Depends(need("daily.view")), db: Session = Depends(get_db)):
    b = _get(db, bid)
    if which in D.KINDS:
        if not has_perm(user, "daily.original"):
            raise HTTPException(403, "Asl fayllar uchun ruxsat yo'q")
        f = _dir(b.task_date) / "orig" / f"{which}.xlsx"
        if not f.exists():
            raise HTTPException(404, "Asl fayl serverda topilmadi")
        return _attach((b.files.get(which) or {}).get("name") or f"{D.LABEL[which]}.xlsx", f.read_bytes())
    name, blob, ext = _out_file(b, which)
    return _attach(name, blob, MIME[ext])


@router.get("/{bid}/zip/{what}")
def get_zip(bid: int, what: str, user: User = Depends(need("daily.view")), db: Session = Depends(get_db)):
    """Barcha tayyor fayllar (out) yoki barcha asl fayllar (orig) — bitta ZIP."""
    b = _get(db, bid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        if what == "orig":
            if not has_perm(user, "daily.original"):
                raise HTTPException(403, "Asl fayllar uchun ruxsat yo'q")
            for k in D.KINDS:
                f = _dir(b.task_date) / "orig" / f"{k}.xlsx"
                if f.exists():
                    z.write(f, (b.files.get(k) or {}).get("name") or f"{D.LABEL[k]}.xlsx")
        elif what == "out":
            for sp in D.out_specs(D.load_settings()):
                if (_dir(b.task_date) / "out" / f"{sp['k']}.{sp['ext']}").exists():
                    n, blob, _e = _out_file(b, sp["k"])
                    z.writestr(n, blob)
        else:
            raise HTTPException(404, "Noma'lum")
    return _attach(f"Kunlik_topshiriq_{b.task_date:%d.%m.%Y}_{what}.zip", buf.getvalue(), "application/zip")


@router.delete("/{bid}")
def delete(bid: int, user: User = Depends(need("daily.delete")), db: Session = Depends(get_db)):
    b = _get(db, bid)
    folder = _dir(b.task_date)
    log(db, user.username, "kunlik_ochirish", b.task_date.isoformat())
    db.delete(b)
    db.commit()
    shutil.rmtree(folder, ignore_errors=True)
    return {"ok": True}


# ----------------------------------------------------------------------------------------- Telegram
class SendIn(BaseModel):
    files: list[str]
    chat_ids: list[int]
    ack: bool = False


@router.post("/{bid}/send")
def send(bid: int, body: SendIn, user: User = Depends(need("daily.send")), _p: User = Depends(need("telegram.send")),
         db: Session = Depends(get_db)):
    b = _get(db, bid)
    if b.status != "done":
        raise HTTPException(400, "Fayllar hali tayyor emas")
    order = [x["k"] for x in D.out_specs(D.load_settings())]
    if not body.files or any(f not in order for f in body.files):
        raise HTTPException(400, "Yuboriladigan faylni tanlang")
    body.files = sorted(set(body.files), key=order.index)        # doim bir xil tartibda: rasmlar, keyin ro'yxatlar
    chats = sendjobs.chats_for(db, body.chat_ids)
    sendjobs.require_bot(db)
    job_id = sendjobs.create_job(db, user.username)
    log(db, user.username, "telegram_kunlik", f"{b.task_date.isoformat()}: {', '.join(body.files)} → {', '.join(c[1] for c in chats)}")
    db.commit()
    pid, pitems = P.create_post("kunlik", f"Kunlik topshiriq — {b.task_date:%d.%m.%Y}", "", [], body.ack, user.username, chats)
    submit("daily.send", job_id, bid, body.files, chats, pid, pitems, body.ack)
    return {"id": job_id}


@task("daily.send")
def run_send(job_id: int, bid: int, files, chats, post_id: int = 0, pitems: dict | None = None, ack: bool = False) -> None:
    pitems = pitems or {}
    chat_err: dict[str, str] = {}
    last_mid: dict[str, int | None] = {}
    lines: list[str] = []
    done = fails = 0
    # Tanlangan 2 ta jadval rasmi bitta albom (karusel) bo'lib ketadi; qolgan fayllar alohida-alohida
    pics = [f for f in files if f.startswith("img")]
    units = ([pics] if len(pics) > 1 else []) + [[f] for f in files if f not in pics or len(pics) == 1]
    total = len(units) * len(chats)

    def flush(st="running"):
        sendjobs.flush(job_id, st, done, total, lines)

    lines.append(f"… Yuborish boshlandi: {len(files)} ta fayl → {len(chats)} ta kanal")
    flush()
    try:
        for ui, unit in enumerate(units):
            try:
                with SessionLocal() as db:
                    b = _get(db, bid)
                    blobs = [_out_file(b, w) for w in unit]
            except HTTPException as e:
                lines.append(f"✗ {', '.join(unit)}: {e.detail}")
                fails += len(chats)
                done += len(chats)
                flush()
                continue
            label = f"{len(blobs)} ta jadval rasmi (albom)" if len(blobs) > 1 else blobs[0][0]
            if post_id:
                for n, _b, _e in blobs:
                    P.add_file(post_id, n)
            is_last = ui == len(units) - 1
            lines.append(f"… {label} yuborilmoqda")
            flush()
            for chat_id, title in chats:
                iid = pitems.get(str(chat_id))
                try:
                    mk = P.markup(iid) if (ack and is_last and iid) else None
                    if len(blobs) > 1:
                        res = tg.send_album(chat_id, [(n, bl) for n, bl, _e in blobs])
                        if mk:      # albomga tugma qo'yib bo'lmaydi — alohida qisqa xabar
                            res = tg.send_text(chat_id, "👆 Yuqoridagi xabar bilan tanishib chiqing.", reply_markup=mk)
                    else:
                        n, bl, ext = blobs[0]
                        res = tg.send_photo(chat_id, n, bl, mk) if ext == "png" else tg.send_file(chat_id, n, bl, mk)
                    last_mid[str(chat_id)] = (res or {}).get("message_id")
                    lines.append(f"✓ {label} → {title}")
                except tg.TgError as e:
                    lines.append(f"✗ {label} → {title}: {e}")
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
