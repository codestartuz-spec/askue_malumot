import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..perms import PERMS, PRESETS
from ..settings_store import app_cfg
from .auth import user_out

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/bootstrap")
def bootstrap(user: User = Depends(current_user), db: Session = Depends(get_db)):
    esps = [dict(r) for r in db.execute(text(
        "SELECT id, name, label FROM esps ORDER BY sort, label")).mappings()]
    brigades = [dict(r) for r in db.execute(text(
        "SELECT b.id, b.esp_id, b.name FROM brigades b JOIN esps e ON e.id=b.esp_id "
        "ORDER BY e.sort, e.label, b.number")).mappings()]
    dates = [r[0].isoformat() for r in db.execute(text(
        "SELECT DISTINCT snap_date FROM snapshots ORDER BY snap_date DESC"))]
    last = db.execute(text(
        "SELECT id, snap_date, finished_at, created_by FROM jobs WHERE status='done' "
        "ORDER BY id DESC LIMIT 1")).mappings().first()
    hb = db.execute(text("SELECT v FROM kv WHERE k='worker_heartbeat'")).scalar()
    bot = db.execute(text("SELECT v FROM kv WHERE k='tg_bot_username'")).scalar() or ""
    return {
        "user": user_out(user), "esps": esps, "brigades": brigades, "dates": dates,
        "last_upload": {"id": last["id"], "snap_date": last["snap_date"].isoformat(),
                        "finished_at": last["finished_at"].isoformat() if last["finished_at"] else None,
                        "by": last["created_by"]} if last else None,
        "bot_username": bot,
        "worker_alive": bool(hb and time.time() - int(hb) < 20),
        "presets": PRESETS, "region_name": app_cfg("region_name"),
        "perms": [{"code": c, "group": g, "name": n, "desc": d, "needs": nd} for c, g, n, d, nd in PERMS],
    }
