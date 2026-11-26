import re
import time
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import log, need
from ..models import Job, User
from ..services import chunked

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _save(f: UploadFile, tag: str) -> str:
    name = re.sub(r"[^\w.\-]+", "_", f.filename or tag)
    if not name.lower().endswith((".csv", ".csv.gz", ".gz")):
        raise HTTPException(400, f"{tag}: faqat .csv.gz yoki .csv fayl qabul qilinadi")
    path = settings.data_dir / "uploads" / f"{int(time.time() * 1000)}_{tag}_{name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    limit, size, first = settings.max_upload_mb * 1048576, 0, True
    try:
        with open(path, "wb") as out:
            while chunk := f.file.read(1024 * 1024):
                if first and name.lower().endswith(".gz") and chunk[:2] != b"\x1f\x8b":
                    raise HTTPException(400, f"{tag}: bu haqiqiy .gz fayl emas")
                first = False
                size += len(chunk)
                if size > limit:
                    raise HTTPException(400, f"{tag}: fayl {settings.max_upload_mb} MB dan katta")
                out.write(chunk)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    return str(path)


def _date_from(name: str | None) -> date | None:
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", name or "")
    if m:
        try:
            return date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            return None
    return None


def job_out(j) -> dict:
    return {"id": j.id, "status": j.status, "progress": j.progress, "stage": j.stage,
            "message": j.message, "snap_date": j.snap_date.isoformat(), "stats": j.stats,
            "area_name": j.area_name, "has_snapshot": j.status == "done", "details_name": j.details_name, "created_by": j.created_by,
            "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None}


@router.post("")
def upload(area: UploadFile | None = File(None), details: UploadFile | None = File(None),
           snap_date: str | None = Form(None), user: User = Depends(need("data.upload")),
           db: Session = Depends(get_db)):
    if not area and not details:
        raise HTTPException(400, "Kamida bitta fayl tanlang")
    d = None
    if snap_date:
        try:
            d = date.fromisoformat(snap_date)
        except ValueError:
            raise HTTPException(400, "Sana noto'g'ri")
    d = d or _date_from(area.filename if area else None) or _date_from(details.filename if details else None) \
        or date.today()
    job = Job(snap_date=d, created_by=user.username,
              area_path=_save(area, "area") if area else None,
              details_path=_save(details, "details") if details else None,
              area_name=area.filename if area else None, details_name=details.filename if details else None)
    db.add(job)
    db.commit()
    return job_out(job)


# ------------------------------------------------------------------ BO'LAKLAB YUKLASH
# Details ~5 MB lik bo'laklarga bo'lingan (generator: ...part001-of-008.csv.gz + .manifest.json).
# Tartib: POST /session -> PUT /{id}/area va PUT /{id}/details/{n} (har biri alohida, qayta yuborish mumkin)
#         -> POST /{id}/finish (tekshiruv + navbatga qo'yish).
class SessionIn(BaseModel):
    snap_date: str | None = None
    area_name: str | None = Field(None, max_length=200)
    details_name: str | None = Field(None, max_length=200)
    has_area: bool = False
    details_parts: int = Field(0, ge=0, le=chunked.MAX_PARTS)
    manifest: dict | None = None


def _purge_stale(db: Session) -> None:
    """Tugallanmagan (yarim qolgan) bo'laklab yuklash seanslarini tozalaydi."""
    old = datetime.now() - timedelta(hours=settings.stale_upload_hours)
    for j in db.query(Job).filter(Job.status == "uploading", Job.created_at < old).all():
        chunked.remove_session(j.id)
        db.delete(j)
    db.commit()


def _session(db: Session, jid: int) -> Job:
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "Yuklash seansi topilmadi")
    if j.status != "uploading":
        raise HTTPException(409, "Bu yuklash allaqachon yakunlangan")
    return j


@router.post("/session")
def start_session(body: SessionIn, user: User = Depends(need("data.upload")), db: Session = Depends(get_db)):
    if not body.has_area and not body.details_parts:
        raise HTTPException(400, "Kamida bitta fayl tanlang")
    d = None
    if body.snap_date:
        try:
            d = date.fromisoformat(body.snap_date)
        except ValueError:
            raise HTTPException(400, "Sana noto'g'ri")
    d = d or _date_from(body.details_name) or _date_from(body.area_name) or date.today()
    try:
        manifest = chunked.clean_manifest(body.manifest)
    except chunked.ChunkError as e:
        raise HTTPException(400, str(e))
    if manifest and body.details_parts and manifest["parts_total"] != body.details_parts:
        raise HTTPException(400, f"Manifestda {manifest['parts_total']} ta bo'lak, siz {body.details_parts} ta tanladingiz")
    _purge_stale(db)
    job = Job(snap_date=d, created_by=user.username, status="uploading", stage="Fayllar yuklanmoqda",
              area_name=body.area_name if body.has_area else None,
              details_name=body.details_name if body.details_parts else None,
              stats={"parts": body.details_parts, "has_area": body.has_area})
    db.add(job)
    db.commit()
    if manifest:
        chunked.save_manifest(job.id, manifest)
    return {"id": job.id, "snap_date": d.isoformat()}


