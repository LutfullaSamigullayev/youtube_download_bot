import asyncio
import html
import os
import re
from urllib.parse import urlparse, parse_qs
import yt_dlp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message, FSInputFile
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! .env fayli yoki environment variable tekshiring.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def sanitize_filename(name: str) -> str:
    """Fayl nomidan taqiqlangan belgilarni tozalash."""
    cleaned = re.sub(r'[\\/*?:"<>|]', '', name).strip()
    return cleaned[:100] if cleaned else "media"

def parse_youtube_url(url: str) -> tuple[str | None, str | None]:
    """(video_id, playlist_id) juftligini qaytaradi."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    video_id = query.get('v', [None])[0]
    playlist_id = query.get('list', [None])[0]

    # youtu.be/e1ph88N7DII?list=... kabi havolalar uchun
    if not video_id and 'youtu.be' in parsed.netloc:
        path_parts = parsed.path.strip('/').split('/')
        if path_parts and path_parts[0]:
            video_id = path_parts[0]

    return video_id, playlist_id

def get_ydl_base_opts() -> dict:
    """yt-dlp uchun asosiy optionlarni tayyorlash (Cloud Server IP bot cheklovlarini aylanib o'tish uchun)."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'mweb']
            }
        }
    }
    cookies_env = os.getenv("YOUTUBE_COOKIES")
    if cookies_env and not os.path.exists("cookies.txt"):
        try:
            with open("cookies.txt", "w", encoding="utf-8") as f:
                f.write(cookies_env)
        except Exception:
            pass
    if os.path.exists("cookies.txt"):
        opts['cookiefile'] = 'cookies.txt'
    return opts

def get_video_info(url: str) -> dict:
    """yt-dlp orqali yakka video ma'lumotlarini olish (noplaylist=True)."""
    ydl_opts = get_ydl_base_opts()
    ydl_opts['noplaylist'] = True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'id': info.get('id'),
            'title': info.get('title', 'YouTube Video'),
            'duration': info.get('duration', 0),
            'url': info.get('webpage_url', url)
        }

def get_playlist_info(playlist_id: str) -> dict:
    """yt-dlp orqali playlist haqida umumiy ma'lumot va barcha videolar ro'yxatini olish."""
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    ydl_opts = get_ydl_base_opts()
    ydl_opts['extract_flat'] = True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        entries = info.get('entries', [])
        valid_entries = []
        for e in entries:
            if e and e.get('id'):
                valid_entries.append({
                    'id': e.get('id'),
                    'title': e.get('title', 'YouTube Video')
                })
        return {
            'id': info.get('id', playlist_id),
            'title': info.get('title', 'YouTube Playlist'),
            'count': len(valid_entries),
            'entries': valid_entries
        }

def download_media(url: str, fmt: str, output_prefix: str) -> tuple[str, str]:
    """
    yt-dlp orqali tanlangan formatda (MP3 yoki Video) media yuklab olish.
    Qaytargan qiymat: (fayl_yo'li, video_nomi)
    """
    outtmpl = f"{output_prefix}.%(ext)s"
    base_opts = get_ydl_base_opts()
    
    if fmt == 'mp3':
        ydl_opts = {
            **base_opts,
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'YouTube Audio')
        return f"{output_prefix}.mp3", title
    else:
        height_map = {
            '360': '360',
            '720': '720',
            '1080': '1080'
        }
        max_height = height_map.get(fmt, '720')
        ydl_opts = {
            **base_opts,
            'format': f'bestvideo[ext=mp4][height<={max_height}]+bestaudio[ext=m4a]/best[ext=mp4][height<={max_height}]/best',
            'outtmpl': outtmpl,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'YouTube Video')
        
        # Yuklangan fayl kengaytmasini aniqlash
        for ext in ['mp4', 'mkv', 'webm']:
            fpath = f"{output_prefix}.{ext}"
            if os.path.exists(fpath):
                return fpath, title
        return f"{output_prefix}.mp4", title

