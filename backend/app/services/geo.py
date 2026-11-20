"""Konsentrator (TP) koordinatasi: unga biriktirilgan hisoblagichlar koordinatalarining markazi.
Chetga chiqib ketgan (noto'g'ri kiritilgan) nuqtalar ikkinchi o'tishda hisobga olinmaydi."""
from sqlalchemy import text

# Qashqadaryo viloyati atrofidagi mantiqiy chegara — undan tashqaridagi nuqtalar xato hisoblanadi
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 37.0, 40.5, 63.0, 69.0


def compute_tr_geo(conn) -> int:
    conn.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_geo1"))
    conn.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_geo2"))
    conn.execute(text(
        "CREATE TEMPORARY TABLE tmp_geo1 (tr_id INT PRIMARY KEY, lat DOUBLE, lon DOUBLE) "
        "SELECT tr_id, AVG(lat) AS lat, AVG(lon) AS lon FROM meters "
        "WHERE tr_id IS NOT NULL AND lat BETWEEN :a AND :b AND lon BETWEEN :c AND :d GROUP BY tr_id"),
        {"a": LAT_MIN, "b": LAT_MAX, "c": LON_MIN, "d": LON_MAX})
    conn.execute(text(
        "CREATE TEMPORARY TABLE tmp_geo2 (tr_id INT PRIMARY KEY, lat DOUBLE, lon DOUBLE) "
        "SELECT m.tr_id, AVG(m.lat) AS lat, AVG(m.lon) AS lon FROM meters m "
        "JOIN tmp_geo1 g ON g.tr_id=m.tr_id "
        "WHERE m.lat IS NOT NULL AND ABS(m.lat-g.lat)<0.02 AND ABS(m.lon-g.lon)<0.02 GROUP BY m.tr_id"))
    conn.execute(text("UPDATE trs SET lat=NULL, lon=NULL WHERE lat IS NOT NULL"))
    n = conn.execute(text("UPDATE trs t JOIN tmp_geo2 g ON g.tr_id=t.id SET t.lat=g.lat, t.lon=g.lon")).rowcount
    # tuzatish: ikkinchi o'tishda hech narsa qolmagan TP'lar uchun birinchi o'tish natijasi
    n += conn.execute(text("UPDATE trs t JOIN tmp_geo1 g ON g.tr_id=t.id SET t.lat=g.lat, t.lon=g.lon "
                           "WHERE t.lat IS NULL")).rowcount
    conn.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_geo1"))
    conn.execute(text("DROP TEMPORARY TABLE IF EXISTS tmp_geo2"))
    return n
