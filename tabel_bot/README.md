# Buono Tabel — xodimlar nazorati boti

Xodimlar ishga kelganda va smenani tugatib ketayotganda **Buono Tabel** guruhiga yumaloq video
yuborishadi. Bot shu videolar orqali kim qachon kelib-ketganini qayd etadi, kechikkanlarni
ogohlantiradi va har kuni hisobot yuboradi.

> Bu alohida bot. Repodagi `bot.py` (mijozlar fikri boti) bilan bog'liq emas va unga tegmaydi.

## Bot nima qiladi

- **Har bir videoga javob beradi** va xodimni belgilaydi (tag):
  - vaqtida kelsa — «👏 Ofarin, Ali! O'z vaqtida keldingiz, rahmat!»
  - kechiksa — «⚠️ Ali, siz 17 daqiqa kechikib keldingiz. Bu yaxshi emas, keyingi safar kechikmasdan keling!»
  - smena tugamasdan ketsa — «⚠️ … smenani 25 daqiqa erta tugatdingiz …»
  - vaqtida ketsa — «✅ … smenangiz yakunlandi. Rahmat, yaxshi dam oling!»
- **10:00, 14:00, 20:00** — tegishli smena hisoboti: necha kishi keldi, kim vaqtida, kim necha daqiqa kechikdi.
- **07:30** — kechagi 3 smena bo'yicha to'liq hisobot: har smenada kimlar va necha kishi ishladi,
  kim kechikdi, kim erta ketdi, kim ketish videosini yubormadi.
- Rahbarlar uchun: istalgan kun hisoboti, oylik statistika, xodimlar ro'yxati va xatolarni tuzatish.

## Qoidalar

| Smena | Ish vaqti | Hisobot vaqti | Kelish videosi shu oraliqda bo'lsa |
|---|---|---|---|
| 🌅 1-smena | 08:30–18:30 | 10:00 | 04:30–11:00 |
| ☀️ O'rta smena | 12:00–00:00 | 14:00 | 11:00–16:30 |
| 🌙 2-smena | 18:30–04:30 | 20:00 | 16:30–04:30 |

- **Kechikish:** 5 daqiqagacha ruxsat. 08:30 dagi smenaga 08:35 da kelsa — vaqtida, 08:36 da — kechikdi.
  Vaqt Telegram ko'rsatgandek daqiqagacha olinadi (08:35:59 → 08:35).
- **Kelish va ketish:** xodimning videosi — *kelish*; smena ochiq bo'lsa, keyingi videosi — *ketish*.
- **Smena** kelish vaqtiga qarab aniqlanadi (jadvaldagi oxirgi ustun). Bot adashsa, rahbar `/smena` bilan tuzatadi.
- Kelgandan keyin **30 daqiqa ichida** yuborilgan yana bir video takroriy hisoblanadi (ketish emas).
- Ketish videosi yuborilmasa, hisobotda «❓ ketish videosi yuborilmagan» deb chiqadi. Smena tugaganidan
  6 soat o'tgach, xodimning keyingi videosi yangi kelish hisoblanadi.
