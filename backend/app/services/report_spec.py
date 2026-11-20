"""Uch dinamika jadvalining tuzilishi (hisobotlar uchun). Frontend'dagi tables.js bilan bir xil."""
n = lambda m, cls="": ("n", m, cls)                    # noqa: E731
d = lambda m, pol: ("d", m, pol)                       # noqa: E731
t = lambda m: ("t", m)                                  # noqa: E731
p = lambda a, b: ("p", a, b)                           # noqa: E731
H = lambda label, rs=1, cs=1, c="": (label, rs, cs, c)  # noqa: E731

_ARR = H("↑↓", c="arr")

TABLES = {
    "konsentrator": {
        "title": "hududida CAS dasturida mavjud konsentratorlar holati bo'yicha",
        "short": "Konsentratorlar",
        "head": [
            [H("Hudud nomi", 3, 1), H("Dasturda mavjud transformatorlar soni", 3, 1, "vert"),
             H("Konsentratorlar", 1, 5), H("Konsentratorlarning obxod olish darajasi bo'yicha soni", 1, 10),
             H("Iste'molchi biriktirilmagan konsentratorlar soni", 3, 1, "vert red")],
            [H("CAS ga yuklangan", 2, 1, "vert"), H("shundan", 1, 4, "it"), H("0%", 1, 2), H("1-30%", 1, 2),
             H("30-50%", 1, 2), H("50-80%", 1, 2), H("80-100%", 1, 2)],
            [H("Online", c="green s"), H("Offline (jami)", c="red s"), H("shundan 3 kundan ortiq", c="red s"), _ARR]
            + [x for _ in range(5) for x in (H("soni", c="red s"), _ARR)],
        ],
        "cols": [n("tp_total", "b"), n("cas_loaded", "b"), n("online", "green"), n("offline", "red"),
                 n("offline3", "red"), d("offline", "bad"),
                 n("lv0", "red"), d("lv0", "bad"), n("lv1", "red"), d("lv1", "bad"), n("lv2", "red"), d("lv2", "bad"),
                 n("lv3", "red"), d("lv3", "mid"), n("lv4", "b"), d("lv4", "good"), n("unattached", "red")],
    },
    "aloqa": {
        "title": "hududida CAS dasturida aloqaga chiqmagan hisoblagichlar bo'yicha",
        "short": "Aloqadan chiqib ketgan hisoblagichlar",
        "head": [
            [H("Hudud nomi", 4, 1),
             H("Aloqaga chiqmay qolgan hisoblagichlar soni", 1, 17, "red"),
             H("Umuman aloqaga chiqmagan hisoblagichlar", 2, 2, "red"),
             H("To'g'ridan-to'g'ri ulanish (peremichka)", 2, 2, "purple")],
            [H("Jami", 1, 3), H("Iste'molchi turi kesimida", 1, 6, "it"), H("Vaqtlar kesimida", 1, 8, "it")],
            [H("soni", 2, 1, "red s"), H("%", 2, 1, "s"), H("↑↓", 2, 1, "arr"), H("Aholi", 1, 2, "green"),
             H("Ulgurji", 1, 2, "blue"), H("Balans", 1, 2, "amber"), H("2-7 kun", 1, 2), H("7-30 kun", 1, 2),
             H("1-3 oy", 1, 2), H("3 oydan ortiq", 1, 2),
             H("soni", 2, 1, "red s"), H("↑↓", 2, 1, "arr"), H("soni", 2, 1, "s"), H("↑↓", 2, 1, "arr")],
            [x for _ in range(7) for x in (H("soni", c="red s"), _ARR)],
        ],
        "cols": [n("out_total", "red b"), p("out_total", "m_total"), d("out_total", "bad"),
                 n("out_aholi", "b"), d("out_aholi", "bad"), n("out_ulgurji", "b"), d("out_ulgurji", "bad"),
                 n("out_balans", "amber"), d("out_balans", "bad"), n("out_2_7", "b"), d("out_2_7", "bad"),
                 n("out_7_30", "b"), d("out_7_30", "bad"), n("out_30_90", "b"), d("out_30_90", "bad"),
                 n("out_90p", "b"), d("out_90p", "bad"), n("m_nopoll", "red"), d("m_nopoll", "bad"),
                 n("m_direct", "purple b"), d("m_direct", "bad")],
    },
    "obxod": {
        "title": "hududida 48 soat ichida obxod bergan hisoblagichlar bo'yicha",
        "short": "48 soat obxod",
        "head": [
            [H("Hudud nomi", 3, 1), H("Jami hisoblagichlar", 2, 4), H("shundan", 1, 12, "it")],
            [H("Aholi iste'molchilari", 1, 4, "green"), H("Ulgurji iste'molchilar", 1, 4, "amber"),
             H("Balans hisoblagichlar", 1, 4, "purple")],
            [H("Jami soni", c="s"), H("shundan obxod olgan", c="green s"), H("%", c="s"), _ARR] * 4,
        ],
        "cols": [n("m_total", "b"), n("polled", "b"), p("polled", "m_total"), d("polled", "mid"),
                 n("a_total"), n("a_polled", "b"), p("a_polled", "a_total"), d("a_polled", "mid"),
                 n("u_total"), n("u_polled", "b"), p("u_polled", "u_total"), d("u_polled", "mid"),
                 n("b_total"), n("b_polled", "b"), p("b_polled", "b_total"), d("b_polled", "mid")],
    },
}

