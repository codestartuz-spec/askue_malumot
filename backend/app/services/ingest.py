"""Area va Details fayllarini bazaga sinxronlash.

Qoida: baza faylning oxirgi holatiga tenglashadi — mavjudlari yangilanadi, yangilari qo'shiladi,
faylda yo'qlari o'chiriladi. Brigada nomlari, xodimlar va qo'lda biriktirilgan TP'lar saqlanib qoladi.
"""
import csv
import gzip
import io
import json
import os
import re
from pathlib import Path

from sqlalchemy import text

from ..config import settings
from ..db import engine
from .staff import normalize_key, split_staff

csv.field_size_limit(10_000_000)

AREA_COLS = ["ESP Code", "ESP name", "Substation Code", "Substation", "Feeder Code", "Feeder",
             "TR Code", "TR", "Manager Name", "DCU No.", "Iste'molchi biriktirilgan",
             "Obxod darajasi", "Konsentrator holati", "Offline", "3 kundan ortiq offline",
             "Daily 0%", "Daily 1-30%", "Daily 30-50%", "Daily 50-80%", "Daily 80-100%"]
DETAILS_COLS = ["ЭСП", "ТП", "Лицевой счет потребителя", "Номер счетчика", "Тип счетчика",
                "Тип связи", "Тип потребителя", "Коэффициент Т/Т", "Коэффициент Т/Н", "широта",
                "долгота", "Статус оборудования", "Имя потребителя", "Адрес установки",
                "Oxirgi obxod vaqti", "Obxod kuni", "0-2 kun", "2-7 kun", "7-30 kun", "30-90 kun",
                "90+ kun", "DirectMeter"]

ESP_ORDER = ["Baxoriston", "G‘uzor", "Dehqonobod", "Qamashi", "Qarshi ShETK", "Qarshi TETK",
             "Koson", "Kasbi", "Kitob", "Mirishkor", "Muborak", "Nishon", "Chiroqchi",
             "Shahrisabz ShETK", "Shahrisabz TETK", "Yakkabog‘", "Ko‘kdala"]


class IngestError(Exception):
    pass


def esp_label(name: str) -> str:
    m = re.match(r"^(.*?)\s+(TETK|ShETK)$", name.strip())
    if m:
        return m.group(1) + (" t." if m.group(2) == "TETK" else " sh.")
    return name.strip()


def esp_sort(name: str) -> int:
    for i, p in enumerate(ESP_ORDER):
        if name.startswith(p):
            return i
    return 500


class _Capped(io.RawIOBase):
    """gzip oqimidan o'qilgan hajmni cheklaydi (gzip-bomba himoyasi)."""

    def __init__(self, inner, limit: int):
        self.inner, self.limit, self.n = inner, limit, 0

    def readable(self):
        return True

    def readinto(self, b):
        data = self.inner.read(len(b))
        self.n += len(data)
        if self.n > self.limit:
            raise IngestError(f"Fayl ochilgach juda katta (>{self.limit // 1048576} MB) — qabul qilinmadi")
        b[:len(data)] = data
        return len(data)


def open_csv(path: str):
    """CSV/CSV.GZ ni oqim bilan o'qiydi (butun fayl xotiraga yuklanmaydi)."""
    raw = open(path, "rb")
    if path.lower().endswith(".gz"):
        stream = io.BufferedReader(_Capped(gzip.GzipFile(fileobj=raw), settings.max_unzipped_mb * 1048576), 1 << 20)
    else:
        stream = raw
    return raw, csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))


def resolve(header: list[str], expected: list[str], what: str) -> list[int]:
    h = [x.strip() for x in header]
    if all(c in h for c in expected):
        return [h.index(c) for c in expected]
    if len(h) == len(expected):  # til o'zgargan bo'lsa ham ustunlar tartibi bir xil
        return list(range(len(h)))
    raise IngestError(f"{what} faylidagi ustunlar kutilganidek emas ({len(h)} ta ustun topildi)")


def _num(v, cast=float):
    try:
        return cast(v) if v not in ("", None) else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- AREA
