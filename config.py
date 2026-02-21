import os

class Config:
    # Your Telegram API Credentials
    API_ID = int(os.environ.get("API_ID", "12345678")) 
    API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
    
    # Your Bot Token from @BotFather
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")
    
    # Your Telegram ID for Admin commands
    OWNER_ID = int(os.environ.get("OWNER_ID", "8072674531"))
    
    # MongoDB Connection String (from MongoDB Atlas)
    MONGO_URL = os.environ.get("MONGO_URL", "your_mongodb_url_here")
    
    # Your Channel Link
    MAIN_CHANNEL_LINK = os.environ.get("MAIN_CHANNEL_LINK", "https://t.me/YourChannel")