# ----------------------------------------------------------------------------------------------
# Respublika dinamikasi: PDF'ning 1,2,3,4,6,7,8-sahifalari. Ustun kalitlari: c<i> — PDF katagi tartib raqami,
# t<i> — shu katakdagi matn (foiz). Faqat «Jami» (viloyat) qatori ko'rsatiladi.
_S4 = lambda k: [x for _ in range(k) for x in (H("soni", c="red s"), _ARR)]   # noqa: E731
_T = "hududida"
REPUBLIC = {
    1: ("r1", "Konsentratorlar"),
    2: ("r2", "Aloqaga chiqmagan"),
    3: ("r3", "Tarmoqdan uzilgan"),
    4: ("r4", "Balans va yuklama"),
    6: ("r6", "48 soat obxod"),
    7: ("r7", "Balans tafovuti"),
    8: ("r8", "Billing va CAS"),
}
TABLES["r1"] = {**TABLES["konsentrator"], "short": "Konsentratorlar", "cols": [
    n("c0", "b"), n("c1", "b"), n("c2", "green"), n("c3", "red"), n("c4", "red"), d("c4", "bad"),
    n("c5", "red"), d("c5", "bad"), n("c6", "red"), d("c6", "bad"), n("c7", "red"), d("c7", "bad"),
    n("c8", "red"), d("c8", "mid"), n("c9", "b"), d("c9", "good"), n("c10", "red")]}
TABLES["r2"] = {
    "title": "hududida CAS dasturida aloqaga chiqmagan hisoblagichlar bo'yicha", "short": "Aloqaga chiqmagan",
    "head": [
        [H("Hudud nomi", 4, 1), H("Aloqaga chiqqan hisoblagichlar soni", 4, 1, "vert green"),
         H("Aloqadan chiqib ketgan hisoblagichlar soni", 1, 15, "red")],
        [H("Jami", 1, 3), H("Iste'molchi turi kesimida", 1, 6, "it"), H("Vaqtlar kesimida", 1, 6, "it")],
        [H("soni", 2, 1, "red s"), H("%", 2, 1, "s"), H("↑↓", 2, 1, "arr"), H("Aholi", 1, 2, "green"),
         H("Ulgurji", 1, 2, "blue"), H("Balans", 1, 2, "amber"), H("7-30 kun", 1, 2), H("1-3 oy", 1, 2),
         H("3 oydan ortiq", 1, 2)],
        _S4(6)],
    "cols": [n("c0", "green b"), n("c1", "red b"), t("t2"), d("c1", "bad"), n("c3", "b"), d("c3", "bad"),
             n("c4", "b"), d("c4", "bad"), n("c5", "amber"), d("c5", "bad"), n("c6", "b"), d("c6", "bad"),
             n("c7", "b"), d("c7", "bad"), n("c8", "b"), d("c8", "bad")]}
