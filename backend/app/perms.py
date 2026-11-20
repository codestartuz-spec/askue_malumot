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
    ("data.upload", "Jadvallar va sahifalar", "Ma'lumot yuklash sahifasi",
     "Area/Details fayllarini va respublika PDF'ini yuklaydi, yuklash tarixini ko'radi", None),

    ("drill.view", "Ro'yxat va hisobotlar", "Raqam ustiga bosib nomma-nom ro'yxatni ko'rish",
     "Jadvaldagi raqamni bosganda hisoblagich/TP ro'yxati ochiladi", None),
    ("export", "Ro'yxat va hisobotlar", "Ro'yxatni Excel'ga yuklab olish",
     "Nomma-nom ro'yxatni Excel qilib saqlaydi", "drill.view"),
    ("dynamics.compare", "Ro'yxat va hisobotlar", "Dinamika sanalarini o'zgartirib solishtirish",
     "Istalgan ikki sanani tanlab solishtiradi (bo'lmasa — joriy oy boshi bilan)", None),
    ("report.download", "Ro'yxat va hisobotlar", "Dinamikani Excel / PDF ko'rinishida yuklab olish",
     "Butun viloyat yoki tuman hisobotini fayl qilib yuklaydi", None),

    ("brigade.edit", "Brigadalar", "Brigada nomi va xodimlarini tahrirlash",
     "Brigada yaratadi, nomini va xodimlar ro'yxatini o'zgartiradi", "brigade.view"),
    ("brigade.assign", "Brigadalar", "TP'larni brigadaga biriktirish / ko'chirish",
     "TP'larni bir brigadadan boshqasiga o'tkazadi", "brigade.view"),

    ("telegram.send", "Telegram va sozlamalar", "Telegramga yuborish",
     "Dinamika hisobotlarini va xabarlarni (matn, rasm, video) kanal/guruhlarga yuboradi", None),
    ("settings.manage", "Telegram va sozlamalar", "Bot va guruhlarni boshqarish",
     "Kanal/guruh qo'shadi va olib tashlaydi (bot tokenini faqat sadmin o'zgartiradi)", None),

    ("system.view", "Tizim", "Tizim va server holatini ko'rish",
     "Sozlamalar → Tizim holati: baza, worker, bot, server resurslari", None),
    ("backup.manage", "Tizim", "Zaxira nusxalarni boshqarish",
     "Sozlamalar → Zaxira nusxa: jadval, hozir olish, yuklab olish, o'chirish", None),
]
PERM_CODES = {p[0] for p in PERMS}
NEEDS = {p[0]: p[4] for p in PERMS if p[4]}
