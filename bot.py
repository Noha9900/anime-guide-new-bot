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
    RAPIDAPI_KEY = "aa36f42fa4msh06760066288f27cp13edaejsn640d7527de2d"

# --- Text Blocks ---
ABOUT_TEXT = "✨ **MyAnimeEnglish Dub** ✨\nYour destination for HD English Dubbed Anime!🎬\nJoin our channel for series and movies."
TERMS_TEXT = "📜 **MyAnimeEnglish - Terms**\n1️⃣ No Spam 🚫\n2️⃣ Support us by sharing links! 🤝\n3️⃣ Stay respectful. ✨"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database ---
mongo_client = AsyncIOMotorClient(Config.MONGO_URL, serverSelectionTimeoutMS=5000)
db = mongo_client["AnimeBotDB"]
anime_collection = db["anime_list"]
users_collection = db["users"]
buttons_collection = db["extra_buttons"]

app = Client("AnimeGlassBot", api_id=Config.API_ID, api_hash=Config.API_HASH, bot_token=Config.BOT_TOKEN)

# --- Logic Helpers ---
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
    async def handle(r): return web.Response(text="Bot Active")
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
    welcome_text = f"✨🎌 **Konnichiwa, {m.from_user.mention}!** 🎌✨\n\nWelcome to **MyAnimeEnglish bot!** 🎬"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✈️ Join Channel", url=Config.MAIN_CHANNEL_LINK)],
        [InlineKeyboardButton("➡️ SKIP / CONTINUE ➡️", callback_data="main_menu")]
    ])
    await m.reply_photo(photo=welcome_photo, caption=welcome_text, reply_markup=buttons)

@app.on_callback_query(filters.regex("main_menu"))
async def menu(c, cb):
    await cb.answer()
    buttons = [
        [InlineKeyboardButton("🔍 Guide (IMDb)", callback_data="guide_info"), InlineKeyboardButton("📂 My Anime List", callback_data="anime_list_page_0")],
        [InlineKeyboardButton("📢 Channel", url=Config.MAIN_CHANNEL_LINK), InlineKeyboardButton("ℹ️ About", callback_data="about_info")],
        [InlineKeyboardButton("📜 Terms", callback_data="terms_info")]
    ]
    extra = await buttons_collection.find().to_list(10)
    for btn in extra: buttons.append([InlineKeyboardButton(btn['name'], url=btn['link'])])
    await cb.message.edit_caption(caption="⛩ **Main Menu** ⛩", reply_markup=InlineKeyboardMarkup(buttons))

# --- Global Guide Search (IMDb) ---
@app.on_message(filters.command("search"))
@flood_handler
async def search(c, m):
    if len(m.command) < 2: return await m.reply("Usage: `/search Naruto`")
    query = m.text.split(None, 1)[1].lower().replace("nyaa", "").strip()
    status_msg = await m.reply("🔎 **Searching Global IMDb Database...**")
    res = await get_imdb_details(query)
    if res:
        cap = f"🎬 **Global Anime Guide**\n\n📌 **Title:** `{res['title']}`\n📅 **Year:** `{res['year']}`\n\n✅ Search this title in our channel for download links! 🚀"
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View on IMDb", url=f"https://www.imdb.com/title/{res['id']}") ]])
        sent = await m.reply_photo(res['image'], caption=cap, reply_markup=btn)
        await status_msg.delete()
        asyncio.create_task(safe_delete(sent, 600))
    else: await status_msg.edit("❌ Anime not found in database!")

# --- Admin Controls ---
@app.on_message(filters.command("addanime") & filters.user(Config.OWNER_ID))
async def add_anime(c, m):
    try:
        n, l = m.text.split(" ", 1)[1].split("|")
        await anime_collection.insert_one({"name": n.strip(), "link": l.strip()})
        await m.reply(f"✅ Added **{n.strip()}** to your Anime List.")
    except: await m.reply("Format: `/addanime Name | Link`")

@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats(c, m):
    u = await users_collection.count_documents({}); a = await anime_collection.count_documents({})
    await m.reply(f"📊 **Stats**\n\nUsers: {u}\nAnime in List: {a}")

# --- Navigation Handlers ---
@app.on_callback_query(filters.regex("guide_info"))
async def guide_cb(c, cb):
    await cb.answer()
    await cb.message.edit_caption(caption="🔎 **Global Guide**\n\nSearch any anime to see its details and release year.\n\n**Command:** `/search [Anime Name]`\n**Example:** `/search Naruto`", 
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

@app.on_callback_query(filters.regex(r"anime_list_page_(\d+)"))
async def list_pg(c, cb):
    page = int(cb.matches[0].group(1))
    total = await anime_collection.count_documents({})
    items = await anime_collection.find().skip(page*10).limit(10).to_list(10)
    if not items: return await cb.answer("Your channel list is currently empty!", show_alert=True)
    await cb.answer()
    
    # Create buttons for your channel posts
    btns = [[InlineKeyboardButton(f"🎬 {i['name']}", url=i['link'])] for i in items]
    
    # Page Navigation Logic
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"anime_list_page_{page-1}"))
    nav.append(InlineKeyboardButton("🏠 Menu", callback_data="main_menu"))
    if total > (page+1)*10: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"anime_list_page_{page+1}"))
    btns.append(nav)
    
    await cb.message.edit_caption(caption=f"📂 **My Channel List - Page {page+1}**\n\nThese are the anime uploaded in our channel.", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query(filters.regex("about_info"))
async def about_cb(c, cb):
    await cb.answer(); await cb.message.edit_caption(caption=ABOUT_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

@app.on_callback_query(filters.regex("terms_info"))
async def terms_cb(c, cb):
    await cb.answer(); await cb.message.edit_caption(caption=TERMS_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

async def main():
    await web_server(); await app.start(); from pyrogram import idle; await idle()

if __name__ == "__main__":
    loop.run_until_complete(main())