TABLES["r3"] = {
    "title": "hududida CAS dasturida tarmoqdan uzilgan hisoblagichlar bo'yicha", "short": "Tarmoqdan uzilgan",
    "head": [
        [H("Hudud nomi", 4, 1), H("Aloqaga chiqqan hisoblagichlar soni", 4, 1, "vert green"),
         H("Tarmoqdan uzilgan hisoblagichlar", 1, 9, "red"),
         H("To'g'ridan-to'g'ri ulanishlar soni (peremichka)", 3, 2, "purple")],
        [H("Jami", 1, 3), H("shundan", 1, 6, "it")],
        [H("soni", 2, 1, "red s"), H("%", 2, 1, "s"), H("↑↓", 2, 1, "arr"), H("4-7 kun", 1, 2), H("7-30 kun", 1, 2),
         H("30 kundan ortiq", 1, 2)],
        _S4(4)],
    "cols": [n("c0", "green b"), n("c1", "red b"), t("t2"), d("c1", "bad"), n("c3", "b"), d("c3", "bad"),
             n("c4", "b"), d("c4", "bad"), n("c5", "b"), d("c5", "bad"), n("c6", "purple b"), d("c6", "bad")]}
TABLES["r4"] = {
    "title": "hududida CAS dasturidagi balans hisoblagichlar va transformatorlar yuklamasi bo'yicha",
    "short": "Balans va yuklama",
    "head": [
        [H("Hudud nomi", 3, 1), H("Loyiha doirasida", 3, 1, "vert"), H("CAS ga yuklangan", 3, 1, "vert"),
         H("Balans hisoblagichlar", 1, 4), H("Muammoli transformatorlar", 2, 2, "amber"), H("shundan", 1, 6, "it")],
        [H("Bir marta obxod olgan", 2, 1, "green"), H("Umuman obxod olmagan", 2, 1, "red"),
         H("shundan 3 kundan ortiq obxod olmagan", 1, 2, "red"),
         H("Quvvati kiritilmagan", 2, 1, "s"), H("TT noto'g'ri yoki nominali xato", 2, 1, "s"),
         H("Sxema xato yoki cos=0", 2, 1, "s"), H("Balans hisoblagich aloqaga chiqmagan", 2, 1, "s"),
         H("TP nagruzkasi 0%", 2, 1, "amber s"), H("TP nagruzkasi 150%", 2, 1, "s")],
        _S4(2)],
    "cols": [n("c0", "b"), n("c1", "b"), n("c2", "green b"), n("c3", "red b"), n("c4", "red b"), d("c4", "bad"),
             n("c5", "amber b"), d("c5", "bad"), n("c6", "red"), n("c7", "red"), n("c8", "red"), n("c9", "red"),
             n("c10", "amber"), n("c11", "b")]}
TABLES["r6"] = {**TABLES["obxod"], "cols": [
    n("c0", "b"), n("c1", "b"), t("t2"), d("c1", "mid"), n("c3"), n("c4", "b"), t("t5"), d("c4", "mid"),
    n("c6"), n("c7", "b"), t("t8"), d("c7", "mid"), n("c9"), n("c10", "b"), t("t11"), d("c10", "mid")]}
TABLES["r7"] = {
    "title": "hududida balans va iste'molchilar hisoblagichlari o'rtasidagi tafovutlar bo'yicha",
    "short": "Balans tafovuti",
    "head": [
        [H("Hudud nomi", 3, 1), H("CAS dasturidagi transformatorlar", 1, 2),
         H("Balans hisoblagich o'rnatilgan TP lar soni", 3, 1, "vert"),
         H("Balans hisoblagich va iste'molchilar hisoblagichlari o'rtasidagi tafovut", 1, 12, "red")],
        [H("Jami soni", 2, 1, "vert"), H("shundan rezervda (2x seksiyali)", 2, 1, "vert"),
         H("Manfiy", 1, 2, "red"), H("0%", 1, 2), H("1-10%", 1, 2), H("10-20%", 1, 2), H("20-50%", 1, 2),
         H("50-100%", 1, 2, "red")],
        _S4(6)],
    "cols": [n("c0", "b"), n("c1", "b"), n("c2", "b"), n("c3", "red b"), d("c3", "bad"), n("c4", "b"), d("c4", "bad"),
             n("c5", "b"), d("c5", "bad"), n("c6", "b"), d("c6", "bad"), n("c7", "b"), d("c7", "bad"),
             n("c8", "red b"), d("c8", "bad")]}