- **Forward qilingan** video qabul qilinmaydi. Oddiy (yumaloq bo'lmagan) video yuborilsa, bot eslatadi.
- Vaqt Toshkent vaqti bo'yicha, video yuborilgan paytdan olinadi. Bot vaqtincha o'chiq bo'lsa ham,
  yoqilgach (24 soat ichida) videolar asl vaqti bilan qayd etiladi, o'tib ketgan hisobot esa 2 soat ichida yuboriladi.

Bu qiymatlarning hammasi `tabel/config.py` da, xabar matnlari esa `tabel/texts.py` da — o'zgartirish oson.

## O'rnatish

1. **Yangi bot yarating:** [@BotFather](https://t.me/BotFather) → `/newbot` → tokenni oling.
   Tokenni kodga yozmang — faqat `.env` fayliga yoki server sozlamalariga.
2. **Botni guruhga qo'shing** va **admin** qiling (maxsus huquqlar shart emas). Admin bo'lmasa,
   bot videolarni ko'rmaydi. Muqobil yo'l: @BotFather → `/setprivacy` → `Disable`.
3. **Botni ishga tushiring** (Python 3.11+):
   ```bash
   cd tabel_bot
   pip install -r requirements.txt
   cp .env.example .env      # BOT_TOKEN ni yozing
   python main.py
   ```
4. **Guruhni ulang:** guruh egasi yoki admini guruhda `/ulash` deb yozadi.
5. Tayyor. Rahbar botga shaxsiy chatda `/start` yozsa, barcha buyruqlarni ko'radi.

**Rahbar kim?** Buono Tabel guruhining egasi va adminlari (avtomatik), hamda `ADMIN_IDS` dagi foydalanuvchilar.

## Sozlamalar (`.env`)

| O'zgaruvchi | Majburiy | Tavsif |
|---|---|---|
| `BOT_TOKEN` | ha | @BotFather bergan token |
| `ADMIN_IDS` | yo'q | Qo'shimcha rahbarlar ID si, vergul bilan. ID ni botga `/id` yozib bilasiz |
| `GROUP_ID` | yo'q | Guruh ID si — `/ulash` o'rniga |
| `REPORT_CHAT_IDS` | yo'q | Hisobotlar qo'shimcha yuboriladigan chatlar (masalan, rahbarning shaxsiy chati; u avval botga `/start` yozgan bo'lishi kerak) |
| `REPORTS_TO_GROUP` | yo'q | `1` — hisobotlar guruhga ham boradi (standart), `0` — faqat `REPORT_CHAT_IDS` ga |
| `DB_PATH` | yo'q | Ma'lumotlar bazasi fayli (standart: `tabel_bot/tabel.db`) |

## Buyruqlar

**Hisobotlar** (rahbarlar; shaxsiy chatda yoki guruhda):

| Buyruq | Nima qiladi |
|---|---|
| `/bugun` | Bugungi holat (ish kuni 04:30 da almashadi, shuning uchun tunda davom etayotgan 2-smena ham ko'rinadi) |
| `/kecha` | Kechagi to'liq hisobot (07:30 dagi bilan bir xil) |
| `/hisobot 28.09.2026` | Tanlangan kun hisoboti |
| `/oylik` yoki `/oylik 09.2026` | Oylik statistika: har bir xodim nechta smena ishladi, necha marta kechikdi, erta ketdi |
| `/xodimlar` | Xodimlar ro'yxati (birinchi videosidan keyin avtomatik qo'shiladi) |

**Tuzatishlar** (rahbarlar; guruhda xodimning videosiga yoki botning javobiga *reply* qilib):

| Buyruq | Qachon kerak |
|---|---|
| `/smena 1`, `/smena 2`, `/smena orta` | Bot smenani noto'g'ri aniqlagan bo'lsa (kechikish qayta hisoblanadi) |
| `/keldi` | Video «ketish» yoki «takroriy» deb olingan, aslida kelish edi |
| `/ketdi` | Video yangi «kelish» deb olingan, aslida ketish edi |
| `/ochir` | Kelish videosiga — yozuvni o'chiradi; ketish videosiga — faqat ketish belgisini o'chiradi |
| `/ism Aliyev Vali` | Xodimning hisobotlardagi ismini o'zgartiradi |

**Sozlash:** `/ulash` — guruhni ulash (guruhda), `/id` — chat va foydalanuvchi ID si, `/start` — yordam.

## Serverga joylash

Bot doim (24/7) ishlab turishi kerak. Bitta token bilan bot faqat **bitta joyda** ishga tushirilsin,
aks holda Telegram `Conflict` xatosini beradi.

**VPS (Ubuntu) + systemd** — `/etc/systemd/system/tabel-bot.service`:

```ini
[Unit]
Description=Buono Tabel bot
After=network-online.target

[Service]
WorkingDirectory=/opt/buonoFBbot/tabel_bot
ExecStart=/opt/buonoFBbot/tabel_bot/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Keyin: `sudo systemctl enable --now tabel-bot` va loglar: `journalctl -u tabel-bot -f`.

**Railway, Render va shunga o'xshash platformalar:** yangi servis yarating, *Root Directory* — `tabel_bot`,
ishga tushirish buyrug'i — `python main.py` (`Procfile` tayyor), o'zgaruvchilarni (`BOT_TOKEN` va h.k.)
servis sozlamalariga yozing.
**Muhim:** bunday platformalarda qayta deploy qilinganda fayllar o'chib ketadi. Ma'lumotlar saqlanishi
uchun doimiy disk (Volume) ulang, masalan `/data` ga, va `DB_PATH=/data/tabel.db` qiling.

## Testlar

```bash
pip install -r requirements-dev.txt
pytest
```

Testlar botni internetsiz, soxta Telegram serveri bilan boshidan oxirigacha tekshiradi.

## Tuzilishi

```
tabel_bot/
├── main.py            # ishga tushirish: python main.py
├── tabel/
│   ├── config.py      # smena vaqtlari, qoidalar, .env
│   ├── texts.py       # bot xabarlari
│   ├── shifts.py      # smena va vaqt hisob-kitobi
│   ├── attendance.py  # kelish/ketish mantig'i va tuzatishlar
│   ├── reports.py     # hisobotlar
│   ├── scheduler.py   # avtomatik hisobot jadvali
│   ├── handlers.py    # Telegram buyruqlari va videolar
│   ├── storage.py     # SQLite baza
│   └── sender.py      # xabar yuborish yordamchilari
└── tests/
```
