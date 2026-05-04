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


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        logger.warning("Invalid %s=%r, using default %s", name, raw_value, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        logger.warning("Invalid %s=%r, using default %s", name, raw_value, default)
        return default


COMPATIBILITY_VALUE_OPTIONS = [
    "🌱 Tumbuh bareng",
    "🎉 Seru-seruan",
    "🧘 Stabil & tenang",
]
COMMUNICATION_STYLE_OPTIONS = [
    "💬 Chat santai tiap hari",
    "⏳ Slow but deep",
    "📞 Suka voice/video call",
]
RELATIONSHIP_GOAL_OPTIONS = [
    "💞 Cari hubungan serius",
    "🤝 Cari teman dulu",
    "🌈 Lihat dulu cocoknya",
]

TEMP_BAN_DEFAULT_HOURS = 24
TEMP_BAN_MAX_HOURS = 24 * 30

DAILY_PROFILE_VIEW_LIMIT = max(_env_int("DAILY_PROFILE_VIEW_LIMIT", 30), 1)
MATCH_RESET_TIMEZONE = os.getenv("MATCH_RESET_TIMEZONE", "Asia/Jakarta")
ERROR_NOTICE_COOLDOWN_SECONDS = max(_env_int("ERROR_NOTICE_COOLDOWN_SECONDS", 60), 0)
AUTO_REPORT_BAN_THRESHOLD = max(_env_int("AUTO_REPORT_BAN_THRESHOLD", 3), 1)
AUTO_REPORT_BAN_DAYS = max(_env_int("AUTO_REPORT_BAN_DAYS", 3650), 1)
DISCOVER_MESSAGE_MAX_LENGTH = max(_env_int("DISCOVER_MESSAGE_MAX_LENGTH", 200), 1)

TELEGRAM_CONNECT_TIMEOUT = max(_env_float("TELEGRAM_CONNECT_TIMEOUT", 10.0), 1.0)
TELEGRAM_READ_TIMEOUT = max(_env_float("TELEGRAM_READ_TIMEOUT", 20.0), 1.0)
TELEGRAM_WRITE_TIMEOUT = max(_env_float("TELEGRAM_WRITE_TIMEOUT", 20.0), 1.0)
TELEGRAM_POOL_TIMEOUT = max(_env_float("TELEGRAM_POOL_TIMEOUT", 10.0), 1.0)
TELEGRAM_GET_UPDATES_READ_TIMEOUT = max(
    _env_float("TELEGRAM_GET_UPDATES_READ_TIMEOUT", 35.0),
    1.0,
)
TELEGRAM_SEND_RETRIES = max(_env_int("TELEGRAM_SEND_RETRIES", 2), 0)
TELEGRAM_RETRY_BASE_DELAY_SECONDS = max(
    _env_float("TELEGRAM_RETRY_BASE_DELAY_SECONDS", 0.7),
    0.1,
)

(
    NAME,
    AGE,
    GENDER,
    DESCRIPTION,
    QUIZ_VALUE,
    QUIZ_COMM_STYLE,
    QUIZ_RELATIONSHIP_GOAL,
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
    ADMIN_BROADCAST,
) = range(22)