async def _body(request: Request) -> bytes:
    limit = settings.max_part_mb * 1048576
    n = request.headers.get("content-length")
    if n and n.isdigit() and int(n) > limit:
        raise HTTPException(413, f"Bo'lak {settings.max_part_mb} MB dan katta")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > limit:
            raise HTTPException(413, f"Bo'lak {settings.max_part_mb} MB dan katta")
    return bytes(data)


@router.put("/{jid}/area")
async def put_area(jid: int, request: Request, _: User = Depends(need("data.upload")), db: Session = Depends(get_db)):
    _session(db, jid)
    try:
        return chunked.save_area(jid, await _body(request))
    except chunked.ChunkError as e:
        raise HTTPException(400, str(e))


@router.put("/{jid}/details/{n}")
async def put_details_part(jid: int, n: int, request: Request, _: User = Depends(need("data.upload")),
                           db: Session = Depends(get_db)):
    j = _session(db, jid)
    total = int((j.stats or {}).get("parts") or 0)
    try:
        return chunked.save_part(jid, n, total, await _body(request))
    except chunked.ChunkError as e:
        raise HTTPException(400, str(e))


@router.get("/{jid}/received")
def received(jid: int, _: User = Depends(need("data.upload")), db: Session = Depends(get_db)):
    """Qaysi bo'laklar serverga yetib kelgan (uzilgandan keyin davom ettirish uchun)."""
    _session(db, jid)
    return chunked.received(jid)


@router.post("/{jid}/finish")
def finish_session(jid: int, user: User = Depends(need("data.upload")), db: Session = Depends(get_db)):
    j = _session(db, jid)
    st = j.stats or {}
    total, has_area = int(st.get("parts") or 0), bool(st.get("has_area"))
    try:
        chunked.verify_complete(jid, total, has_area)
    except chunked.ChunkError as e:
        raise HTTPException(409, str(e))
    j.area_path = str(chunked.area_file(jid)) if has_area else None
    j.details_path = str(chunked.details_dir(jid)) if total else None
    j.stats = None
    j.status, j.stage, j.progress = "queued", "Navbatda", 0
    db.commit()
    return job_out(j)


@router.delete("/{jid}/session")
def abort_session(jid: int, _: User = Depends(need("data.upload")), db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    if j and j.status == "uploading":
        chunked.remove_session(jid)
        db.delete(j)
        db.commit()
    return {"ok": True}


@router.get("/jobs")
def jobs(_: User = Depends(need("data.upload")), db: Session = Depends(get_db)):
    rows = db.query(Job).order_by(Job.id.desc()).limit(15).all()
    hb = db.execute(text("SELECT v FROM kv WHERE k='worker_heartbeat'")).scalar()
    return {"items": [job_out(j) for j in rows],
            "worker_alive": bool(hb and time.time() - int(hb) < 20)}


@router.get("/jobs/{jid}")
def job(jid: int, _: User = Depends(need("data.upload")), db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "Topilmadi")
    return job_out(j)


@router.delete("/jobs/{jid}")
def delete_job(jid: int, user: User = Depends(need("data.delete")), db: Session = Depends(get_db)):
    """Yuklash yozuvini, serverdagi fayllarni va (boshqa yuklash qolmasa) shu sana dinamikasini o'chiradi.
    Hisoblagich/TP ro'yxatlari (joriy holat) o'zgarmaydi — ular keyingi yuklash bilan yangilanadi."""
    import os
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "Topilmadi")
    if j.status == "running":
        raise HTTPException(400, "Bajarilayotgan yuklashni o'chirib bo'lmaydi. Tugashini kuting")
    for p in (j.area_path, j.details_path):
        chunked.remove_path(p)
    chunked.remove_session(jid)
    d = j.snap_date
    others = db.scalar(text("SELECT COUNT(*) FROM jobs WHERE snap_date=:d AND status='done' AND id<>:i"), {"d": d, "i": jid})
    removed = 0
    if j.status == "done" and not others:
        removed = db.execute(text("DELETE FROM snapshots WHERE snap_date=:d"), {"d": d}).rowcount
    log(db, user.username, "yuklash_ochirish", f"#{jid} {d.isoformat()} (dinamika qatorlari: {removed})")
    db.delete(j)
    db.commit()
    return {"ok": True, "snapshot_removed": bool(removed)}
