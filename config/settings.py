from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    raise ValueError("DATABASE_URL must be set in environment")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY") # Optional fallback
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL") # Optional
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
IMAGE_OUTPUT_DIR = os.getenv("IMAGE_OUTPUT_DIR", "output/images")
IMAGE_SIZE = (1080, 1350)
TOP_N_ARTICLES = int(os.getenv("TOP_N_ARTICLES", "30"))
FONT_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts')
