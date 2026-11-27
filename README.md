# ASKUE ma'lumot

Qashqadaryo hududiy filiali uchun CAS (ASKUE) ma'lumotlari monitoringi: konsentratorlar, aloqadan chiqqan va 48 soat obxod bergan hisoblagichlarning tuman va brigadalar kesimidagi kunlik dinamikasi.

**Texnologiyalar:** Python (FastAPI) · MySQL · React (Vite). Yuklash navbat (job) orqali alohida *worker* jarayonida bajariladi.

## Serverga joylash (Docker + Cloudflare Tunnel)

Tizim 4 ta konteynerdan iborat: **mysql**, **api** (FastAPI + tayyor frontend), **worker** (yuklash navbati, Telegram bot, zaxira) va ixtiyoriy **cloudflared** (internetga chiqarish). MySQL tashqariga ochilmaydi, API faqat `127.0.0.1:8000` da ochiq turadi, internetga faqat Cloudflare Tunnel orqali chiqadi.

**1. GitHub'ga yuklash** (`.env`, `backend/data`, `node_modules` avtomatik e'tiborsiz qoldiriladi):
```
git init && git add . && git commit -m "ASKUE" && git branch -M main
git remote add origin git@github.com:<akkaunt>/<repo>.git && git push -u origin main
```

**2. Cloudflare'da tunnel yaratish** (bir marta): Zero Trust → Networks → Tunnels → *Create a tunnel* (Cloudflared) → token'ni nusxalang. *Public hostname*: o'zingizning domeningiz (masalan `askue.example.uz`), *Service*: `HTTP` → `api:8000`.

**3. Serverda (Ubuntu/Debian, SSH orqali)** — bitta buyruq:
```
git clone git@github.com:<akkaunt>/<repo>.git askue && cd askue
cp .env.example .env && nano .env      # faqat CLOUDFLARE_TUNNEL_TOKEN=... ni yozing (parollar o'zi to'ldiriladi)
bash deploy.sh
```
`deploy.sh` Docker'ni o'rnatadi (yo'q bo'lsa), parol va maxfiy kalitlarni tasodifiy yaratadi, tizimni yig'adi va ishga tushiradi; oxirida sadmin paroli ekranga chiqadi (u `.env` da ham saqlanadi). Tunnel tokeni bo'lmasa tunnel yoqilmaydi — tizim `http://<server>:8000` da (`API_BIND=0.0.0.0` qilsangiz) ishlaydi.

**Keyingi yangilashlar:** o'zgarishni GitHub'ga `git push` qiling, serverda `bash deploy.sh` — kod olinadi, qayta yig'iladi, ma'lumotlar (baza, yuklangan fayllar, zaxiralar) Docker volume'larda saqlanib qoladi.

| Buyruq | Vazifasi |
|---|---|
| `bash deploy.sh status` | konteynerlar holati |
| `bash deploy.sh logs api` | jurnal (`api`, `worker`, `mysql`, `cloudflared`) |
| `bash deploy.sh backup` | bazani `backups/` ga `.sql.gz` qilib saqlash |
| `bash deploy.sh restart` / `stop` | qayta ishga tushirish / to'xtatish |

Eslatma: Cloudflare bepul tarifida bitta so'rov hajmi **100 MB** bilan cheklangan. Area/Details fayllari shundan katta bo'lsa, yuklashni serverning ichki manzilidan (`http://127.0.0.1:8000`, SSH tunnel orqali) bajaring yoki tarifni oshiring.

## Ishga tushirish (Windows, mahalliy)

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


## Xavfsizlik, Redis va sifat (v10)

