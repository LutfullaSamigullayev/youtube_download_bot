# 🎬 YouTube Downloader Telegram Bot

YouTube video va playlistlarini MP3 audio hamda turli sifatlarda (360p, 720p HD, 1080p Full HD) yuklab beruvchi zamonaviy Telegram Bot.

## ✨ Imkoniyatlar
- 🎵 Videolardan MP3 audio ajratib olish
- 🎬 Video sifatlarini (360p, 720p HD, 1080p Full HD) tanlash
- 📚 YouTube Playlistlarini to'liq qo'llab-quvvatlash (Yakka videoni yoki butun playlistni yuklab olish)
- 📱 2-bosqichli dynamic Inline Menyu hamda "Orqaga" tugmasi
- 🏷 Video nomini media tepasida ko'rsatish (`show_caption_above_media`)
- 🧹 Muvaffaqiyatli yuklab berilgach, foydalanuvchi linkini va vaqtincha fayllarni avtomatik o'chirish

## 🛠 O'rnatish va Ishga tushirish (Local)

1. Repository-ni klon qiling:
```bash
git clone https://github.com/LutfullaSamigullayev/AI_Video_Translator_bot.git
cd AI_Video_Translator_bot
```

2. Virtual muhit yaratib, kutubxonalarni o'rnating:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. `.env` faylini yaratib, bot tokeningizni kiriting:
```env
BOT_TOKEN=your_bot_token_here
```

4. Tizim talablari:
- Tizimda `FFmpeg` o'rnatilgan va PATH da bo'lishi kerak.

5. Botni ishga tushirish:
```bash
python main.py
```

## 🚀 Render.com ga Joylash (Deployment)

1. Loyihani GitHub-ga yuklang (`git push`).
2. Render.com saytiga kiring va **New +** -> **Background Worker** (yoki **Web Service**) ni tanlang.
3. GitHub repozitoriyangizni ulaysiz.
4. **Environment** bo'limida **Docker** ni tanlaysiz (chunki Dockerfile `FFmpeg`ni avtomatik o'rnatadi).
5. **Environment Variables** bo'limida yangi o'zgaruvchi qo'shasiz:
   - **Key:** `BOT_TOKEN`
   - **Value:** `sizning_bot_tokeningiz`
6. **Create Background Worker** (yoki Web Service) tugmasini bosing.
