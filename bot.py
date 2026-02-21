import asyncio
import logging
import os
import uvloop
import functools
from aiohttp import web
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from imdb import Cinemagoer

# --- Event Loop Fix for Python 3.11+ ---
uvloop.install()
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# --- Configuration ---
class Config:
    API_ID = int(os.environ.get("API_ID", "36982189")) 
    API_HASH = os.environ.get("API_HASH", "d3ec5feee7342b692e7b5370fb9c8db7")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")
    OWNER_ID = int(os.environ.get("OWNER_ID", "8072674531"))
    MONGO_URL = os.environ.get("MONGO_URL", "your_mongodb_url_here")
    MAIN_CHANNEL_LINK = os.environ.get("MAIN_CHANNEL_LINK", "https://t.me/MyAnimeEnglish")

# ==========================================
# 📝 EDIT YOUR CUSTOM TEXT HERE
# ==========================================

ABOUT_TEXT = """
ℹ️ **About MyAnimeEnglish Dub**

Welcome to the ultimate hub for English Dubbed Anime! 
We are dedicated to providing high-quality anime directly to your Telegram. 

Make sure to join our main channel to stay updated with the latest episodes, movies, and ongoing series.

**Bot created by MyAnimeEnglish Dub ⚡️**
"""

TERMS_TEXT = """
📜 **Terms & Conditions**

By using this bot and our channels, you agree to the following:
1. **No Spamming:** Do not spam the bot with constant commands.
2. **Sharing:** If you want to share our content, share the channel link, not the direct file files.
3. **Respect:** Be respectful in the comments section of our channel.
4. **Enjoy:** Grab some popcorn and enjoy the best English dubs!

**Bot created by MyAnimeEnglish Dub ⚡️**
"""

# ==========================================

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database Setup (MongoDB) ---
mongo_client = AsyncIOMotorClient(Config.MONGO_URL, serverSelectionTimeoutMS=5000)
db = mongo_client["AnimeBotDB"]
anime_collection = db["anime_list"]
users_collection = db["users"]
buttons_collection = db["extra_buttons"]

# --- Bot Client ---
app = Client(
    "AnimeGlassBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    sleep_threshold=60 
)

# --- FloodWait Handler ---
def flood_handler(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        while True:
            try:
                return await func(*args, **kwargs)
            except FloodWait as e:
                logger.warning(f"Sleeping for {e.value} seconds due to FloodWait...")
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                if len(args) > 1 and hasattr(args[1], "reply_text"):
                    try:
                        await args[1].reply_text(f"⚠️ Command Error: `{e}`")
                    except: pass
                break
    return wrapper

# --- Auto Delete Helper ---
@flood_handler
async def safe_delete(message, time=600):
    await asyncio.sleep(time)
    try:
        await message.delete()
    except Exception:
        pass

# --- IMDb API Helper ---
ia = Cinemagoer()

def fetch_imdb_sync(query):
    try:
        results = ia.search_movie(query)
        if not results:
            return None
        
        show = results[0]
        ia.update(show, info=['main'])
        
        if show.get('kind') in ['tv series', 'tv mini series', 'tv show']:
            ia.update(show, info=['episodes'])
            total_episodes = 0
            if 'episodes' in show:
                for season in show['episodes']:
                    total_episodes += len(show['episodes'][season])
            status = "TV Series"
        else:
            total_episodes = "N/A (Movie)"
            status = "Movie"

        title = show.get('title', 'Unknown')
        year = show.get('year', 'Unknown')
        rating = show.get('rating', 'N/A')
        genres = ", ".join(show.get('genres', ['Unknown']))
        
        plot = show.get('plot', ['No synopsis available.'])[0]
        if "::" in plot:
            plot = plot.split("::")[0] 
        
        poster_url = show.get('full-size cover url', "https://files.catbox.moe/dhatqa.jpg")
        imdb_id = show.getID()
        imdb_url = f"https://www.imdb.com/title/tt{imdb_id}/"

        return {
            "title": f"{title} ({year})",
            "rating": rating,
            "episodes": total_episodes,
            "status": status,
            "genres": genres,
            "synopsis": plot[:400] + "...",
            "url": imdb_url,
            "image": poster_url
        }
    except Exception as e:
        logger.error(f"IMDb Error: {e}")
        return None

async def get_imdb_details(query):
    return await asyncio.to_thread(fetch_imdb_sync, query)

# --- Render Port Binding Web Server ---
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

# --- Start Command ---
@app.on_message(filters.command("start"))
@flood_handler
async def start_command(client, message):
    user_id = message.from_user.id
    
    try:
        await users_collection.update_one(
            {"user_id": user_id}, 
            {"$set": {"name": message.from_user.first_name}}, 
            upsert=True
        )
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")

    welcome_photo = "https://w0.peakpx.com/wallpaper/433/193/HD-wallpaper-gojo-satoru-anime-jujutsu-kaisen-satoru-gojo.jpg"
    
    # Updated Welcome Text
    welcome_text = (
        f"👋 **Hello {message.from_user.mention}!**\n\n"
        f"🎉 Welcome to **MyAnimeEnglish bot**.\n"
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

# --- Main Menu ---
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

    try:
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
    except Exception:
        pass 

    # Edit the existing message back to the main menu
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        pass # Ignore if the message is already identical

# --- Basic Callbacks (Updated with Back Buttons) ---
@app.on_callback_query(filters.regex("about_info"))
async def about_handler(client, callback):
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]])
    await callback.message.edit_caption(caption=ABOUT_TEXT, reply_markup=back_btn)