TABLES["r8"] = {
    "title": "hududida Billing va CAS dasturlarida tafovutga ega hisoblagichlar bo'yicha", "short": "Billing va CAS",
    "head": [
        [H("Hudud nomi", 4, 1), H("Billing dasturi bilan ma'lumot almashmaydigan hisoblagichlar", 3, 2, "red"),
         H("shundan", 1, 6, "red it"), H("«Billing» dasturida mavjud", 1, 6, "amber"),
         H("CAS dasturida mavjud, Billing dasturiga kiritilmagan", 1, 4, "green")],
        [H("Iste'molchi hisob raqami mos emas", 2, 2), H("Iste'molchi turi mos emas", 2, 2),
         H("CAS dasturida mavjud bo'lmagan hisoblagichlar", 2, 2), H("ASKUE ga mos bo'lmagan hisoblagichlar", 2, 2, "blue"),
         H("shundan", 1, 2, "it"), H("Dublikat hisoblagichlar", 2, 2, "amber"),
         H("hisoblagichlar jami soni", 2, 2, "green"), H("shundan obxod olgan", 1, 2, "it")],
        [H("Aholi", 2, 1, "green"), H("Ulgurji", 2, 1, "amber"), H("3 kun ichida", 2, 1, "blue"),
         H("30 kun ichida", 2, 1, "blue")],
        _S4(7)],
    "cols": [n("c0", "red b"), d("c0", "bad"), n("c1", "b"), d("c1", "bad"), n("c2", "b"), d("c2", "bad"),
             n("c3", "b"), d("c3", "bad"), n("c4", "b"), d("c4", "bad"), n("c5", "green"), n("c6", "amber"),
             n("c7", "amber b"), d("c7", "bad"), n("c8", "green b"), d("c8", "bad"), n("c9", "blue b"),
             n("c10", "blue b")]}

# pol: o'sish / kamayish ranglari
POL = {"bad": ("red", "blue"), "mid": ("blue", "red"), "good": ("green", "red")}
# Namuna (Excel) hisobotidagi ranglar: oq fon, qora chegara, och ko'k sarlavha, och sariq "Jami" qatori
COLORS = {"red": "#C00000", "green": "#00A050", "blue": "#0033CC", "amber": "#C55A11", "purple": "#7030A0",
          "": "#000000", "b": "#000000"}
ARROW = {"up_red": "#FF0000", "down_blue": "#0033CC"}
HEAD_BG = "#DCE6F1"
TOTAL_BG = "#FFE699"
HEAD_TXT = {"red": "#C00000", "green": "#00A050", "blue": "#2F5597", "amber": "#C55A11", "purple": "#7030A0",
            "": "#000000"}


def head_style(cls: str) -> dict:
    """Sarlavha katagi uslubi: matn rangi, vertikal, kursiv, kichik, strelka."""
    t = (cls or "").split()
    color = next((x for x in t if x in HEAD_TXT), "")
    return {"color": HEAD_TXT[color], "vert": "vert" in t, "it": "it" in t, "small": "s" in t, "arr": "arr" in t}


def place_header(rows: list[list[tuple]], ncols: int) -> list[tuple]:
    """HTML jadval kabi rowspan/colspan joylashtiradi. Qaytaradi: [(r, c, rs, cs, label, cls)]."""
    occupied: set[tuple[int, int]] = set()
    cells = []
    for r, row in enumerate(rows):
        c = 0
        for label, rs, cs, cls in row:
            while (r, c) in occupied:
                c += 1
            for i in range(rs):
                for j in range(cs):
                    occupied.add((r + i, c + j))
            cells.append((r, c, rs, cs, label, cls))
            c += cs
    return cells


def fmt_num(v) -> str:
    return "" if v is None else f"{int(round(v)):,}".replace(",", " ")


def cell_values(col: tuple, cur: dict, base: dict | None):
    """Qaytaradi: (matn, rang_nomi, qalin_mi)."""
    t = col[0]
    if t == "n":
        v = cur.get(col[1], 0)
        cls = col[2].split()
        color = next((x for x in cls if x in ("red", "green", "amber", "blue", "purple")), "")
        return (fmt_num(v) if v else "", color, True)
    if t == "t":                                  # tayyor matn (masalan, PDF'dagi foiz)
        return (str(cur.get(col[1], "") or ""), "", False)
    if t == "p":
        a, b = cur.get(col[1], 0), cur.get(col[2], 0)
        return (f"{a / b * 100:.1f}%".replace(".", ",") if b > 0 else "", "", False)
    if base is None:
        return ("", "", False)
    dv = cur.get(col[1], 0) - base.get(col[1], 0)
    if dv == 0:
        return ("", "", False)
    up, down = POL[col[2]]
    return (("↑" if dv > 0 else "↓") + fmt_num(abs(dv)), up if dv > 0 else down, True)
