import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot tokens
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "")
    ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/threadai")
    DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
    DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "5"))
    
    # AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Stripe
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
    # For platforms like Vercel where API is under /api, set PUBLIC_BASE_PATH="/api"
    PUBLIC_BASE_PATH = os.getenv("PUBLIC_BASE_PATH", "")
    
    # Admin IDs
    ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
    
    # Other settings
    FREE_CARD_COOLDOWN_HOURS = 24
    SESSION_TIMEOUT_MINUTES = 15

    # Crystal packages (counts and prices in cents)
    CRYSTALS_PROBE = int(os.getenv("CRYSTALS_PROBE", "10"))
    CRYSTALS_STANDARD = int(os.getenv("CRYSTALS_STANDARD", "50"))
    CRYSTALS_PREMIUM = int(os.getenv("CRYSTALS_PREMIUM", "100"))

    PRICE_PROBE_CENTS = int(os.getenv("PRICE_PROBE_CENTS", "199"))
    PRICE_STANDARD_CENTS = int(os.getenv("PRICE_STANDARD_CENTS", "799"))
    PRICE_PREMIUM_CENTS = int(os.getenv("PRICE_PREMIUM_CENTS", "1299"))

    # Tarot costs in crystals
    TAROT_QUICK_COST = int(os.getenv("TAROT_QUICK_COST", "10"))
    TAROT_DEEP_COST = int(os.getenv("TAROT_DEEP_COST", "25"))
