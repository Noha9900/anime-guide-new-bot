import asyncio
import logging
import os
import uvloop
from aiohttp import web
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait

from config import Config

uvloop.install()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mongo_client = AsyncIOMotorClient(Config.MONGO_URL)
db = mongo_client["AnimeBotDB"]
anime_collection = db["anime_list"]
users_collection = db["users"]
buttons_collection = db["extra_buttons"]

app = Client(
    "AnimeGlassBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    sleep_threshold=60 
)

def flood_handler(func):
    async def wrapper(*args, **kwargs):
        while True:
            try:
                return await func(*args, **kwargs)
            except FloodWait as e:
                logger.warning(f"Sleeping for {e.value} seconds due to FloodWait...")
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                break
    return wrapper

@flood_handler
async def safe_delete(message, time=600):
    await asyncio.sleep(time)
    await message.delete()

async def get_anime_details(query):
    url = f"https://api.jikan.moe/v4/anime?q={query}&limit=1"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if data.get('data'):
                return data['data'][0]
    return None

async def web_server():
    async def handle(request):
        return web.Response(text="Anime Bot is running ultra-fast!")
    
    web_app = web.Application()
    web_app.router.add_get("/", handle)
    runner = web.AppRunner(web_app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server started on port {port}")

@app.on_message(filters.command("start"))
@flood_handler
async def start_command(client, message):
    user_id = message.from_user.id
    
    await users_collection.update_one(
        {"user_id": user_id}, 
        {"$set": {"name": message.from_user.first_name}}, 
        upsert=True
    )

    welcome_photo = "https://i.pinimg.com/originals/82/32/73/82327341cb82442488a03362a2656360.gif"
    
    welcome_text = (
        f"👋 **Hello {message.from_user.mention}!**\n\n"
        f"🎉 Welcome to the **Advanced Anime Bot**.\n"
        f"🤖 **Status:** Online & Ready\n\n"
        f"Please follow us on social media to continue or press Skip."
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📸 Instagram", url="https://instagram.com"),
            InlineKeyboardButton("🐦 Twitter", url="https://twitter.com")
        ],
        [
            InlineKeyboardButton("▶️ YouTube", url="https://youtube.com"),
            InlineKeyboardButton("✈️ Telegram", url=Config.MAIN_CHANNEL_LINK)
        ],
        [
            InlineKeyboardButton("➡️ SKIP / CONTINUE ➡️", callback_data="main_menu")
        ]
    ])

    sent_msg = await message.reply_photo(
        photo=welcome_photo,
        caption=welcome_text,
        reply_markup=buttons
    )
    
    asyncio.create_task(safe_delete(message, 600))
    asyncio.create_task(safe_delete(sent_msg, 600))

@app.on_callback_query(filters.regex("main_menu"))
@flood_handler
async def main_menu(client, callback: CallbackQuery):
    text = (
        "⛩ **Main Menu** ⛩\n\n"
        "Select an option below to browse anime, get info, or check our channels.\n\n"
        "**Bot created by MyAnimeEnglish Dub ⚡️**"
    )
    
    buttons = [
        [
            InlineKeyboardButton("🔍 Anime Guide (IMDb)", callback_data="guide_info"),
            InlineKeyboardButton("📂 Anime List", callback_data="anime_list_page_0")
        ],
        [
            InlineKeyboardButton("📢 Main Channel", url=Config.MAIN_CHANNEL_LINK),
            InlineKeyboardButton("ℹ️ Channel About", callback_data="about_info")
        ],
        [
             InlineKeyboardButton("📜 Terms & Conditions", callback_data="terms_info")
        ]
    ]

    extra_btns = await buttons_collection.find().to_list(length=10)
    if extra_btns:
        temp_row = []
        for btn in extra_btns:
            temp_row.append(InlineKeyboardButton(btn['name'], url=btn['link']))
            if len(temp_row) == 2:
                buttons.append(temp_row)
                temp_row = []
        if temp_row:
            buttons.append(temp_row)

    await callback.message.edit_caption(
        caption=text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex("about_info"))
async def about_handler(client, callback):
    await callback.answer("We provide the best Anime in English Dub!", show_alert=True)

