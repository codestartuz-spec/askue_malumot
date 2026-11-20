# ASKUE ma'lumot

Qashqadaryo hududiy filiali uchun CAS (ASKUE) ma'lumotlari monitoringi: konsentratorlar, aloqadan chiqqan va 48 soat obxod bergan hisoblagichlarning tuman va brigadalar kesimidagi kunlik dinamikasi.

**Texnologiyalar:** Python (FastAPI) · MySQL · React (Vite). Yuklash navbat (job) orqali alohida *worker* jarayonida bajariladi.

## Ishga tushirish (Windows)

1. MySQL tayyor bo'lsin (o'rnatilgan MySQL yoki `docker compose up -d` — `docker-compose.yml` tayyor, parol `root`, baza `askue`).
2. `setup.bat` — kutubxonalarni o'rnatadi va `backend\.env` yaratadi. Ofis proksisi bo'lsa, `setup.bat` ichidagi `ASKUE_PROXY` qatorini yoqing.
3. `backend\.env` dagi `DATABASE_URL` (MySQL login/paroli) ni tekshiring. Baza yo'q bo'lsa, avtomatik yaratiladi.
4. `start.bat` — ikki oyna ochiladi (Server va Worker) va brauzerda `http://localhost:8000` ochiladi.

Boshlang'ich kirish: **sadmin / Sadmin@2026** (`.env` da o'zgartiriladi). Kirgach parolni almashtiring.
Tarmoqdagi boshqa qurilmalardan: `http://<kompyuter-IP>:8000`.

