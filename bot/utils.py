from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt

from .config import ADMIN_TELEGRAM_IDS, ADMIN_USERNAMES


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula"""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 6371 * c


def normalize_username(username):
    """Normalize Telegram username for storage/comparison"""
    if not username:
        return None
    normalized = username.strip().lstrip("@").lower()
    return normalized or None


def format_username(username):
    """Format username for user-facing messages"""
    normalized = normalize_username(username)
    if not normalized:
        return "tidak ada username"
    return f"@{normalized}"


def is_admin(user):
    """Check if user is admin by username or telegram ID"""
    if not user:
        return False

    if user.id in ADMIN_TELEGRAM_IDS:
        return True

    normalized = normalize_username(user.username)
    if not normalized:
        return False
    return normalized in ADMIN_USERNAMES


def now_utc():
    """Return current UTC time (timezone-aware)"""
    return datetime.now(timezone.utc)


def ensure_utc(value):
    """Ensure datetime value is timezone-aware UTC"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_utc(value):
    """Format datetime value in UTC for UI messages"""
    normalized = ensure_utc(value)
    if not normalized:
        return "-"
    return normalized.strftime("%d/%m/%Y %H:%M UTC")


def is_temporarily_banned(profile):
    """Check whether user profile is currently under temporary ban"""
    if not profile:
        return False
    ban_until = ensure_utc(profile.get("ban_until"))
    if not ban_until:
        return False
    return ban_until > now_utc()


def get_ban_notice(profile):
    """Build human-readable ban notice for user"""
    ban_until = ensure_utc(profile.get("ban_until"))
    reason = profile.get("ban_reason", "Pelanggaran aturan komunitas")
    if not ban_until:
        return "Akun kamu sedang dibatasi oleh admin."
    return (
        "⛔ Akun kamu sedang dibatasi sementara.\n"
        f"Sampai: {format_utc(ban_until)}\n"
        f"Alasan: {reason}"
    )


def not_banned_query(reference_time=None):
    """Mongo query fragment to include only not-banned users"""
    current_time = reference_time or now_utc()
    return {
        "$or": [
            {"ban_until": {"$exists": False}},
            {"ban_until": None},
            {"ban_until": {"$lte": current_time}},
        ]
    }


def get_target_gender(gender):
    """Return strict opposite binary gender for matching"""
    if gender == "Cowok":
        return "Cewek"
    if gender == "Cewek":
        return "Cowok"
    return None


def get_age_group(age):
    """Group ages for better matching"""
    if age < 18:
        return "teen"
    if age < 25:
        return "young_adult"
    return "adult"


def get_current_match(context):
    """Get currently displayed match in active search session"""
    matches = context.user_data.get("matches")
    current_index = context.user_data.get("current_match_index")

    if not matches or current_index is None:
        return None
    if current_index < 0 or current_index >= len(matches):
        return None
    return matches[current_index]