@app.on_callback_query(filters.regex("terms_info"))
async def terms_handler(client, callback):
    await callback.answer("1. Do not spam.\n2. Enjoy the anime.", show_alert=True)

@app.on_callback_query(filters.regex("guide_info"))
@flood_handler
async def guide_handler(client, callback):
    await callback.message.reply_text(
        "🔎 **Anime Guide Search**\n\nSend the name of the anime you want to search for.\nExample: `/search Naruto`",
        quote=True
    )

@app.on_message(filters.command("search"))
@flood_handler
async def search_anime(client, message):
    if len(message.command) < 2:
        await message.reply_text("⚠️ Please provide an anime name.\nExample: `/search Jujutsu Kaisen`")
        return

    query = " ".join(message.command[1:])
    m = await message.reply_text("🔎 **Searching Database...**")
    
    details = await get_anime_details(query)
    
    if details:
        title = details.get('title', 'Unknown')
        score = details.get('score', 'N/A')
        episodes = details.get('episodes', 'Unknown')
        status = details.get('status', 'Unknown')
        synopsis = details.get('synopsis', 'No synopsis available.')[:400] + "..."
        url = details.get('url')
        img_url = details['images']['jpg']['large_image_url']
        
        caption = (
            f"🎬 **{title}**\n\n"
            f"⭐️ **Score:** {score}/10\n"
            f"📺 **Episodes:** {episodes}\n"
            f"📡 **Status:** {status}\n\n"
            f"📖 **Synopsis:** {synopsis}\n\n"
            f"**Bot created by MyAnimeEnglish Dub ⚡️**"
        )
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("More Info (MAL)", url=url)]])
        
        await message.reply_photo(img_url, caption=caption, reply_markup=btn)
        await m.delete()
    else:
        await m.edit_text("❌ Anime not found. Try checking the spelling.")

    asyncio.create_task(safe_delete(message, 600))

@app.on_message(filters.command("addanime") & filters.user(Config.OWNER_ID))
@flood_handler
async def add_anime(client, message):
    try:
        text_data = message.text.split(" ", 1)[1]
        name, link = text_data.split("|")
        await anime_collection.insert_one({"name": name.strip(), "link": link.strip()})
        await message.reply_text(f"✅ Added **{name.strip()}** to the Anime List.")
    except Exception:
        await message.reply_text("⚠️ Error. Format: `/addanime Anime Name | Post_Link`")

@app.on_message(filters.command("addbtn") & filters.user(Config.OWNER_ID))
@flood_handler
async def add_button(client, message):
    try:
        text_data = message.text.split(" ", 1)[1]
        name, link = text_data.split("|")
        await buttons_collection.insert_one({"name": name.strip(), "link": link.strip()})
        await message.reply_text(f"✅ Added button **{name.strip()}** to Main Menu.")
    except Exception:
        await message.reply_text("⚠️ Error. Format: `/addbtn Button Name | Link`")

@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
@flood_handler
async def stats_command(client, message):
    users_count = await users_collection.count_documents({})
    anime_count = await anime_collection.count_documents({})
    await message.reply_text(f"📊 **Database Stats**\n\n👥 Total Users: {users_count}\n🎬 Total Anime: {anime_count}")

@app.on_callback_query(filters.regex(r"anime_list_page_(\d+)"))
@flood_handler
async def anime_list_handler(client, callback):
    page = int(callback.matches[0].group(1))
    limit = 10 
    skip = page * limit
    
    total_anime = await anime_collection.count_documents({})
    cursor = anime_collection.find().skip(skip).limit(limit)
    anime_list = await cursor.to_list(length=limit)
    
    if not anime_list:
        await callback.answer("No anime found!", show_alert=True)
        return

    buttons = []
    row = []
    for anime in anime_list:
        row.append(InlineKeyboardButton(f"🎬 {anime['name']}", url=anime['link']))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"anime_list_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton("🏠 Home", callback_data="main_menu"))
    if total_anime > skip + limit:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"anime_list_page_{page+1}"))
    
    buttons.append(nav_buttons)

    await callback.message.edit_caption(
        caption=f"📂 **Anime List - Page {page+1}**\n\nClick to go to the download/watch post.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def main():
    logger.info("Starting Web Server...")
    await web_server()
    logger.info("Starting Bot...")
    await app.start()
    from pyrogram import idle
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