def get_step1_playlist_keyboard(video_id: str | None, playlist_id: str, user_msg_id: int) -> InlineKeyboardMarkup:
    """1-BOSQICH MENYU: Faqat ushbu video yoki Butun playlistni tanlash."""
    vid_param = video_id if video_id else "none"
    buttons = []
    if video_id:
        buttons.append([
            InlineKeyboardButton(text="📹 Faqat ushbu videoni yuklash", callback_data=f"m:s:{vid_param}:{playlist_id}:{user_msg_id}")
        ])
    buttons.append([
        InlineKeyboardButton(text="📚 Butun Playlistni yuklash", callback_data=f"m:p:{playlist_id}:{vid_param}:{user_msg_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"dl:cancel:{user_msg_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_single_video_keyboard(video_id: str, user_msg_id: int, playlist_id: str | None = None) -> InlineKeyboardMarkup:
    """2-BOSQICH MENYU (Yakka Video): MP3, 360p, 720p, 1080p formatlari."""
    buttons = [
        [
            InlineKeyboardButton(text="🎵 MP3 (Audio)", callback_data=f"dl:mp3:{video_id}:{user_msg_id}"),
        ],
        [
            InlineKeyboardButton(text="🎬 360p", callback_data=f"dl:360:{video_id}:{user_msg_id}"),
            InlineKeyboardButton(text="🎬 720p HD", callback_data=f"dl:720:{video_id}:{user_msg_id}"),
            InlineKeyboardButton(text="🎬 1080p Full HD", callback_data=f"dl:1080:{video_id}:{user_msg_id}"),
        ]
    ]
    bottom_row = []
    if playlist_id:
        bottom_row.append(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"m:b:{playlist_id}:{video_id}:{user_msg_id}"))
    bottom_row.append(InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"dl:cancel:{user_msg_id}"))
    buttons.append(bottom_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_playlist_formats_keyboard(playlist_id: str, user_msg_id: int, video_id: str | None = None) -> InlineKeyboardMarkup:
    """2-BOSQICH MENYU (Butun Playlist): MP3, 360p, 720p, 1080p formatlari."""
    vid_param = video_id if video_id else "none"
    buttons = [
        [
            InlineKeyboardButton(text="🎵 MP3 (Audio)", callback_data=f"pldl:mp3:{playlist_id}:{user_msg_id}"),
        ],
        [
            InlineKeyboardButton(text="🎬 360p", callback_data=f"pldl:360:{playlist_id}:{user_msg_id}"),
            InlineKeyboardButton(text="🎬 720p HD", callback_data=f"pldl:720:{playlist_id}:{user_msg_id}"),
            InlineKeyboardButton(text="🎬 1080p Full HD", callback_data=f"pldl:1080:{playlist_id}:{user_msg_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"m:b:{playlist_id}:{vid_param}:{user_msg_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"dl:cancel:{user_msg_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def format_duration(seconds: int) -> str:
    """Sekundlarni daqiqa va sekund formatiga o'tkazish."""
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}s {minutes}m {sec}s"
    return f"{minutes}m {sec}s"

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Assalomu alaykum! YouTube video yoki playlist havolasini yuboring, uni MP3 audio yoki video ko'rinishida yuklab beraman.")

@dp.message()
async def process_video_url(message: Message):
    url = message.text.strip()
    if not ("youtube.com" in url or "youtu.be" in url):
        await message.answer("Iltimos, haqiqiy YouTube havolasini yuboring.")
        return

    status_msg = await message.answer("🔍 Ma'lumotlar olinmoqda, iltimos kuting...")

    video_id, playlist_id = parse_youtube_url(url)

    try:
        if playlist_id:
            # 1-BOSQICH: Playlist va Video haqida ma'lumot olish
            playlist_info = await asyncio.to_thread(get_playlist_info, playlist_id)
            pl_title = html.escape(playlist_info['title'])
            pl_count = playlist_info['count']

            if video_id:
                v_info = await asyncio.to_thread(get_video_info, f"https://www.youtube.com/watch?v={video_id}")
                v_title = html.escape(v_info['title'])
                duration_str = format_duration(v_info['duration'])

                text = (
                    f"🎬 <b>Video:</b> {v_title} ({duration_str})\n"
                    f"📚 <b>Playlist:</b> {pl_title} ({pl_count} ta video)\n\n"
                    f"👇 <i>Nimani yuklab olmoqchisiz?</i>"
                )
            else:
                text = (
                    f"📚 <b>Playlist:</b> {pl_title}\n"
                    f"📊 <b>Jami videolar:</b> {pl_count} ta\n\n"
                    f"👇 <i>Nimani yuklab olmoqchisiz?</i>"
                )

            await status_msg.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=get_step1_playlist_keyboard(video_id, playlist_id, message.message_id)
            )
        else:
            # Oddiy yakka video havolasi kelganda (playlist yo'q)
            info = await asyncio.to_thread(get_video_info, url)
            v_id = info['id']
            title = info['title']
            duration_str = format_duration(info['duration'])

            safe_title = html.escape(title)
            text = (
                f"🎬 <b>{safe_title}</b>\n"
                f"⏱ <b>Davomiyligi:</b> {duration_str}\n\n"
                f"👇 <i>Iltimos, kerakli format yoki sifatni tanlang:</i>"
            )

            await status_msg.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=get_single_video_keyboard(v_id, message.message_id)
            )
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

# ----------------- MENYU NAVIGATSIYASI -----------------

@dp.callback_query(F.data.startswith("m:s:"))
async def menu_single_video_selected(callback: CallbackQuery):
    """1-BOSQICH: 'Faqat ushbu videoni yuklash' bosilganda 2-bosqich formatlar menyusini ochish."""
    parts = callback.data.split(":")
    if len(parts) != 5:
        await callback.answer("Noto'g'ri so'rov!", show_alert=True)
        return

    video_id = parts[2]
    playlist_id = parts[3]
    user_msg_id = int(parts[4])

    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        info = await asyncio.to_thread(get_video_info, url)
        safe_title = html.escape(info['title'])
        duration_str = format_duration(info['duration'])
        text = (
            f"🎬 <b>{safe_title}</b>\n"
            f"⏱ <b>Davomiyligi:</b> {duration_str}\n\n"
            f"👇 <i>Ushbu video uchun format yoki sifatni tanlang:</i>"
        )
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_single_video_keyboard(video_id, user_msg_id, playlist_id)
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

@dp.callback_query(F.data.startswith("m:p:"))
async def menu_playlist_selected(callback: CallbackQuery):
    """1-BOSQICH: 'Butun Playlistni yuklash' bosilganda 2-bosqich playlist formatlar menyusini ochish."""
    parts = callback.data.split(":")
    if len(parts) != 5:
        await callback.answer("Noto'g'ri so'rov!", show_alert=True)
        return

    playlist_id = parts[2]
    video_id = parts[3] if parts[3] != "none" else None
    user_msg_id = int(parts[4])

    try:
        playlist_info = await asyncio.to_thread(get_playlist_info, playlist_id)
        pl_title = html.escape(playlist_info['title'])
        pl_count = playlist_info['count']

        text = (
            f"📚 <b>{pl_title}</b>\n"
            f"📊 <b>Jami videolar:</b> {pl_count} ta\n\n"
            f"👇 <i>Butun playlist uchun format yoki sifatni tanlang:</i>"
        )
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_playlist_formats_keyboard(playlist_id, user_msg_id, video_id)
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

@dp.callback_query(F.data.startswith("m:b:"))
async def menu_back_to_step1(callback: CallbackQuery):
    """2-BOSQICH: 'Orqaga' bosilganda 1-bosqich menyusiga qaytish."""
    parts = callback.data.split(":")
    if len(parts) != 5:
        await callback.answer("Noto'g'ri so'rov!", show_alert=True)
        return

    playlist_id = parts[2]
    video_id = parts[3] if parts[3] != "none" else None
    user_msg_id = int(parts[4])

    try:
        playlist_info = await asyncio.to_thread(get_playlist_info, playlist_id)
        pl_title = html.escape(playlist_info['title'])
        pl_count = playlist_info['count']

        if video_id:
            v_info = await asyncio.to_thread(get_video_info, f"https://www.youtube.com/watch?v={video_id}")
            v_title = html.escape(v_info['title'])
            duration_str = format_duration(v_info['duration'])

            text = (
                f"🎬 <b>Video:</b> {v_title} ({duration_str})\n"
                f"📚 <b>Playlist:</b> {pl_title} ({pl_count} ta video)\n\n"
                f"👇 <i>Nimani yuklab olmoqchisiz?</i>"
            )
        else:
            text = (
                f"📚 <b>Playlist:</b> {pl_title}\n"
                f"📊 <b>Jami videolar:</b> {pl_count} ta\n\n"
                f"👇 <i>Nimani yuklab olmoqchisiz?</i>"
            )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_step1_playlist_keyboard(video_id, playlist_id, user_msg_id)
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

# ----------------- YUKLAB OLISH HANDLERLARI -----------------

@dp.callback_query(F.data.startswith("pldl:"))
async def process_playlist_download_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("Noto'g'ri so'rov!", show_alert=True)
        return

    fmt = parts[1]
    playlist_id = parts[2]
    user_msg_id = int(parts[3])

    fmt_labels = {
        'mp3': 'MP3 (Audio)',
        '360': '360p Video',
        '720': '720p HD Video',
        '1080': '1080p Full HD Video'
    }
    fmt_name = fmt_labels.get(fmt, fmt)

    await callback.answer(f"Playlist ({fmt_name}) yuklash boshlandi.")
    await callback.message.edit_text(f"⏳ Playlist ma'lumotlari olinmoqda...", parse_mode="HTML")

    try:
        playlist_info = await asyncio.to_thread(get_playlist_info, playlist_id)
        entries = playlist_info['entries']
        total = len(entries)

        if total == 0:
            await callback.message.edit_text("❌ Playlistda videolar topilmadi.")
            return

        sent_count = 0
        for i, entry in enumerate(entries, 1):
            v_id = entry['id']
            v_title = entry['title']
            safe_v_title = html.escape(v_title)

            await callback.message.edit_text(
                f"⏳ Playlist yuklanmoqda (<b>{i}/{total}</b>):\n"
                f"🎬 <i>{safe_v_title}</i>",
                parse_mode="HTML"
            )

            v_url = f"https://www.youtube.com/watch?v={v_id}"
            output_prefix = f"media_{callback.from_user.id}_{callback.message.message_id}_{i}"
            downloaded_file = None

            try:
                downloaded_file, fetched_title = await asyncio.to_thread(download_media, v_url, fmt, output_prefix)

                if os.path.exists(downloaded_file):
                    file_size = os.path.getsize(downloaded_file)
                    if file_size <= 50 * 1024 * 1024:
                        clean_name = sanitize_filename(fetched_title)
                        ext = "mp3" if fmt == 'mp3' else downloaded_file.split('.')[-1]
                        custom_filename = f"{clean_name}.{ext}"

                        file_input = FSInputFile(downloaded_file, filename=custom_filename)
                        caption_text = f"🎵 ({i}/{total}) <b>{html.escape(fetched_title)}</b>" if fmt == 'mp3' else f"🎬 ({i}/{total}) <b>{html.escape(fetched_title)}</b>"

                        if fmt == 'mp3':
                            await callback.message.answer_audio(
                                audio=file_input,
                                title=fetched_title,
                                caption=caption_text,
                                parse_mode="HTML",
                                show_caption_above_media=True
                            )
                        else:
                            await callback.message.answer_video(
                                video=file_input,
                                caption=caption_text,
                                parse_mode="HTML",
                                show_caption_above_media=True
                            )
                        sent_count += 1
                    else:
                        await callback.message.answer(
                            f"⚠️ ({i}/{total}) <b>{safe_v_title}</b> hajmi 50MB dan katta bo'lgani uchun o'tkazib yuborildi.",
                            parse_mode="HTML"
                        )
            except Exception as item_err:
                await callback.message.answer(f"⚠️ ({i}/{total}) Yuklashda xatolik: {str(item_err)}")
            finally:
                if downloaded_file and os.path.exists(downloaded_file):
                    os.remove(downloaded_file)

        await callback.message.answer(f"✅ Playlist muvaffaqiyatli yakunlandi! Jami {sent_count}/{total} ta media yuborildi.")

        # Link xabarini va status xabarini o'chirish
        try:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=user_msg_id)
        except Exception:
            pass
    except Exception as e:
        await callback.message.answer(f"❌ Playlist yuklashda xatolik yuz berdi: {str(e)}")
    finally:
        try:
            await callback.message.delete()
        except Exception:
            pass

@dp.callback_query(F.data.startswith("dl:cancel"))
async def cancel_download(callback: CallbackQuery):
    await callback.answer("Amaliyot bekor qilindi.")
    await callback.message.edit_text("❌ Yuklab olish bekor qilindi.")

@dp.callback_query(F.data.startswith("dl:"))
async def process_download_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("Noto'g'ri so'rov!", show_alert=True)
        return

    fmt = parts[1]
    video_id = parts[2]
    user_msg_id = int(parts[3])
    url = f"https://www.youtube.com/watch?v={video_id}"

    fmt_labels = {
        'mp3': 'MP3 (Audio)',
        '360': '360p Video',
        '720': '720p HD Video',
        '1080': '1080p Full HD Video'
    }
    fmt_name = fmt_labels.get(fmt, fmt)

    await callback.answer(f"{fmt_name} tanlandi.")
    await callback.message.edit_text(f"⏳ <b>{fmt_name}</b> formatida yuklab olinmoqda, iltimos kuting...", parse_mode="HTML")

    output_prefix = f"media_{callback.from_user.id}_{callback.message.message_id}"
    downloaded_file = None

    try:
        downloaded_file, title = await asyncio.to_thread(download_media, url, fmt, output_prefix)

        if not os.path.exists(downloaded_file):
            await callback.message.answer("❌ Fayl yuklab olinmadi.")
            return

        file_size = os.path.getsize(downloaded_file)
        # Telegram Bot API 50MB yuklash cheklovi
        if file_size > 50 * 1024 * 1024:
            size_mb = file_size / (1024 * 1024)
            await callback.message.answer(
                f"⚠️ Fayl hajmi juda katta ({size_mb:.1f} MB).\n"
                f"Telegram bot faqat 50 MB gacha bo'lgan fayllarni yubora oladi.\n"
                f"Iltimos, pastroq sifatni (masalan 360p yoki MP3) tanlab ko'ring."
            )
            return

        safe_title = html.escape(title)
        caption_text = f"🎬 <b>{safe_title}</b>" if fmt != 'mp3' else f"🎵 <b>{safe_title}</b>"

        clean_name = sanitize_filename(title)
        ext = "mp3" if fmt == 'mp3' else downloaded_file.split('.')[-1]
        custom_filename = f"{clean_name}.{ext}"

        file_input = FSInputFile(downloaded_file, filename=custom_filename)

        if fmt == 'mp3':
            await callback.message.answer_audio(
                audio=file_input,
                title=title,
                caption=caption_text,
                parse_mode="HTML",
                show_caption_above_media=True
            )
        else:
            await callback.message.answer_video(
                video=file_input,
                caption=caption_text,
                parse_mode="HTML",
                show_caption_above_media=True
            )

        # Muvaffaqiyatli yuklangach, foydalanuvchi yuborgan link xabarini botdan o'chirish
        try:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=user_msg_id)
        except Exception:
            pass

    except Exception as e:
        await callback.message.answer(f"❌ Yuklab olishda xatolik yuz berdi: {str(e)}")
    finally:
        try:
            await callback.message.delete()
        except Exception:
            pass
        if downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)

from aiohttp import web

async def handle_health_check(request):
    return web.Response(text="Bot is running live!")

async def start_health_check_server():
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    app.router.add_get('/health', handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await start_health_check_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())