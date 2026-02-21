import asyncio
import logging
import os
import uvloop
import functools
import aiohttp
from aiohttp import web
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait

# --- Event Loop Optimization ---
uvloop.install()
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# --- Configuration ---
class Config:
    API_ID = int(os.environ.get("API_ID", "36982189")) 
    API_HASH = os.environ.get("API_HASH", "d3ec5feee7342b692e7b5370fb9c8db7")
    BOT_TOKEN = "8291835114:AAGK6S_9DCp_ZZbZQUQEuMArh8SccI-CeSk"
    OWNER_ID = 8072674531
    MONGO_URL = "mongodb+srv://leech:leech123@cluster0.fdnowvo.mongodb.net/?appName=Cluster0"
    
    MAIN_CHANNEL_LINK = "https://t.me/MyAnimeEnglish"
    INSTAGRAM_LINK = "https://" 
    TWITTER_LINK = "https://"     
    YOUTUBE_LINK = "https://"   
    
    RAPIDAPI_KEY = "aa36f42fa4msh06760066288f27cp13edaejsn640d7527de2d"

# --- Professional Text Blocks ---
ABOUT_TEXT = """
✨ **MyAnimeEnglish Dub** ✨

Your premier destination for high-quality **English Dubbed Anime**! 🎬 
We bring you the latest episodes, movies, and series directly to Telegram in HD.

🌟 **Why Choose Us?**
🔥 High Quality Dubs
🚀 Fast Uploads
📂 Organized Playlists

Join our community and dive into the world of anime! 🎌
"""

TERMS_TEXT = """
📜 **MyAnimeEnglish - Terms & Conditions**

1️⃣ **No Spam:** Repeated commands will result in a temporary ban. 🚫
2️⃣ **Support Us:** Please share our channel links instead of direct files. 🤝
3️⃣ **Respect:** Maintain a positive vibe in our community. ✨
4️⃣ **Content:** All files are for personal viewing only. 🍿

Enjoy your stay and keep watching! ⚔️
"""

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database ---
mongo_client = AsyncIOMotorClient(Config.MONGO_URL, serverSelectionTimeoutMS=5000)
db = mongo_client["AnimeBotDB"]
anime_collection = db["anime_list"]
users_collection = db["users"]
buttons_collection = db["extra_buttons"]

app = Client("AnimeGlassBot", api_id=Config.API_ID, api_hash=Config.API_HASH, bot_token=Config.BOT_TOKEN)

# --- Helpers ---
def flood_handler(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        while True:
            try: return await func(*args, **kwargs)
            except FloodWait as e: await asyncio.sleep(e.value + 1)
            except Exception as e: logger.error(f"Error: {e}"); break
    return wrapper

@flood_handler
async def safe_delete(message, time=600):
    await asyncio.sleep(time)
    try: await message.delete()
    except: pass

async def get_imdb_details(query):
    url = "https://imdb-com.p.rapidapi.com/auto-complete"
    headers = {"X-RapidAPI-Key": Config.RAPIDAPI_KEY, "X-RapidAPI-Host": "imdb-com.p.rapidapi.com"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params={"q": query}) as resp:
                data = await resp.json()
                if data and 'd' in data:
                    item = data['d'][0]
                    return {
                        "title": item.get('l'), 
                        "year": item.get('y'), 
                        "id": item.get('id'), 
                        "image": item.get('i', {}).get('imageUrl', "https://i.postimg.cc/pL5ZYCwc/photo-2026-02-21-16-00-36.jpg")
                    }
    except: return None

async def web_server():
    async def handle(r): return web.Response(text="MyAnimeEnglish Bot Active")
    web_app = web.Application(); web_app.router.add_get("/", handle)
    runner = web.AppRunner(web_app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080))).start()

# --- Handlers ---
@app.on_message(filters.command("start"))
@flood_handler
async def start(c, m):
    try: await users_collection.update_one({"user_id": m.from_user.id}, {"$set": {"name": m.from_user.first_name}}, upsert=True)
    except: pass
    welcome_photo = "https://i.postimg.cc/pL5ZYCwc/photo-2026-02-21-16-00-36.jpg"
    welcome_text = (
        f"✨🎌 **Konnichiwa, {m.from_user.mention}!** 🎌✨\n\n"
        f"🎊 **Welcome to MyAnimeEnglish bot!** 🎊\n"
        f"🎬 *Your destination for HD English Dubbed Anime* 🍿⚔️\n\n"
        f"🤖 **Status:** 🟢 *Online & Ready!* ⚡️\n\n"
        f"📣 Please follow our official social media channels to support us! 🚀"
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Instagram", url=Config.INSTAGRAM_LINK), InlineKeyboardButton("🐦 Twitter", url=Config.TWITTER_LINK)],
        [InlineKeyboardButton("▶️ YouTube", url=Config.YOUTUBE_LINK), InlineKeyboardButton("✈️ Telegram", url=Config.MAIN_CHANNEL_LINK)],
        [InlineKeyboardButton("➡️ SKIP / CONTINUE ➡️", callback_data="main_menu")]
    ])
    await m.reply_photo(photo=welcome_photo, caption=welcome_text, reply_markup=buttons)