def ingest_area(path: str, batch: int, progress) -> dict:
    raw, rd = open_csv(path)
    with raw:
        idx = resolve(next(rd), AREA_COLS, "Area")
        rows = [[r[i].strip() if i < len(r) else "" for i in idx] for r in rd if r]
    if not rows:
        raise IngestError("Area faylida ma'lumot topilmadi")
    progress(0.3, "Area: tumanlar va brigadalar")

    with engine.begin() as conn:
        existing_trs = conn.execute(text("SELECT COUNT(*) FROM trs")).scalar() or 0
        if existing_trs > 1000 and len(rows) < existing_trs * 0.5:
            raise IngestError(f"Area fayli to'liq emas ko'rinadi: {len(rows)} qator "
                              f"(bazada {existing_trs} ta TP bor). Ma'lumot o'chirilmadi.")

        esps = {r[1]: r[0] for r in conn.execute(text("SELECT id,name FROM esps"))}
        for r in rows:
            name = r[1]
            if name and name not in esps:
                res = conn.execute(text(
                    "INSERT INTO esps (name, code, label, sort) VALUES (:n,:c,:l,:s)"),
                    {"n": name, "c": r[0], "l": esp_label(name), "s": esp_sort(name)})
                esps[name] = res.lastrowid

        brig = {(r[1], r[2]): r[0] for r in conn.execute(
            text("SELECT id, esp_id, manager_key FROM brigades"))}      # (esp_id, kalit) -> id
        max_no = {r[0]: r[1] for r in conn.execute(
            text("SELECT esp_id, MAX(number) FROM brigades GROUP BY esp_id"))}
        new_brigades = 0
        for r in rows:
            eid, mk = esps.get(r[1]), normalize_key(r[8])
            if not eid or not mk or (eid, mk) in brig:
                continue
            n = max_no.get(eid, 0) + 1
            max_no[eid] = n
            res = conn.execute(text(
                "INSERT INTO brigades (esp_id, manager_key, number, name, source_name) "
                "VALUES (:e,:k,:n,:nm,:s)"),
                {"e": eid, "k": mk, "n": n, "nm": f"{n}-brigada", "s": r[8][:500]})
            bid = res.lastrowid
            brig[(eid, mk)] = bid
            members = [{"b": bid, "n": nm[:150], "s": i} for i, nm in enumerate(split_staff(r[8]))]
            if members:
                conn.execute(text("INSERT INTO brigade_members (brigade_id, full_name, sort) "
                                  "VALUES (:b,:n,:s)"), members)
            new_brigades += 1

        existing = {(r[0], r[1]): (r[2], r[3], r[4], r[5]) for r in conn.execute(text(
            "SELECT esp_id, tr_code, id, brigade_id, manual, file_key FROM trs"))}

        params = []
        moved = 0
        for r in rows:
            eid = esps.get(r[1])
            if not eid:
                continue
            tr_code = r[6]
            mk = normalize_key(r[8])
            file_brig = brig.get((eid, mk)) if mk else None
            ex = existing.get((eid, tr_code))
            if ex is None:
                brigade_id, manual, fkey = file_brig, 0, mk
            else:
                _, cur_b, manual, fkey = ex
                brigade_id = cur_b
                if not manual and mk != fkey:       # faylda menejer o'zgargan va qo'lda tegilmagan
                    brigade_id = file_brig
                    moved += 1
                fkey = mk
            lv = 0
            for i, col in enumerate(range(15, 20), start=1):
                if r[col] == "1":
                    lv = i
                    break
            holati = r[12].lower()
            params.append((
                eid, tr_code, r[7][:80], r[3][:150], r[5][:150], r[9] or None, fkey, brigade_id,
                1 if r[9] else 0, 1 if r[10] == "1" else 0, 1 if r[13] == "1" else 0,
                1 if r[14] == "1" else 0, lv, _num(r[11]),
                1 if holati == "online" else 2 if holati == "offline" else 0, batch, int(manual or 0)))
        cols = ("esp_id,tr_code,tp_no,substation,feeder,dcu,file_key,brigade_id,has_dcu,attached,"
                "offline,offline3,lv,obx_level,state,batch,manual")
        upd = ",".join(f"{c}=VALUES({c})" for c in cols.split(",") if c not in ("esp_id", "tr_code", "manual"))
        sql = (f"INSERT INTO trs ({cols}) VALUES ({','.join(['%s'] * 17)}) "
               f"ON DUPLICATE KEY UPDATE {upd}")
        raw_conn = conn.connection
        cur = raw_conn.cursor()
        for i in range(0, len(params), 3000):
            cur.executemany(sql, params[i:i + 3000])
            progress(0.3 + 0.6 * min(1, (i + 3000) / len(params)), "Area: TP va konsentratorlar")
        removed = conn.execute(text("DELETE FROM trs WHERE batch<>:b"), {"b": batch}).rowcount
    return {"area_rows": len(rows), "new_brigades": new_brigades, "tp_removed": removed,
            "tp_brigade_changed": moved}


# ---------------------------------------------------------------- DETAILS
_METER_COLS = ("meter_no,esp_id,tp_no,tr_id,brigade_id,account,mtype,link,ctype,status,name,address,"
               "lat,lon,last_poll,days,bucket,direct,batch")
_METER_SQL = (f"INSERT INTO meters ({_METER_COLS}) VALUES ({','.join(['%s'] * 19)}) ON DUPLICATE KEY UPDATE "
              + ",".join(f"{c}=VALUES({c})" for c in _METER_COLS.split(",") if c != "meter_no"))


def details_parts(path: str) -> list[str]:
    """path - bitta CSV(.gz) yoki bo'laklar papkasi (001.csv.gz, 002.csv.gz ...) -> o'qiladigan fayllar tartibda."""
    p = Path(path)
    if p.is_dir():
        files = sorted(str(f) for f in p.iterdir() if f.is_file() and f.name.lower().endswith((".csv.gz", ".csv")))
        if not files:
            raise IngestError("Details bo'laklari topilmadi")
        return files
    return [path]