@app.on_callback_query(filters.regex("terms_info"))
async def terms_handler(client, callback):
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]])
    await callback.message.edit_caption(caption=TERMS_TEXT, reply_markup=back_btn)

@app.on_callback_query(filters.regex("guide_info"))
@flood_handler
async def guide_handler(client, callback):
    await callback.message.reply_text(
        "🔎 **Anime Guide Search**\n\nSend the name of the anime you want to search for.\nExample: `/search Naruto`",
        quote=True
    )

# --- Search Command (IMDb Version) ---
@app.on_message(filters.command("search"))
@flood_handler
async def search_anime(client, message):
    if len(message.command) < 2:
        await message.reply_text("⚠️ Please provide an anime name.\nExample: `/search Jujutsu Kaisen`")
        return

    query = " ".join(message.command[1:])
    m = await message.reply_text(f"🔎 **Searching IMDb for '{query}'...**\n*(This takes a few seconds to calculate episodes)*")
    
    details = await get_imdb_details(query)
    
    if details:
        caption = (
            f"🎬 **{details['title']}**\n\n"
            f"⭐️ **IMDb Rating:** {details['rating']}/10\n"
            f"📺 **Total Episodes:** {details['episodes']}\n"
            f"📡 **Type:** {details['status']}\n"
            f"🎭 **Genres:** {details['genres']}\n\n"
            f"📖 **Synopsis:** {details['synopsis']}\n\n"
            f"**Bot created by MyAnimeEnglish Dub ⚡️**"
        )
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("More Info on IMDb", url=details['url'])]])
        
        await message.reply_photo(details['image'], caption=caption, reply_markup=btn)
        await m.delete()
    else:
        await m.edit_text("❌ Series or Movie not found on IMDb. Try checking the spelling.")

    asyncio.create_task(safe_delete(message, 600))

# --- Admin Commands ---
@app.on_message(filters.command("addanime") & filters.user(Config.OWNER_ID))
@flood_handler
async def add_anime(client, message):
    try:
        text_data = message.text.split(" ", 1)[1]
        name, link = text_data.split("|")
        await anime_collection.insert_one({"name": name.strip(), "link": link.strip()})
        await message.reply_text(f"✅ Added **{name.strip()}** to the Anime List.\nUsers will now be redirected to: {link.strip()}")
    except Exception as e:
        await message.reply_text(f"⚠️ Error. Format: `/addanime Anime Name | Post_Link`\nDB Error: {e}")

@app.on_message(filters.command("addbtn") & filters.user(Config.OWNER_ID))
@flood_handler
async def add_button(client, message):
    try:
        text_data = message.text.split(" ", 1)[1]
        name, link = text_data.split("|")
        await buttons_collection.insert_one({"name": name.strip(), "link": link.strip()})
        await message.reply_text(f"✅ Added button **{name.strip()}** to Main Menu.")
    except Exception as e:
        await message.reply_text(f"⚠️ Error. Format: `/addbtn Button Name | Link`\nDB Error: {e}")

@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
@flood_handler
async def stats_command(client, message):
    try:
        users_count = await users_collection.count_documents({})
        anime_count = await anime_collection.count_documents({})
        await message.reply_text(f"📊 **Database Stats**\n\n👥 Total Users: {users_count}\n🎬 Total Anime: {anime_count}")
    except Exception as e:
         await message.reply_text("⚠️ **Database Error!** Ensure your MongoDB URL is correct and your IP is whitelisted under Network Access in Atlas.")

# --- Pagination ---
@app.on_callback_query(filters.regex(r"anime_list_page_(\d+)"))
@flood_handler
async def anime_list_handler(client, callback):
    page = int(callback.matches[0].group(1))
    limit = 10 
    skip = page * limit
    
    try:
        total_anime = await anime_collection.count_documents({})
        cursor = anime_collection.find().skip(skip).limit(limit)
        anime_list = await cursor.to_list(length=limit)
    except Exception:
        await callback.answer("Database connection failed!", show_alert=True)
        return
    
    if not anime_list:
        await callback.answer("No anime found in the list yet. Admin needs to add them!", show_alert=True)
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
        caption=f"📂 **Anime List - Page {page+1}**\n\nClick an anime to go directly to its download/watch post in our channel.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- Main Execution ---
async def main():
    logger.info("Starting Web Server...")
    await web_server()
    logger.info("Starting Bot...")
    await app.start()
    from pyrogram import idle
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop.run_until_complete(main())