@app.on_callback_query(filters.regex("main_menu"))
async def menu(c, cb):
    await cb.answer() # Snappy UI Fix
    buttons = [
        [InlineKeyboardButton("🔍 Guide", callback_data="guide_info"), InlineKeyboardButton("📂 List", callback_data="anime_list_page_0")],
        [InlineKeyboardButton("📢 Channel", url=Config.MAIN_CHANNEL_LINK), InlineKeyboardButton("ℹ️ About", callback_data="about_info")],
        [InlineKeyboardButton("📜 Terms", callback_data="terms_info")]
    ]
    extra = await buttons_collection.find().to_list(10)
    for btn in extra: buttons.append([InlineKeyboardButton(btn['name'], url=btn['link'])])
    await cb.message.edit_caption(caption="⛩ **Main Menu** ⛩\n\nSelect an option below to browse.", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("search"))
@flood_handler
async def search(c, m):
    if len(m.command) < 2: return await m.reply("Usage: `/search Naruto`")
    query = m.text.split(None, 1)[1].lower().replace("nyaa", "").strip()
    status_msg = await m.reply("🔎 **Searching MyAnimeEnglish Database...**")
    res = await get_imdb_details(query)
    if res:
        cap = f"🎬 **MyAnimeEnglish Search Results**\n\n📌 **Title:** `{res['title']}`\n📅 **Year:** `{res['year']}`\n\n✅ **More Details:** Search this title in our channel for download links! 🚀"
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View on IMDb", url=f"https://www.imdb.com/title/{res['id']}") ]])
        sent = await m.reply_photo(res['image'], caption=cap, reply_markup=btn)
        await status_msg.delete()
        asyncio.create_task(safe_delete(sent, 600))
    else: await status_msg.edit("❌ Anime not found. Try again!")

@app.on_message(filters.command("broadcast") & filters.user(Config.OWNER_ID))
async def broadcast(c, m):
    if not m.reply_to_message: return await m.reply("Reply to a message to broadcast it.")
    users = await users_collection.find().to_list(None)
    sent, failed = 0, 0
    msg = await m.reply(f"🚀 **Broadcasting to {len(users)} users...**")
    for user in users:
        try:
            await m.reply_to_message.copy(user['user_id'])
            sent += 1
            await asyncio.sleep(0.3) # Prevent flood ban during broadcast
        except: failed += 1
    await msg.edit(f"✅ **Broadcast Finished!**\n\nSuccessful: {sent}\nFailed: {failed}")

@app.on_message(filters.command("addanime") & filters.user(Config.OWNER_ID))
async def add_anime(c, m):
    try:
        n, l = m.text.split(" ", 1)[1].split("|")
        await anime_collection.insert_one({"name": n.strip(), "link": l.strip()})
        await m.reply(f"✅ Added **{n.strip()}** to the list.")
    except: await m.reply("Format: `/addanime Name | Link`")

@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats(c, m):
    u = await users_collection.count_documents({}); a = await anime_collection.count_documents({})
    await m.reply(f"📊 **MyAnimeEnglish Stats**\n\nUsers: {u}\nAnime in List: {a}")

@app.on_callback_query(filters.regex("guide_info"))
async def guide_cb(c, cb):
    await cb.answer()
    guide_text = "🔎 **MyAnimeEnglish Guide**\n\nTo find your favorite anime, use the search command below!\n\n**Command:** `/search [Anime Name]`\n**Example:** `/search Jujutsu Kaisen`"
    await cb.message.edit_caption(caption=guide_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

@app.on_callback_query(filters.regex("about_info"))
async def about_cb(c, cb):
    await cb.answer()
    await cb.message.edit_caption(caption=ABOUT_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

@app.on_callback_query(filters.regex("terms_info"))
async def terms_cb(c, cb):
    await cb.answer()
    await cb.message.edit_caption(caption=TERMS_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

@app.on_callback_query(filters.regex(r"anime_list_page_(\d+)"))
async def list_pg(c, cb):
    page = int(cb.matches[0].group(1))
    total = await anime_collection.count_documents({})
    items = await anime_collection.find().skip(page*10).limit(10).to_list(10)
    if not items: 
        return await cb.answer("The list is empty!", show_alert=True)
    await cb.answer()
    btns = [[InlineKeyboardButton(f"🎬 {i['name']}", url=i['link'])] for i in items]
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"anime_list_page_{page-1}"))
    nav.append(InlineKeyboardButton("🏠 Menu", callback_data="main_menu"))
    if total > (page+1)*10: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"anime_list_page_{page+1}"))
    btns.append(nav)
    await cb.message.edit_caption(caption=f"📂 **Anime List - Page {page+1}**", reply_markup=InlineKeyboardMarkup(btns))

async def main():
    await web_server()
    await app.start()
    from pyrogram import idle
    await idle()

if __name__ == "__main__":
    loop.run_until_complete(main())