def _expected_rows(path: str) -> int | None:
    """Bo'laklar papkasidagi manifest.json (yoki ota papkadagi) bo'yicha kutilgan qatorlar soni."""
    p = Path(path)
    if not p.is_dir():
        return None
    for cand in (p / "manifest.json", p.parent / "manifest.json"):
        if cand.is_file():
            try:
                return int(json.loads(cand.read_text(encoding="utf-8"))["rows_total"])
            except (OSError, ValueError, KeyError, TypeError):
                return None
    return None


def ingest_details(path: str, batch: int, progress) -> dict:
    parts = details_parts(path)
    size = max(sum(os.path.getsize(f) for f in parts), 1)
    expected = _expected_rows(path)
    done_bytes = 0
    with engine.begin() as conn:
        esps = {r[1]: r[0] for r in conn.execute(text("SELECT id,name FROM esps"))}
        trmap = {}
        for r in conn.execute(text("SELECT id, esp_id, tp_no, brigade_id FROM trs ORDER BY id DESC")):
            trmap[(r[1], r[2])] = (r[0], r[3])          # id bo'yicha kamayish: birinchisi yutadi
        existing = conn.execute(text("SELECT COUNT(*) FROM meters")).scalar() or 0

    total = 0
    unmatched = 0
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        for part in parts:
            raw, rd = open_csv(part)
            with raw:
                try:
                    header = next(rd)
                except StopIteration:
                    raise IngestError(f"{os.path.basename(part)}: fayl bo'sh")
                idx = resolve(header, DETAILS_COLS, "Details")
                (i_esp, i_tp, i_acc, i_no, i_mt, i_link, i_ct, _, _, i_lat, i_lon, i_st, i_name,
                 i_addr, i_lp, i_days, b1, b2, b3, b4, b5, i_dir) = idx
                buf = []
                for r in rd:
                    if len(r) <= max(idx):
                        continue
                    no = r[i_no].strip()
                    if not no:
                        continue
                    en = r[i_esp].strip()
                    eid = esps.get(en)
                    if eid is None:
                        cur.execute("INSERT INTO esps (name, code, label, sort) VALUES (%s,'',%s,%s)",
                                    (en, esp_label(en), esp_sort(en)))
                        eid = esps[en] = cur.lastrowid
                    tp = r[i_tp].strip()[:80]
                    tr_id, brig = trmap.get((eid, tp), (None, None))
                    if tr_id is None:
                        unmatched += 1
                    bucket = (1 if r[b1] == "1" else 2 if r[b2] == "1" else 3 if r[b3] == "1"
                              else 4 if r[b4] == "1" else 5 if r[b5] == "1" else 0)
                    lp = r[i_lp].strip()
                    buf.append((
                        no, eid, tp, tr_id, brig, r[i_acc].strip()[:24], r[i_mt].strip()[:24],
                        r[i_link].strip()[:8], _num(r[i_ct], int) or 0, _num(r[i_st], int) or 0,
                        r[i_name].strip()[:200], r[i_addr].strip()[:250], _num(r[i_lat]), _num(r[i_lon]),
                        lp if len(lp) >= 10 else None, _num(r[i_days], int), bucket,
                        1 if r[i_dir].strip() == "1" else 0, batch))
                    total += 1
                    if len(buf) >= 4000:
                        cur.executemany(_METER_SQL, buf)
                        raw_conn.commit()
                        buf = []
                        progress(min(0.99, (done_bytes + raw.tell()) / size), f"Hisoblagichlar: {total:,}".replace(",", " "))
                if buf:
                    cur.executemany(_METER_SQL, buf)
                    raw_conn.commit()
            done_bytes += os.path.getsize(part)
        if total == 0:
            raise IngestError("Details faylida ma'lumot topilmadi")
        if expected is not None and total != expected:
            raise IngestError(f"Details bo'laklaridagi qatorlar soni manifestga mos emas: {total} ta o'qildi, "
                              f"manifestda {expected} ta. Eski ma'lumot o'chirilmadi.")
        if existing > 10000 and total < existing * 0.5:
            raise IngestError(f"Details fayli to'liq emas ko'rinadi: {total} ta hisoblagich "
                              f"(bazada {existing} ta bor). Eskilari o'chirilmadi.")
        cur.execute("DELETE FROM meters WHERE batch<>%s", (batch,))
        removed = cur.rowcount
        raw_conn.commit()
    finally:
        raw_conn.close()
    return {"meters": total, "meters_removed": removed, "meters_without_tp": unmatched}


def remap_meters() -> None:
    """Area o'zgarib, Details yuklanmagan holatda hisoblagichlarni TP/brigadaga qayta bog'lash."""
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE meters m LEFT JOIN trs t ON t.esp_id=m.esp_id AND t.tp_no=m.tp_no "
            "SET m.tr_id=t.id, m.brigade_id=t.brigade_id"))
