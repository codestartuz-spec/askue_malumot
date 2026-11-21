import os
import threading
import time
import traceback
from datetime import datetime

from sqlalchemy import text

from ..db import engine, upsert_kv
from . import geo, snapshots
from .ingest import IngestError, ingest_area, ingest_details, remap_meters


def set_kv(k: str, v: str) -> None:
    with engine.begin() as c:
        upsert_kv(c, k, v)


def heartbeat_loop() -> None:
    while True:
        try:
            set_kv("worker_heartbeat", str(int(time.time())))
        except Exception:
            pass
        time.sleep(5)


def start_heartbeat() -> None:
    threading.Thread(target=heartbeat_loop, daemon=True).start()


class Progress:
    def __init__(self, job_id: int):
        self.job_id, self.last_t, self.last_p = job_id, 0.0, -1.0
        self.lo, self.hi = 0.0, 1.0

    def window(self, lo: float, hi: float):
        self.lo, self.hi = lo, hi

    def __call__(self, frac: float, stage: str, force: bool = False):
        pct = round(100 * (self.lo + (self.hi - self.lo) * min(max(frac, 0), 1)), 1)
        now = time.time()
        if not force and (now - self.last_t < 1.0 or abs(pct - self.last_p) < 0.4):
            return
        self.last_t, self.last_p = now, pct
        with engine.begin() as c:
            c.execute(text("UPDATE jobs SET progress=:p, stage=:s WHERE id=:i"),
                      {"p": pct, "s": stage[:190], "i": self.job_id})


def run_job(job_id: int) -> None:
    with engine.begin() as c:
        job = c.execute(text("SELECT * FROM jobs WHERE id=:i"), {"i": job_id}).mappings().one()
        c.execute(text("UPDATE jobs SET status='running', started_at=:t, progress=0, "
                       "stage='Boshlanmoqda' WHERE id=:i"), {"t": datetime.now(), "i": job_id})
    prog = Progress(job_id)
    stats: dict = {}
    try:
        has_area, has_det = bool(job["area_path"]), bool(job["details_path"])
        if has_area:
            prog.window(0.0, 0.08 if has_det else 0.8)
            stats.update(ingest_area(job["area_path"], job_id, prog))
        if has_det:
            prog.window(0.08 if has_area else 0.0, 0.88)
            stats.update(ingest_details(job["details_path"], job_id, prog))
        elif has_area:
            prog.window(0.8, 0.9)
            prog(0.0, "Hisoblagichlar brigadalarga bog'lanmoqda", True)
            remap_meters()
        prog.window(0.88, 1.0)
        prog(0.05, "Konsentratorlar koordinatalari hisoblanmoqda", True)
        with engine.begin() as c:
            stats["tp_geo"] = geo.compute_tr_geo(c)
        prog(0.4, "Kunlik dinamika saqlanmoqda", True)
        with engine.begin() as c:
            stats["snapshot_rows"] = snapshots.write(c, job["snap_date"])
        stats["snap_date"] = str(job["snap_date"])
        with engine.begin() as c:
            c.execute(text("UPDATE jobs SET status='done', progress=100, stage='Tayyor', stats=:s, "
                           "finished_at=:t WHERE id=:i"),
                      {"s": __import__("json").dumps(stats), "t": datetime.now(), "i": job_id})
            c.execute(text("INSERT INTO audit (username, action, detail, created_at) "
                           "VALUES (:u,'upload',:d,:t)"),
                      {"u": job["created_by"], "t": datetime.now(),
                       "d": f"Yuklash #{job_id} ({job['snap_date']}): {stats}"})
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        msg = str(e) if isinstance(e, IngestError) else f"{type(e).__name__}: {e}"
        with engine.begin() as c:
            c.execute(text("UPDATE jobs SET status='error', stage='Xatolik', message=:m, "
                           "finished_at=:t WHERE id=:i"),
                      {"m": msg[:1500], "t": datetime.now(), "i": job_id})
    finally:
        for p in (job["area_path"], job["details_path"]):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
