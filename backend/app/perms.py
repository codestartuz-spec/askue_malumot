"""Ruxsatlar katalogi. Sadmin barcha ruxsatlarga ega; qolganlariga sadmin belgilaydi.
Har bir ruxsat: (kod, guruh, nomi, izoh, bog'liq ruxsat). «Bog'liq» — shu ruxsat ishlashi uchun kerak bo'lgan boshqa ruxsat."""

PERMS = [
    # (kod, guruh, nomi, izoh, needs)
    ("view.konsentrator", "Jadvallar va sahifalar", "Kunlik dinamika: Konsentratorlar jadvali",
     "Konsentratorlar holati va obxod darajasi jadvalini ko'radi", None),
    ("view.aloqa", "Jadvallar va sahifalar", "Kunlik dinamika: Aloqadan chiqib ketgan hisoblagichlar jadvali",
     "Aloqaga chiqmay qolgan, umuman chiqmagan va peremichka jadvalini ko'radi", None),
    ("view.obxod", "Jadvallar va sahifalar", "Kunlik dinamika: 48 soat obxod jadvali",
     "48 soat ichida obxod bergan hisoblagichlar jadvalini ko'radi", None),
    ("map.view", "Jadvallar va sahifalar", "Xarita sahifasi",
     "Hisoblagich va konsentratorlarni xaritada ko'radi, qidiradi; ro'yxatlarda manzil belgisi chiqadi", None),
    ("brigade.view", "Jadvallar va sahifalar", "Brigadalar sahifasi",
     "Brigadalar, ularning xodimlari va TP'larini ko'radi", None),
    ("republic.view", "Jadvallar va sahifalar", "Respublika dinamikasi sahifasi",
     "Viloyat bo'yicha respublika dinamikasini ko'radi va kunma-kun solishtiradi", None),
    ("ag.view", "Jadvallar va sahifalar", "AG dinamikasi sahifasi",
     "Aloqadan chiqib ketgan hisoblagichlar va hodisalar (AG) dinamikasini ko'radi va solishtiradi", None),
    ("data.upload", "Ma'lumot yuklash", "Kunlik ma'lumot (Area / Details) yuklash",
     "Ma'lumot yuklash sahifasi: Area/Details fayllarini yuklaydi va yuklash tarixini ko'radi", None),
    ("republic.upload", "Ma'lumot yuklash", "Respublika PDF'ini yuklash",
     "Respublika dinamikasi PDF'ini yuklaydi, yuklangan sanalar ro'yxatini ko'radi", None),
    ("ag.upload", "Ma'lumot yuklash", "AG PDF'ini yuklash",
     "AG dinamikasi PDF'ini yuklaydi, yuklangan sanalar ro'yxatini ko'radi", None),
    ("data.delete", "Ma'lumot yuklash", "Yuklangan ma'lumotni o'chirish",
     "Yuklash tarixidagi yozuvni, fayllarni va shu sana dinamikasini (Kunlik / Respublika / AG) o'chiradi", None),

    ("daily.view", "Kunlik topshiriq", "Kunlik topshiriq bo'limini ko'rish",
     "Bo'lim, arxiv va tayyor jadvallarni ko'radi (fayl yuklab olish va yuborish alohida ruxsat)", None),
    ("daily.upload", "Kunlik topshiriq", "5 ta Excel faylni yuklash",
     "Har kungi 5 ta faylni yuklaydi (sanani tanlaydi); iste'molchi turini belgilashi mumkin", "daily.view"),
    ("daily.recompute", "Kunlik topshiriq", "Qayta hisoblash",
     "Sozlamalar o'zgargach kunni asl fayllardan qayta hisoblaydi; iste'molchi turini belgilaydi", "daily.view"),
    ("daily.download", "Kunlik topshiriq", "Tayyor fayl va rasmlarni yuklab olish",
     "2 ta jadval rasmi, 7 ta nomma-nom Excel va ZIP'ni yuklab oladi", "daily.view"),
    ("daily.original", "Kunlik topshiriq", "Yuklangan asl fayllarni yuklab olish",
     "Serverda saqlangan 5 ta asl Excel faylni yuklab oladi", "daily.view"),
    ("daily.send", "Kunlik topshiriq", "Kunlik topshiriq fayllarini Telegramga yuborish",
     "Tanlangan jadval rasmlari va Excel fayllarni kanal/guruhlarga yuboradi (Telegram yuborish ruxsati ham kerak)", "daily.view"),
    ("daily.settings", "Kunlik topshiriq", "Kunlik topshiriq sozlamalari",
     "Jadval va fayl nomlari, offline kunlari, kun oraliqlari, rayonlar tartibi, standart kanallar", "daily.view"),
    ("daily.delete", "Kunlik topshiriq", "Arxivdan o'chirish", "Kun yozuvi va uning fayllarini o'chiradi", "daily.view"),

    ("drill.view", "Ro'yxat va hisobotlar", "Raqam ustiga bosib nomma-nom ro'yxatni ko'rish",
     "Jadvaldagi raqamni bosganda hisoblagich/TP ro'yxati ochiladi", None),
    ("export", "Ro'yxat va hisobotlar", "Ro'yxatni Excel'ga yuklab olish",
     "Nomma-nom ro'yxatni Excel qilib saqlaydi", "drill.view"),
    ("republic.original", "Ro'yxat va hisobotlar", "Respublika asl PDF faylini ochish va yuklab olish",
     "Respublika markazi yuborgan PDF'ni brauzerda ochadi yoki yuklab oladi", "republic.view"),
    ("ag.original", "Ro'yxat va hisobotlar", "AG asl PDF faylini ochish va yuklab olish",
     "AG markazi yuborgan PDF'ni brauzerda ochadi yoki yuklab oladi", "ag.view"),
    ("dynamics.compare", "Ro'yxat va hisobotlar", "Dinamika sanalarini o'zgartirib solishtirish",
     "Istalgan ikki sanani tanlab solishtiradi (bo'lmasa — joriy oy boshi bilan)", None),
    ("report.download", "Ro'yxat va hisobotlar", "Dinamikani Excel / PDF ko'rinishida yuklab olish",
     "Butun viloyat yoki tuman hisobotini fayl qilib yuklaydi", None),

    ("brigade.edit", "Brigadalar", "Brigada nomi va xodimlarini tahrirlash",
     "Brigada yaratadi, nomini va xodimlar ro'yxatini o'zgartiradi", "brigade.view"),
    ("brigade.assign", "Brigadalar", "TP'larni brigadaga biriktirish / ko'chirish",
     "TP'larni bir brigadadan boshqasiga o'tkazadi", "brigade.view"),

    ("telegram.send", "Telegram va sozlamalar", "Hisobotlarni Telegramga yuborish",
     "Kunlik, Respublika va AG dinamikasi hisobotlarini kanal/guruhlarga yuboradi", None),
    ("telegram.message", "Telegram va sozlamalar", "Xabar yuborish (matn, rasm, video)",
     "«Xabar yuborish» bo'limi: erkin xabar tayyorlab kanal/guruhlarga yuboradi", None),
    ("telegram.journal", "Telegram va sozlamalar", "Yuborilganlar jurnali va «Tanishdim» holati",
     "Yuborilgan xabar/hisobotlar tarixi, kim va qachon tanishgani", None),
    ("settings.manage", "Telegram va sozlamalar", "Bot va guruhlarni boshqarish",
     "Kanal/guruh qo'shadi va olib tashlaydi (bot tokenini faqat sadmin o'zgartiradi)", None),

    ("audit.view", "Tizim", "Harakatlar jurnalini ko'rish",
     "Kim qachon nima qilganini ko'rsatuvchi jurnal", None),
    ("system.view", "Tizim", "Tizim va server holatini ko'rish",
     "Sozlamalar → Tizim holati: baza, worker, bot, server resurslari", None),
    ("backup.manage", "Tizim", "Zaxira nusxalarni boshqarish",
     "Sozlamalar → Zaxira nusxa: jadval, hozir olish, yuklab olish, o'chirish", None),
]
PERM_CODES = {p[0] for p in PERMS}
NEEDS = {p[0]: p[4] for p in PERMS if p[4]}

