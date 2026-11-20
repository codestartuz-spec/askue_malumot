"""Bitta joyda aniqlangan ko'rsatkichlar. Xuddi shu SQL shartlari ham jadval yig'indisi uchun,
ham raqam ustiga bosilganda ochiladigan nomma-nom ro'yxat uchun ishlatiladi."""

# --- Konsentratorlar (trs jadvali) ---
TR_SPEC = {
    "tp_total": "1=1",
    "cas_loaded": "attached=1",
    "online": "attached=1 AND offline=0",
    "offline": "attached=1 AND offline=1",
    "offline3": "attached=1 AND offline3=1",
    "lv0": "lv=1",
    "lv1": "lv=2",
    "lv2": "lv=3",
    "lv3": "lv=4",
    "lv4": "lv=5",
    "unattached": "has_dcu=1 AND attached=0",
}

# --- Hisoblagichlar (meters jadvali) ---
# bucket: 0 = obxod vaqti yo'q, 1 = 0-2 kun, 2 = 2-7, 3 = 7-30, 4 = 30-90, 5 = 90+
# ctype: 1 = ulgurji (yuridik), 2 = aholi (maishiy), 3 = balans
METER_SPEC = {
    "m_total": "1=1",
    "m_conn": "bucket=1",
    "out_total": "bucket>=2",
    "out_aholi": "bucket>=2 AND ctype=2",
    "out_ulgurji": "bucket>=2 AND ctype=1",
    "out_balans": "bucket>=2 AND ctype=3",
    "out_2_7": "bucket=2",
    "out_7_30": "bucket=3",
    "out_30_90": "bucket=4",
    "out_90p": "bucket=5",
    "m_nopoll": "bucket=0",
    "m_direct": "direct=1",
    "polled": "bucket=1",
    "a_total": "ctype=2",
    "a_polled": "ctype=2 AND bucket=1",
    "u_total": "ctype=1",
    "u_polled": "ctype=1 AND bucket=1",
    "b_total": "ctype=3",
    "b_polled": "ctype=3 AND bucket=1",
}

TR_METRICS = list(TR_SPEC)
METER_METRICS = list(METER_SPEC)
ALL_METRICS = TR_METRICS + METER_METRICS


def agg_sql(spec: dict) -> str:
    return ", ".join(f"COALESCE(SUM({cond}),0) AS {name}" for name, cond in spec.items())