**Redis.** Docker'da avtomatik (`redis` xizmati, parol `.env` dagi `REDIS_PASSWORD`). U ishlatiladi: login urinishlarini cheklash
(login+IP, IP va login bo'yicha, bosqichma-bosqich 1→5→15→60 daqiqa bloklash), Telegramga yuborish navbati (worker ishonchli
oladi, yiqilsa qayta navbatga qaytadi), yetakchi qulf (bot polling / zaxira jadvali faqat bitta nusxada), sozlamalar keshi.
`REDIS_URL` bo'sh bo'lsa (Windows `start.bat`) xotira rejimi ishlaydi — bitta jarayon uchun yetarli, shuning uchun `start.bat` 1 ta
worker bilan ishga tushadi. Production'da (`ENV=production`) Redis'siz yoki `SECRET_KEY`siz ishga tushmaydi.

**Mijoz IP si.** `CF-Connecting-IP` / `X-Forwarded-For` ga faqat `TRUSTED_PROXIES` (standart: loopback va Docker tarmoqlari)
dagi proksidan kelgan so'rovlarda ishoniladi. Uvicorn'ning `--proxy-headers` rejimi o'chirilgan.

**Qurilma identifikatori.** Server imzolagan HttpOnly cookie (`askue_did`) + eski localStorage UUID (o'tish uchun). Cookie va
storage tozalansa ham, bloklangan qurilma bilan IP+User-Agent mos kelsa, baribir bloklangan hisoblanadi.

**PDF yuklash.** Kengaytma, hajm (`MAX_PDF_MB`), `%PDF-`/`%%EOF`, parol, JavaScript/Launch/EmbeddedFile va boshqa faol kontent
(`#xx` bilan yashirilganlari ham) tekshiriladi; o'qish alohida jarayonda, vaqt (`PDF_PARSE_TIMEOUT`) va xotira chegarasi bilan.
Area/Details: yuklash hajmi (`MAX_UPLOAD_MB`), `.gz` belgisi va ochilgandan keyingi hajm (`MAX_UNZIPPED_MB`, gzip-bomba) cheklangan;
o'qish oqim bilan, 4000 qatorlik bo'laklarda.

**Shifrlash.** Zaxira nusxalar `*.sql.gz.enc` (Fernet, kalit — `BACKUP_KEY`, bo'sh bo'lsa `SECRET_KEY`dan). Telegram tokeni bazada
shifrlangan (`enc1:`). Zaxirani ochish: `python -m app.tools.decrypt_backup fayl.sql.gz.enc`. **Kalitni yo'qotmang** — usiz ochib bo'lmaydi.

**Migratsiyalar.** Alembic (`backend/app/migrations`), ishga tushganda avtomatik (`MySQL GET_LOCK` bilan, API va worker bir vaqtda
ishlasa ham xavfsiz). Eski bazalar ham bir xil yo'l bilan yangilanadi. Yangi o'zgarish: `app/migrations/versions/` ga yangi fayl
(`add_column`/`add_index` yordamchilari qayta bajarilsa ham xavfsiz).

**MySQL 8.** Har ulanishda MySQL 8 `sql_mode` (ONLY_FULL_GROUP_BY, STRICT) o'rnatiladi, shuning uchun MariaDB'da ham xuddi shu
qoidalar bilan sinaladi. CI (`.github/workflows/ci.yml`) testlarni ham `mysql:8.0`, ham `mariadb` da yuritadi.

**Sozlamalar.** Hudud nomi, AG sarlavhasi/hududi/boshlang'ich sanasi — Sozlamalar → «Umumiy sozlamalar» (kodda qattiq yozilmagan).
Ruxsatlar va tayyor to'plamlar (presetlar) faqat `backend/app/perms.py` da; frontend ularni `/api/meta/bootstrap` dan oladi.

**Audit jurnali.** Qidiruv, foydalanuvchi/amal/IP/sana filtrlari, CSV va Excel eksport (formula in'ektsiyasidan himoyalangan),
`AUDIT_KEEP_DAYS` (standart 365) dan eskilari kuniga bir marta tozalanadi.

**Testlar.** `cd backend && pip install -r requirements-dev.txt && python -m pytest` (alohida `askue_test` bazasi kerak:
`TEST_DATABASE_URL`; Redis testlari uchun `redis-server` bo'lsa yoki `TEST_REDIS_URL`). Testlar ruxsatlar (har bir route),
login/IP/qurilma, PDF, shifrlash, Redis/navbat, migratsiya, audit va yuborish jarayonini qamraydi.

**Bog'liqliklar.** `requirements.txt` va `package.json` aniq versiyalarga qulflangan; Dependabot haftalik PR ochadi; CI'da
`pip-audit` va `npm audit` bor.

### v11 — fayl nomlari va izohsiz yuborish
- Telegramga hisobot fayllari **faqat fayl** sifatida yuboriladi (izoh/caption yo'q). Zaxira nusxasi sadminga alohida izoh bilan ketadi.
- Fayl nomlari Sozlamalar → Umumiy sozlamalar → «Fayl nomlari» bo'limida shablon bilan o'zgartiriladi (`{hudud} {nom} {sana} {sana_dmy} {dan} {dan_dmy} {yil} {oy} {kun} {asl}`). Kengaytma avtomatik; taqiqlangan belgilar olib tashlanadi. Kod: `backend/app/services/filenames.py`.
- Respublika 2-sahifa: yangi «Billingda otkl. status» ustuni («soni» katagi bilan); eski PDF'lar ustunsiz ko'rinadi.
- Xarita: OSM plitkalari 403 «Access blocked» bergan edi (Referrer-Policy `same-origin` Referer'ni olib tashlagan). Endi `strict-origin-when-cross-origin`; qorong'u xarita — CARTO dark; OSM javob bermasa avtomatik zaxira xarita yoqiladi.

## v12 — «Kunlik topshiriq» bo'limi (alohida)
- Menyu: **Kunlik topshiriq** → tablar: *Fayl yuklash*, *Arxiv*, *Sozlamalar*. Ruxsatlar: `daily.view/upload/original/send/settings/delete`.
- Har kuni 5 ta Excel (AreaInformationReport, CommissioningStatus, DirectMeter, NoMeterData, Online_Device_Monitoring) yuklanadi; fayl turi sarlavha bo'yicha aniqlanadi. Asl fayllar `data/daily/<sana>/orig` da saqlanadi.
- Natija: 2 ta jadval (Konsentratorlar; Aloqadan chiqib ketgan hisoblagichlar soni) — har biri alohida Excel, nomi jadval nomi + sana; hamda nomma-nom «Kunlik topshiriq» Excel (3 varaq: offline kontsentratorlar, aloqasiz hisoblagichlar, primichka; xodim bo'yicha tartiblangan, joylashuv — Google Maps havolasi).
- Offline: faqat Online_Device faylidan; oxirgi N kun (sukut 3: 21, 22, 23.11) «shundan N kundan ortiq» ga kirmaydi. Kun oraliqlari (2/7/30/90), jadval nomlari, fayl nomi shablonlari, rayonlar tartibi, standart kanallar — bo'lim Sozlamalarida.
- Iste'molchi turi tushunarsiz bo'lsa, yuklashda bir marta so'raladi va saqlanadi.
- Telegram: umumiy bot va kanallar; faqat fayl yuboriladi. Jadvallar: `daily_batches`, `daily_settings` (Alembic 0003).

## v13 — Kunlik topshiriq: 2 rasm + 7 alohida fayl, katak bo'yicha o'qish
- **Fayl turi va ustunlar sarlavha nomiga qaramaydi**: tur ma'lumot qatorining ko'rinishidan, ustunlar katak o'rnidan aniqlanadi
  (`services/daily.py`: `POS`, `_is_data`). Sarlavha nomi yoki tili o'zgarsa ham ishlaydi; fayl nomi faqat tenglikda yordam beradi.
- **Telegramga yuboriladi (shu tartibda)**: 1) Konsentratorlar jadvali — rasm; 2) Aloqadan chiqib ketgan hisoblagichlar jadvali — rasm;
  3) Offline konsentratorlar (N kundan ortiq); 4) Obxod olish darajasi past (0–50%) konsentratorlar; 5) To'g'ridan to'g'ri ulanish (Primichka);
  6–9) Aloqadan chiqib ketgan hisoblagichlar 2-7 / 7-30 / 30-90 kun / 90 kundan ortiq — hammasi nomma-nom (xodim bilan), alohida Excel.