_TBL = ["view.konsentrator", "view.aloqa", "view.obxod"]
# Tayyor ruxsat to'plamlari — YAGONA manba (frontend /meta/bootstrap orqali oladi)
PRESETS = [
    {"name": "Kuzatuvchi", "hint": "Faqat jadvallarni ko'radi", "codes": _TBL + ["republic.view", "ag.view"]},
    {"name": "Operator", "hint": "Jadval, xarita, ro'yxat va Excel/PDF",
     "codes": _TBL + ["republic.view", "map.view", "drill.view", "export", "dynamics.compare", "report.download",
                      "republic.original", "ag.view", "ag.original"]},
    {"name": "Brigadir", "hint": "Brigadalar va xarita",
     "codes": _TBL + ["map.view", "brigade.view", "brigade.edit", "brigade.assign", "drill.view", "export"]},
    {"name": "Ma'lumot kiritish", "hint": "Fayl yuklaydi va o'chiradi",
     "codes": _TBL + ["republic.view", "data.upload", "republic.upload", "data.delete", "republic.original",
                      "ag.view", "ag.upload", "ag.original"]},
    {"name": "Kunlik topshiriq", "hint": "Fayl yuklaydi, jadval tayyorlaydi va Telegramga yuboradi",
     "codes": ["daily.view", "daily.upload", "daily.recompute", "daily.download", "daily.original", "daily.send",
               "telegram.send"]},
    {"name": "Kunlik topshiriq (ko'ruvchi)", "hint": "Tayyor jadval va fayllarni ko'radi, yuklab oladi",
     "codes": ["daily.view", "daily.download"]},
    {"name": "Telegram operatori", "hint": "Hisobot va xabar yuboradi",
     "codes": _TBL + ["republic.view", "ag.view", "report.download", "telegram.send", "telegram.message",
                      "telegram.journal"]},
]


