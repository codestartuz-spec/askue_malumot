"""Alohida jarayon: yuklash navbatidagi ishlarni ketma-ket bajaradi.
Ishga tushirish:  python -m app.worker"""
import time
from datetime import datetime

from sqlalchemy import text

from .db import engine
from .init_db import init_db
from .services.backup import start_scheduler
from .services.jobs import run_job, start_heartbeat
from .services.telegram import start_polling


def claim() -> int | None:
    with engine.begin() as c:
        row = c.execute(text("SELECT id FROM jobs WHERE status='queued' ORDER BY id LIMIT 1")).first()
        return row[0] if row else None


def main() -> None:
    init_db()
    with engine.begin() as c:   # oldingi ish o'rtasida to'xtab qolgan bo'lsa
        c.execute(text("UPDATE jobs SET status='error', stage='Xatolik', "
                       "message='Jarayon to''xtatilgan (worker qayta ishga tushdi)', finished_at=:t "
                       "WHERE status='running'"), {"t": datetime.now()})
    try:   # TP koordinatalari hisoblanmagan bo'lsa (masalan, eski yuklashdan keyin) — hisoblab qo'yamiz
        from sqlalchemy import text as _t
        from .services import geo
        with engine.begin() as c:
            has_tr = c.execute(_t("SELECT 1 FROM trs WHERE lat IS NOT NULL LIMIT 1")).first()
            has_m = c.execute(_t("SELECT 1 FROM meters WHERE lat IS NOT NULL LIMIT 1")).first()
            if has_m and not has_tr:
                print("TP koordinatalari hisoblanmoqda:", geo.compute_tr_geo(c), flush=True)
    except Exception as e:  # noqa: BLE001
        print("TP koordinatalarini hisoblashda xato:", e, flush=True)
    start_heartbeat()
    start_polling()
    start_scheduler()
    print("Worker ishga tushdi. Navbat kutilmoqda...", flush=True)
    while True:
        job_id = claim()
        if job_id:
            print(f"Ish #{job_id} boshlandi", flush=True)
            run_job(job_id)
            print(f"Ish #{job_id} tugadi", flush=True)
        else:
            time.sleep(2)


if __name__ == "__main__":
    main()
