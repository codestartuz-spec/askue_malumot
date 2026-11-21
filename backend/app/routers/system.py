import os
import platform
import re
import shutil
import sys
import time
from datetime import datetime

import psutil
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import log, need
from ..models import Backup, User
from ..services import backup as B
from ..services import telegram as tg

router = APIRouter(prefix="/system", tags=["system"])
_PROC_START = time.time()
_tg_cache: dict = {"t": 0, "v": None}


def _kv(db: Session, k: str):
    return db.execute(text("SELECT v FROM kv WHERE k=:k"), {"k": k}).scalar()


def _age(ts) -> float | None:
    try:
        return round(time.time() - int(ts), 1)
    except (TypeError, ValueError):
        return None


def _fmt_dur(sec: float) -> str:
    sec = int(sec)
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    return (f"{d} kun " if d else "") + f"{h} soat {m} daqiqa"


def _tg_check() -> dict:
    if time.time() - _tg_cache["t"] < 25 and _tg_cache["v"]:
        return _tg_cache["v"]
    if not tg.get_token():
        v = {"state": "warn", "text": "Bot ulanmagan", "ms": None}
    else:
        t0 = time.time()
        try:
            me = tg.call("getMe", timeout=8, retries=1)
            v = {"state": "ok", "text": f"@{me.get('username')} — Telegram'ga ulanish bor", "ms": round((time.time() - t0) * 1000)}
        except tg.TgError as e:
            v = {"state": "bad", "text": "Telegram'ga ulanib bo'lmadi", "ms": None, "err": str(e)}
    _tg_cache.update(t=time.time(), v=v)
    return v


@router.get("/status")
def status(_: User = Depends(need("system.view")), db: Session = Depends(get_db)):
    checks = []

    def add(key, title, state, value, detail=""):
        checks.append({"key": key, "title": title, "state": state, "value": value, "detail": detail})

    # 1. Ma'lumotlar bazasi
    t0 = time.time()
    db.execute(text("SELECT 1"))
    ping = round((time.time() - t0) * 1000, 1)
    ver = db.execute(text("SELECT VERSION()")).scalar()
    size = db.execute(text("SELECT COALESCE(SUM(data_length+index_length),0) FROM information_schema.tables WHERE table_schema=DATABASE()")).scalar()
    add("db", "Ma'lumotlar bazasi (MySQL)", "ok" if ping < 200 else "warn", f"Ulangan • {ping} ms",
        f"Versiya {ver} • hajmi {round(float(size) / 1048576)} MB")
    # 2. Worker
    age = _age(_kv(db, "worker_heartbeat"))
    queued = db.execute(text("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')")).scalar()
    if age is None:
        add("worker", "Yuklash jarayoni (worker)", "bad", "Ishga tushmagan", "python -m app.worker ni ishga tushiring")
    elif age > 30:
        add("worker", "Yuklash jarayoni (worker)", "bad", f"Javob bermayapti ({int(age)} s)", "worker to'xtab qolgan bo'lishi mumkin")
    else:
        add("worker", "Yuklash jarayoni (worker)", "ok", "Ishlayapti", f"Navbatda/bajarilmoqda: {queued} ta ish")
    # 3. Telegram
    hb = _age(_kv(db, "tg_poll_hb"))
    tgc = _tg_check()
    add("tg", "Telegram bot", tgc["state"], tgc["text"] + (f" • {tgc['ms']} ms" if tgc["ms"] else ""),
        ((tgc.get("err", "") + " • " if tgc.get("err") else "") + "Bot buyruqlarini tinglash: " + ("faol" if hb is not None and hb < 60 else "faol emas (worker kerak)")) if tgc["state"] != "warn" else "")
    # 4. Oxirgi ma'lumot
    last = db.execute(text("SELECT MAX(snap_date) FROM snapshots")).scalar()
    cnt = db.execute(text("SELECT COUNT(DISTINCT snap_date) FROM snapshots")).scalar()
    if last:
        days = (datetime.now().date() - last).days
        add("data", "Ma'lumotlar yangiligi", "ok" if days <= 1 else "warn" if days <= 3 else "bad",
            f"Oxirgisi: {last:%d.%m.%Y}", f"{days} kun oldin • jami {cnt} ta sana")
    else:
        add("data", "Ma'lumotlar yangiligi", "warn", "Hali ma'lumot yuklanmagan")
    # 5. Zaxira
    lb = db.scalar(select(Backup).where(Backup.status == "ok").order_by(Backup.id.desc()))
    cfg = B.settings_get()
    if not cfg["enabled"]:
        add("backup", "Zaxira nusxa", "warn", "Avtomatik o'chirilgan", "Sozlamalar → Zaxira nusxa")
    elif lb:
        h = (datetime.now() - lb.created_at).total_seconds() / 3600
        add("backup", "Zaxira nusxa", "ok" if h < 30 else "warn", f"Oxirgisi: {lb.created_at:%d.%m.%Y %H:%M}",
            f"Har kuni {cfg['time']} da • Telegram'ga {'yuborilgan' if lb.sent else 'yuborilmagan'}")
    else:
        add("backup", "Zaxira nusxa", "warn", "Hali nusxa olinmagan", f"Har kuni {cfg['time']} da avtomatik olinadi")
    # 6. Server
    vm = psutil.virtual_memory()
    try:
        du = shutil.disk_usage(settings.data_dir)
        dpct = round(100 * du.used / du.total, 1)
    except OSError:
        du, dpct = None, None
    cpu = psutil.cpu_percent(interval=0.25)
    add("cpu", "Protsessor (CPU)", "ok" if cpu < 80 else "warn" if cpu < 95 else "bad", f"{cpu}%",
        f"{psutil.cpu_count()} yadro")
    add("ram", "Operativ xotira (RAM)", "ok" if vm.percent < 85 else "warn" if vm.percent < 95 else "bad",
        f"{vm.percent}%", f"{round(vm.used / 1073741824, 1)} / {round(vm.total / 1073741824, 1)} GB")
    if du:
        add("disk", "Disk (ma'lumotlar joylashgan)", "ok" if dpct < 85 else "warn" if dpct < 95 else "bad", f"{dpct}%",
            f"Bo'sh {round(du.free / 1073741824, 1)} GB / {round(du.total / 1073741824, 1)} GB")
    bad = sum(c["state"] == "bad" for c in checks)
    warn = sum(c["state"] == "warn" for c in checks)
    proc = psutil.Process(os.getpid())
    return {
        "overall": "bad" if bad else "warn" if warn else "ok",
        "checks": checks,
        "server": {"os": f"{platform.system()} {platform.release()}", "python": sys.version.split()[0],
                   "host": platform.node(), "uptime": _fmt_dur(time.time() - psutil.boot_time()),
                   "app_uptime": _fmt_dur(time.time() - _PROC_START), "api_mem_mb": round(proc.memory_info().rss / 1048576),
                   "time": datetime.now().strftime("%d.%m.%Y %H:%M:%S")},
        "stats": {"meters": db.execute(text("SELECT COUNT(*) FROM meters")).scalar(),
                  "trs": db.execute(text("SELECT COUNT(*) FROM trs")).scalar(),
                  "users": db.execute(text("SELECT COUNT(*) FROM users WHERE is_active=1")).scalar()},
    }