def validate_catalog() -> list[str]:
    """Katalog izchilligini tekshiradi (testlar chaqiradi): xatolar ro'yxati, bo'sh bo'lsa hammasi joyida."""
    errs = []
    codes = [p[0] for p in PERMS]
    errs += [f"takroriy kod: {c}" for c in set(codes) if codes.count(c) > 1]
    errs += [f"{p[0]}: bog'liq ruxsat yo'q ({p[4]})" for p in PERMS if p[4] and p[4] not in PERM_CODES]
    for pr in PRESETS:
        errs += [f"preset {pr['name']}: noma'lum kod {c}" for c in pr["codes"] if c not in PERM_CODES]
    for old, new in list(INHERIT.items()) + [i for g in INHERIT_GROUPS.values() for i in g.items()]:
        errs += [f"INHERIT: noma'lum kod {c}" for c in [old, *new] if c not in PERM_CODES]
    return errs

# Eski ruxsatlar bo'yicha yangi ruxsatlarni avtomatik berish (bir marta): (eski, [yangilari])
INHERIT = {"data.upload": ["republic.upload", "data.delete"],
           "telegram.send": ["telegram.message", "telegram.journal"],
           "republic.view": ["republic.original"],
           "daily.view": ["daily.download"], "daily.upload": ["daily.recompute"]}

# Guruh bo'yicha (bir marta): yangi bo'lim ruxsatlarini mavjud bo'lim ruxsati bor xodimlarga berish
INHERIT_GROUPS = {"grp:ag": {"republic.view": ["ag.view"], "republic.upload": ["ag.upload"],
                             "republic.original": ["ag.original"]}}
