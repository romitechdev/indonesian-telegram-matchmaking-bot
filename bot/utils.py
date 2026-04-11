import asyncio
from html import escape
from datetime import datetime, timedelta, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Awaitable, Callable, TypeVar
from zoneinfo import ZoneInfo

from telegram.error import NetworkError, RetryAfter, TimedOut

from .config import (
    ADMIN_TELEGRAM_IDS,
    MATCH_RESET_TIMEZONE,
    TELEGRAM_RETRY_BASE_DELAY_SECONDS,
    TELEGRAM_SEND_RETRIES,
    logger,
)


ResultType = TypeVar("ResultType")


def _resolve_match_timezone():
    try:
        return ZoneInfo(MATCH_RESET_TIMEZONE)
    except Exception:
        return timezone.utc


MATCH_RESET_TZ = _resolve_match_timezone()


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


def escape_html(value):
    """Escape dynamic text for Telegram HTML parse mode."""
    if value is None:
        return ""
    return escape(str(value), quote=False)


def build_match_chat_draft(sender_name):
    """Build default Lovematch chat opener with sender name when available."""
    clean_name = " ".join(str(sender_name or "").strip().split())
    if clean_name:
        return f"Hai! Aku {clean_name} dari Lovematchbot ❤️"
    return "Hai! Aku dari Lovematchbot ❤️"


def build_profile_link_by_id(telegram_id):
    """Build Telegram profile link by numeric ID."""
    if telegram_id is None:
        return None
    return f"tg://user?id={telegram_id}"


def is_admin(user):
    """Check if user is admin by telegram ID"""
    if not user:
        return False
    return user.id in ADMIN_TELEGRAM_IDS


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


def get_local_day_key(reference_time=None):
    """Return local day key (YYYY-MM-DD) based on configured reset timezone."""
    current_time = ensure_utc(reference_time or now_utc())
    return current_time.astimezone(MATCH_RESET_TZ).date().isoformat()


def get_local_day_window(reference_time=None):
    """Return UTC start/end timestamps for current local day window."""
    current_time = ensure_utc(reference_time or now_utc())
    local_time = current_time.astimezone(MATCH_RESET_TZ)
    day_start_local = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
    next_day_start_local = day_start_local + timedelta(days=1)
    return (
        day_start_local.astimezone(timezone.utc),
        next_day_start_local.astimezone(timezone.utc),
    )


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


async def telegram_call_with_retry(
    call_factory: Callable[[], Awaitable[ResultType]],
) -> ResultType:
    max_attempts = TELEGRAM_SEND_RETRIES + 1
    for attempt in range(1, max_attempts + 1):
        try:
            return await call_factory()
        except RetryAfter as exc:
            if attempt >= max_attempts:
                raise
            retry_after_seconds = float(getattr(exc, "retry_after", 0) or 0)
            delay_seconds = max(retry_after_seconds, TELEGRAM_RETRY_BASE_DELAY_SECONDS)
        except (TimedOut, NetworkError):
            if attempt >= max_attempts:
                raise
            delay_seconds = TELEGRAM_RETRY_BASE_DELAY_SECONDS * attempt

        logger.warning(
            "Telegram request retry (%s/%s), waiting %.2fs",
            attempt,
            max_attempts,
            delay_seconds,
        )
        await asyncio.sleep(delay_seconds)

    raise RuntimeError("Unreachable retry path")
