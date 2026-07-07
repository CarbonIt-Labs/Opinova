import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

DATA_DIR = os.getenv("DATA_DIR", "data")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
