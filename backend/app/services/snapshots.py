from datetime import date

from sqlalchemy import text

from ..metrics import ALL_METRICS, METER_SPEC, TR_SPEC, agg_sql


def compute(conn, esp_id: int | None = None) -> dict:
    where = "WHERE esp_id=:e" if esp_id else ""
    params = {"e": esp_id} if esp_id else {}
    res: dict[tuple[int, int], dict] = {}
    for table, spec in (("trs", TR_SPEC), ("meters", METER_SPEC)):
        sql = (f"SELECT esp_id, COALESCE(brigade_id,0) AS bid, {agg_sql(spec)} "
               f"FROM {table} {where} GROUP BY esp_id, bid")
        for row in conn.execute(text(sql), params).mappings():
            d = res.setdefault((row["esp_id"], row["bid"]), {m: 0 for m in ALL_METRICS})
            for name in spec:
                d[name] = int(row[name])
    return res


def write(conn, snap_date: date, esp_id: int | None = None) -> int:
    data = compute(conn, esp_id)
    if esp_id:
        conn.execute(text("DELETE FROM snapshots WHERE snap_date=:d AND esp_id=:e"),
                     {"d": snap_date, "e": esp_id})
    else:
        conn.execute(text("DELETE FROM snapshots WHERE snap_date=:d"), {"d": snap_date})
    rows = [{"snap_date": snap_date, "esp_id": e, "brigade_id": b, **vals}
            for (e, b), vals in data.items()]
    if rows:
        cols = ["snap_date", "esp_id", "brigade_id"] + ALL_METRICS
        conn.execute(text(
            f"INSERT INTO snapshots ({','.join(cols)}) VALUES ({','.join(':' + c for c in cols)})"), rows)
    return len(rows)
