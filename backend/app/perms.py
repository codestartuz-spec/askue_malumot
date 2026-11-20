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
    ("data.upload", "Ma'lumot yuklash", "Kunlik ma'lumot (Area / Details) yuklash",
     "Ma'lumot yuklash sahifasi: Area/Details fayllarini yuklaydi va yuklash tarixini ko'radi", None),
    ("republic.upload", "Ma'lumot yuklash", "Respublika PDF'ini yuklash",
     "Respublika dinamikasi PDF'ini yuklaydi, yuklangan sanalar ro'yxatini ko'radi", None),
    ("data.delete", "Ma'lumot yuklash", "Yuklangan ma'lumotni o'chirish",
     "Yuklash tarixidagi yozuvni, fayllarni va shu sana dinamikasini (Kunlik / Respublika) o'chiradi", None),

    ("drill.view", "Ro'yxat va hisobotlar", "Raqam ustiga bosib nomma-nom ro'yxatni ko'rish",
     "Jadvaldagi raqamni bosganda hisoblagich/TP ro'yxati ochiladi", None),
    ("export", "Ro'yxat va hisobotlar", "Ro'yxatni Excel'ga yuklab olish",
     "Nomma-nom ro'yxatni Excel qilib saqlaydi", "drill.view"),
    ("republic.original", "Ro'yxat va hisobotlar", "Respublika asl PDF faylini ochish va yuklab olish",
     "Respublika markazi yuborgan PDF'ni brauzerda ochadi yoki yuklab oladi", "republic.view"),
    ("dynamics.compare", "Ro'yxat va hisobotlar", "Dinamika sanalarini o'zgartirib solishtirish",
     "Istalgan ikki sanani tanlab solishtiradi (bo'lmasa — joriy oy boshi bilan)", None),
    ("report.download", "Ro'yxat va hisobotlar", "Dinamikani Excel / PDF ko'rinishida yuklab olish",
     "Butun viloyat yoki tuman hisobotini fayl qilib yuklaydi", None),

    ("brigade.edit", "Brigadalar", "Brigada nomi va xodimlarini tahrirlash",
     "Brigada yaratadi, nomini va xodimlar ro'yxatini o'zgartiradi", "brigade.view"),
    ("brigade.assign", "Brigadalar", "TP'larni brigadaga biriktirish / ko'chirish",
     "TP'larni bir brigadadan boshqasiga o'tkazadi", "brigade.view"),

    ("telegram.send", "Telegram va sozlamalar", "Hisobotlarni Telegramga yuborish",
     "Kunlik va Respublika dinamikasi hisobotlarini kanal/guruhlarga yuboradi", None),
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

# Eski ruxsatlar bo'yicha yangi ruxsatlarni avtomatik berish (bir marta): (eski, [yangilari])
INHERIT = {"data.upload": ["republic.upload", "data.delete"],
           "telegram.send": ["telegram.message", "telegram.journal"],
           "republic.view": ["republic.original"]}