Rivojlantirish rejimi: `backend` da `uvicorn app.main:app --reload`, `python -m app.worker`; `frontend` da `npm run dev` (http://localhost:5173).

## Ma'lumot qanday yuklanadi

«Ma'lumot yuklash» sahifasida generator tayyorlagan `Area_…csv.gz` va `Details_…csv.gz` fayllari tanlanadi (sana fayl nomidan olinadi). Yuklash orqa fonda, foiz ko'rsatkichi bilan bajariladi.

- **Sinxronlash:** bazada mavjud yozuvlar yangilanadi, yangilari qo'shiladi, faylda yo'qlari o'chiriladi (TP — tuman + TP kodi bo'yicha, hisoblagich — raqami bo'yicha).
- **Kunlik dinamika:** har yuklashda shu sananing jami sonlari (tuman × brigada kesimida) alohida saqlanadi. Bir sana qayta yuklansa, o'sha sana yangilanadi. Nomma-nom ro'yxat doim oxirgi yuklangan ma'lumot bo'yicha.
- **Himoya:** fayl to'liq emas ko'rinsa (avvalgi hajmning yarmidan kam), eski ma'lumot o'chirilmaydi va xatolik ko'rsatiladi.

## Brigadalar

- Har bir tumandagi har xil `Manager Name` qiymati — alohida brigada (`1-brigada`, `2-brigada`…). Xodimlar shu matndan ajratib olinadi (vergul, nuqta, `;`, `/`), noto'g'ri ajralgan bo'lsa tahrirlab to'g'rilanadi.
- Brigada nomi, xodimlari va qo'lda biriktirilgan TP'lar keyingi yuklashlarda **o'zgarmaydi**. Faylda TP'ning menejeri o'zgarsa va TP qo'lda tegilmagan bo'lsa, u yangi brigadaga o'tadi.
- Menejeri yo'q TP'lar o'z tumanida «Biriktirilmagan» sifatida ko'rinadi; ularni brigadaga biriktirish mumkin (alohida ruxsat bilan).

## Ruxsatlar

Sadmin — bitta, barcha ruxsatlarga ega. Qolgan xodimlarga sadmin «Xodimlar va ruxsatlar» sahifasida sahifalar (3 jadval, brigadalar) va amallar (ro'yxatni ko'rish, Excel, sanalarni solishtirish, brigada tahriri, TP biriktirish, yuklash) bo'yicha ruxsat beradi. Barcha o'zgarishlar «Harakatlar jurnali»da saqlanadi.

## Jadvallardagi hisob-kitob

| Jadval | Ko'rsatkich |
|---|---|
| Konsentratorlar | CAS ga yuklangan = «Iste'molchi biriktirilgan» belgisi; Online = yuklangan − Offline (>24 soat); 3 kundan ortiq = >72 soat; obxod darajalari Daily ustunlaridan |
| Aloqadan chiqqanlar | Aloqaga chiqqan = oxirgi obxod ≤7 kun; chiqib ketgan = 7-30, 1-3 oy (30-90), 3 oydan ortiq (90+); % = chiqib ketgan / aloqaga chiqqan; «Obxod vaqti yo'q» — alohida ustun |
| 48 soat obxod | Obxod olgan = «0-2 kun» guruhidagilar; turlar: aholi (2), ulgurji (1), balans (3) |

Dinamika (↑↓) = tanlangan «oxirgi» sana minus «boshlang'ich» sana (standart: shu oyning birinchi yuklangan kuni).

## Xarita

«Xarita» sahifasida koordinatasi bor hisoblagichlar (aholi, ulgurji, balans) va konsentratorlar belgilar bilan ko'rinadi; belgi ustiga olib borilsa qurilma haqida to'liq ma'lumot chiqadi. Ko'p nuqta bo'lsa, ular server tomonida guruhlanadi (yaqinlashtirgan sari ajraladi). Filtrlar: tuman, brigada, qurilma turi, holati; hisoblagich/abonent/TP bo'yicha qidiruv. Dinamika ro'yxatlaridagi **«Xaritada ko'rish»** tugmasi va har bir qator yonidagi pin shu ro'yxatni xaritada ochadi.

Konsentratorlarda koordinata ustuni yo'q, shuning uchun u TP'ga biriktirilgan hisoblagichlar koordinatalarining markazi (chetga chiqqan xato nuqtalar hisobga olinmaydi) sifatida avtomatik hisoblanadi — har yuklashda yangilanadi. Xarita plitkalari (OpenStreetMap / Esri / CARTO) brauzer orqali internetdan yuklanadi.

## Telegram bot va hisobotlar

1. **Sozlamalar** sahifasida bot tokeni kiritiladi (@BotFather). Bot **worker** jarayonida ishlaydi (`start.bat` ikkalasini ham ishga tushiradi).
2. Bot kanal/guruhga admin qilib qo'shilganda, ular Sozlamalarda o'zi paydo bo'ladi; kerak bo'lsa chat ID yoki `@nom` orqali qo'lda qo'shiladi.
3. Ofis tarmog'i proksi orqali chiqsa, `backend\.env` ga `TELEGRAM_PROXY=http://192.168.0.1:3128` yozing.
4. **Dinamika** sahifasida: «Yuklab olish» — butun viloyat (yoki tanlangan tuman — brigadalar kesimida) uchun Excel / PDF; «Telegramga yuborish» — viloyat PDF/Excel, tumanlar PDF/Excel (tumanlar alohida tanlanadi) va kanal/guruhlar ro'yxati; yuborish jarayoni foiz bilan ko'rinadi.
5. **Parolni tiklash:** xodim profiliga telefon va Telegram chat ID kiritiladi (chat ID'ni bot `/start` ga javob sifatida yozib beradi). Kirish sahifasidagi «Parolni unutdingizmi?» orqali botga 6 xonali kod keladi; yoki botga `/parol` yozilsa yangi vaqtinchalik parol yuboriladi.

Ruxsatlar: `map.view`, `settings.manage`, `report.download`, `telegram.send` qo'shildi (Xodimlar sahifasida belgilanadi). Hisobot shriftlari `backend/assets/fonts` da.

## Tuzilma

```
backend/   FastAPI: app/routers (API), app/services (sinxronlash, snapshot), app/worker.py (navbat)
frontend/  React: src/pages, src/tables.js (jadval tuzilmasi), dist/ (tayyor build)
```

## Oxirgi yangilanishlar
- **Dinamika jadvallari** Excel/PDF hisobotlari namunadagi ko'rinishda (oq fon, och ko'k sarlavha, sariq «Jami»). Brigadalar kesimida har bir brigada xodimlari ham chiqadi.
- **«Aloqadan chiqib ketgan hisoblagichlar»** jadvali: «Aloqaga chiqmay qolgan» (2-7 kun, 7-30 kun, 1-3 oy, 3 oydan ortiq), «Umuman aloqaga chiqmagan» va «To'g'ridan-to'g'ri ulanish (peremichka)» ustunlari. Aloqaga chiqqan = oxirgi 2 kun ichida obxod bergan.
- **Sozlamalar** tablari: «Xabar yuborish» (matn, rasm, video, albom; Telegram ko'rinishidagi jonli ko'rinish) va «Bot va guruh sozlamalari».
- **Xarita**: har bir holat alohida rang va soni bilan (hisoblagich: 0-2 kun, 2-7, 7-30, 1-3 oy, 3 oydan ortiq, umuman yo'q, peremichka; konsentrator: online/offline/3 kundan ortiq/obxod darajalari).
- Telegram'ga yuborishda uzilgan ulanish 3 martagacha qayta uriniladi.
- Eski snapshotlarda yangi ko'rsatkichlar (2-7 kun, peremichka) yo'q: fayllarni qayta yuklasangiz shu sana uchun yangidan hisoblanadi.

## Yangilanish (21.11)
- Kunlik dinamika: aloqa jadvalidan «Aloqaga chiqqan» ustuni olib tashlandi, «Umuman aloqaga chiqmagan» uchun ↑↓ qo'shildi; PDF A4 varaqni to'liq to'ldiradi.
- Manzil belgisi Google Maps yo'nalishini ochadi (hisoblagich va TP); qorong'u xarita kalitsiz OSM asosida.
- Telegram: yuborish oralig'i va 429 (retry after) kutish yaxshilandi.
- Respublika dinamikasi: «Ma'lumot yuklash → Respublika dinamikasi» orqali PDF yuklanadi; alohida sahifada kunma-kun solishtirish, PDF/Excel yuklash va Telegramga yuborish.
- Sozlamalar: «Tizim va server holati» va «Zaxira nusxa» (har kuni 01:00, sadminga Telegram orqali; worker ishlashi shart). Tiklash: gunzip -c fayl.sql.gz | mysql -u root -p askue
- Ruxsatlar qayta tuzildi (yangi: republic.view, system.view, backup.manage; bog'liq ruxsatlar avtomatik).
- Yangi kutubxonalar: pdfplumber, psutil — setup.bat qayta ishga tushiring.
