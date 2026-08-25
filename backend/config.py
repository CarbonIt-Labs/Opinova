import os
from dotenv import load_dotenv

load_dotenv()

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
DATA_DIR = os.getenv("DATA_DIR", "data")
LOG_FILE = os.path.join(DATA_DIR, "activity.log")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))

# Optimization Settings
DUPLICATE_SIMILARITY_THRESHOLD = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", 90.0))
MIN_FEEDBACK_LENGTH = int(os.getenv("MIN_FEEDBACK_LENGTH", 3))
IGNORED_PHRASES = set(os.getenv("IGNORED_PHRASES", "ok,good,fine,nice,yes,no,n/a,-,none").lower().split(","))
LANGUAGE_WHITELIST = set(os.getenv("LANGUAGE_WHITELIST", "en").split(","))

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
