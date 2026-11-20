import re
import time
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import need
from ..models import Job, User

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _save(f: UploadFile, tag: str) -> str:
    name = re.sub(r"[^\w.\-]+", "_", f.filename or tag)
    if not name.lower().endswith((".csv", ".csv.gz", ".gz")):
        raise HTTPException(400, f"{tag}: faqat .csv.gz yoki .csv fayl qabul qilinadi")
    path = settings.data_dir / "uploads" / f"{int(time.time() * 1000)}_{tag}_{name}"
    with open(path, "wb") as out:
        while chunk := f.file.read(1024 * 1024):
            out.write(chunk)
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
            "area_name": j.area_name, "details_name": j.details_name, "created_by": j.created_by,
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
