import logging
import os

from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

MONGODB_URI = os.environ["MONGODB_URI"]
DB_NAME = "love_match"
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

ADMIN_USERNAMES = ["rrscriptt", "romiscript"]
ADMIN_USERNAMES = [username.strip().lstrip("@").lower() for username in ADMIN_USERNAMES]
ADMIN_TELEGRAM_IDS = [
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")
    if user_id.strip().isdigit()
]

REPORT_REASON_OPTIONS = [
    "🚫 Spam/Iklan",
    "💸 Penipuan",
    "🔞 Konten Tidak Pantas",
    "🤬 Pelecehan/Kasar",
    "❓ Lainnya",
    "❌ Batal Report",
]
REPORT_REASON_PATTERN = "^(🚫 Spam/Iklan|💸 Penipuan|🔞 Konten Tidak Pantas|🤬 Pelecehan/Kasar|❓ Lainnya|❌ Batal Report)$"

TEMP_BAN_DEFAULT_HOURS = 24
TEMP_BAN_MAX_HOURS = 24 * 30

(
    NAME,
    AGE,
    GENDER,
    DESCRIPTION,
    LOCATION,
    PHOTO,
    EDIT_CHOICE,
    EDIT_NAME,
    EDIT_AGE,
    EDIT_GENDER,
    EDIT_DESCRIPTION,
    EDIT_LOCATION,
    EDIT_PHOTO,
    ADMIN_ACTION,
    ADMIN_VIEW_USER,
    ADMIN_DELETE_CONFIRM,
    ADMIN_RESOLVE_REPORT,
    ADMIN_TEMP_BAN,
) = range(18)