# ---------------- Zaxira nusxa ----------------
def _b_out(b: Backup) -> dict:
    return {"id": b.id, "at": b.created_at.isoformat(), "kind": b.kind, "filename": b.filename, "size": b.size,
            "status": b.status, "sent": b.sent, "note": b.note,
            "exists": (B._bdir() / b.filename).exists()}


@router.get("/backups")
def backups(_: User = Depends(need("backup.manage")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Backup).order_by(Backup.id.desc()).limit(60))
    chats = B.sadmin_chats()
    return {"settings": B.settings_get(), "items": [_b_out(b) for b in rows], "sadmin_chat": bool(chats),
            "bot": bool(tg.get_token())}


class BSet(BaseModel):
    enabled: bool = True
    time: str = "01:00"
    keep: int = 14


@router.put("/backups/settings")
def set_backup(body: BSet, user: User = Depends(need("backup.manage")), db: Session = Depends(get_db)):
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", body.time):
        raise HTTPException(400, "Vaqtni SS:DD ko'rinishida kiriting (masalan 01:00)")
    if not 1 <= body.keep <= 90:
        raise HTTPException(400, "Saqlanadigan nusxalar soni 1 dan 90 gacha bo'lsin")
    B._set("backup_enabled", "1" if body.enabled else "0")
    B._set("backup_time", body.time)
    B._set("backup_keep", str(body.keep))
    log(db, user.username, "zaxira_sozlama", f"{'yoqilgan' if body.enabled else 'oʻchirilgan'} {body.time}, {body.keep} ta")
    db.commit()
    return B.settings_get()


@router.post("/backups/run")
def run(user: User = Depends(need("backup.manage")), db: Session = Depends(get_db)):
    r = B.run_backup("manual")
    log(db, user.username, "zaxira_qolda", r["filename"])
    db.commit()
    if r["status"] != "ok":
        raise HTTPException(500, r["note"] or "Zaxira nusxa olinmadi")
    return r


def _get(db: Session, bid: int) -> Backup:
    b = db.get(Backup, bid)
    if not b:
        raise HTTPException(404, "Topilmadi")
    return b


@router.get("/backups/{bid}/download")
def b_download(bid: int, _: User = Depends(need("backup.manage")), db: Session = Depends(get_db)):
    b = _get(db, bid)
    p = B._bdir() / b.filename
    if not p.exists():
        raise HTTPException(404, "Fayl serverda topilmadi")
    return FileResponse(p, filename=b.filename, media_type="application/octet-stream")


@router.post("/backups/{bid}/send")
def b_send(bid: int, user: User = Depends(need("backup.manage")), db: Session = Depends(get_db)):
    b = _get(db, bid)
    p = B._bdir() / b.filename
    if not p.exists():
        raise HTTPException(404, "Fayl serverda topilmadi")
    ok, note = B.send_to_sadmin(b.filename, p.read_bytes(), "manual")
    if not ok:
        raise HTTPException(400, note or "Yuborilmadi")
    b.sent = True
    db.commit()
    return {"ok": True}


@router.delete("/backups/{bid}")
def b_delete(bid: int, user: User = Depends(need("backup.manage")), db: Session = Depends(get_db)):
    b = _get(db, bid)
    (B._bdir() / b.filename).unlink(missing_ok=True)
    log(db, user.username, "zaxira_ochirish", b.filename)
    db.delete(b)
    db.commit()
    return {"ok": True}