- Eski jadval Excel fayllari (t1, t2) va 3 varaqli umumiy fayl yuklab olish uchun qoldirilgan (Telegramga standart yuborilmaydi).
- Rasm Pillow bilan chiziladi (shrift: `assets/fonts/Carlito`), Telegramga `sendPhoto` orqali, izohsiz.
- Yuborish oynasi darhol «Yuborish boshlandi» va har fayl uchun «yuborilmoqda» qatorini ko'rsatadi.

## v14 — yangi bo'lim: «Respublika dinamikasi» (barcha viloyatlar)

Qashqadaryo dinamikasidagi barcha imkoniyatlar respublika (R-Dynamic) PDF'i uchun alohida bo'lim sifatida qo'shildi.
Qashqadaryo bo'limi o'z tuman PDF'lari bilan o'zgarishsiz qoladi.

- **PDF o'qish** (`services/nation.py`): jadval chiziqsiz chizilgani uchun kataklar matn joylashuvi bo'yicha topiladi. Sahifalar: 1, 2, 3, 4, 6, 7, 9 (diagramma va SmartApp o'tkazib yuboriladi). Qatorlar: «Жами» + 14 viloyat; ↑↓ o'zgarishlar; sana «Динамика:» qatoridan.
- **Sahifa** `/respublika-dinamikasi`: oy boshidan / kunlik solishtirish, **viloyatlar reytingi** (istalgan ustun bo'yicha saralash va o'rin 1–14), **Qashqadaryo qatori ajratilgan**, PDF / Excel / asl PDF / **jadval rasmlari (ZIP)** yuklash.
- **Telegram**: PDF, Excel, asl PDF va **jadval rasmlari** (har kanalga albom/karusel) — tanlab yuboriladi.
- **Bosh sahifa**: «Respublika dinamikasi» tabi (grafiklar va viloyatlar bo'yicha reyting diagrammalari).
- **Ma'lumot yuklash**: «Respublika dinamikasi» tabi — bittadan PDF, ko'rish / yuklab olish / o'chirish. Qashqadaryo PDF'i bu yerga, respublika PDF'i Qashqadaryo bo'limiga yuklansa — aniq xato xabari chiqadi.
- **Ruxsatlar** (alohida): `nation.view`, `nation.upload`, `nation.original`. Qashqadaryo ruxsatlari (`republic.*`) bor xodimlarga bir marta avtomatik beriladi; tayyor to'plamlarga ham qo'shildi.
- Yangi jadval `nation_reports` (migratsiya 0004), fayl nomlari Sozlamalarda (`fn_nation`, `fn_nation_png`, `fn_nation_orig`). Qashqadaryo fayllari endi `Qashqadaryo_dinamikasi_{sana}` deb nomlanadi.
- Yangi bog'liqlik: `pypdfium2` (PDF sahifani rasmga aylantirish).

### v14c — PDF yuklash: ikki bosqichli jarayon (Qashqadaryo / Respublika / AG)
1. **Serverga yuklash** (progress 0–100%), 2. **PDF o'qish va bazaga yozish** orqa fonda (worker). «Yuklangan sanalar» jadvalida holat ko'rinadi: *Yuklanmoqda → Navbatda → PDF o'qilmoqda → Yuklandi* (xato bo'lsa sababi bilan, ✕ bilan yopiladi). Sahifani yopsa ham jarayon davom etadi. API: `POST /{bo'lim}/upload/start`, `GET /{bo'lim}/jobs` (eski sinxron `POST /upload` ham saqlangan). Jadval `pdf_jobs` (migratsiya 0005).
