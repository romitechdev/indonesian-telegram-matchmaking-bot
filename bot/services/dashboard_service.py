from datetime import timedelta

from bson.objectid import ObjectId

from ..config import AUTO_REPORT_BAN_THRESHOLD, DAILY_PROFILE_VIEW_LIMIT
from .moderation_service import moderation_service
from ..repositories.reports import report_repository
from ..repositories.seen_profiles import seen_profile_repository
from ..repositories.users import user_repository
from ..utils import (
    format_username,
    format_utc,
    get_local_day_key,
    get_local_day_window,
    is_temporarily_banned,
    now_utc,
)


class DashboardService:
    def __init__(
        self,
        users_repo,
        reports_repo,
        moderation,
        seen_repo,
    ):
        self.users_repo = users_repo
        self.reports_repo = reports_repo
        self.moderation = moderation
        self.seen_repo = seen_repo

    @staticmethod
    def _current_day_context():
        current_time = now_utc()
        day_key = get_local_day_key(current_time)
        day_start, day_end = get_local_day_window(current_time)
        return day_key, day_start, day_end

    def _daily_view_count(self, telegram_id: int | None) -> int:
        if telegram_id is None:
            return 0
        day_key, day_start, day_end = self._current_day_context()
        return self.seen_repo.count_viewed_for_day(telegram_id, day_key, day_start, day_end)

    def _approved_report_count(self, telegram_id: int | None) -> int:
        if telegram_id is None:
            return 0
        return self.reports_repo.count_by_reported_telegram_id(telegram_id, "approved")

    def _open_report_count(self, telegram_id: int | None) -> int:
        if telegram_id is None:
            return 0
        return self.reports_repo.count_by_reported_telegram_id(telegram_id, "open")

    def _rejected_report_count(self, telegram_id: int | None) -> int:
        if telegram_id is None:
            return 0
        return self.reports_repo.count_by_reported_telegram_id(telegram_id, "rejected")

    def get_summary(self):
        total_users = self.users_repo.count_all()
        active_users = self.users_repo.count_active()
        inactive_users = total_users - active_users
        gender_stats = self.users_repo.aggregate_gender_stats()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "banned_users": self.users_repo.count_temporarily_banned(now_utc()),
            "total_reports": self.reports_repo.count_all(),
            "open_reports": self.reports_repo.count_open(),
            "approved_reports": self.reports_repo.count_by_status("approved"),
            "rejected_reports": self.reports_repo.count_by_status("rejected"),
            "gender_stats": [
                {
                    "gender": item.get("_id") or "(tanpa data)",
                    "count": item.get("count", 0),
                }
                for item in gender_stats
            ],
            "auto_ban_threshold": AUTO_REPORT_BAN_THRESHOLD,
            "generated_at": format_utc(now_utc()),
        }

    def list_recent_users(self, page: int = 1, per_page: int = 20):
        total_items = self.users_repo.count_all()
        current_page = max(page, 1)
        total_pages = max((total_items + per_page - 1) // per_page, 1)
        if current_page > total_pages:
            current_page = total_pages

        skip = (current_page - 1) * per_page
        rows = []
        for user in self.users_repo.list_recent(limit=per_page, skip=skip):
            latitude = user.get("latitude")
            longitude = user.get("longitude")
            telegram_id = user.get("telegram_id")
            daily_views_used = self._daily_view_count(telegram_id)
            rows.append(
                {
                    "id": str(user.get("_id")),
                    "telegram_id": telegram_id if telegram_id is not None else "-",
                    "name": user.get("name", "(tanpa nama)"),
                    "age": user.get("age", "-"),
                    "gender": user.get("gender", "-"),
                    "username": format_username(user.get("username")),
                    "active": "Ya" if user.get("is_active", True) else "Tidak",
                    "is_banned": is_temporarily_banned(user),
                    "ban_until": format_utc(user.get("ban_until")) if user.get("ban_until") else "-",
                    "created_at": format_utc(user.get("created_at")),
                    "latitude": latitude,
                    "longitude": longitude,
                    "maps_url": self._build_maps_url(latitude, longitude),
                    "approved_reports_count": self._approved_report_count(telegram_id),
                    "open_reports_count": self._open_report_count(telegram_id),
                    "daily_views_used": daily_views_used,
                    "daily_views_remaining": max(DAILY_PROFILE_VIEW_LIMIT - daily_views_used, 0),
                }
            )
        return {
            "items": rows,
            "page": current_page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_prev": current_page > 1,
            "has_next": current_page < total_pages,
            "prev_page": current_page - 1,
            "next_page": current_page + 1,
        }

    def list_recent_reports(self, limit: int = 20):
        return self.moderation.list_reports_enriched(
            limit,
            query={"status": {"$ne": "rejected"}},
        )

    def review_report(self, report_id_text: str, action: str, reviewed_by="dashboard_web"):
        return self.moderation.review_report(report_id_text, action, reviewed_by)

    def apply_bulk_user_action(
        self,
        user_id_texts: list[str],
        action: str,
        ban_hours: int = 24,
        reason: str = "Moderasi via dashboard web",
    ):
        parsed_ids = []
        invalid_ids = 0

        for user_id_text in set(user_id_texts):
            try:
                parsed_ids.append(ObjectId(user_id_text.strip()))
            except Exception:
                invalid_ids += 1

        if not parsed_ids:
            return {
                "ok": False,
                "level": "error",
                "message": "Tidak ada user valid yang dipilih.",
            }

        action = (action or "").strip().lower()

        if action == "delete":
            result = self.users_repo.delete_many_by_object_ids(parsed_ids)
            return {
                "ok": True,
                "level": "warn",
                "message": (
                    f"Hapus massal selesai. Target: {len(parsed_ids)} | "
                    f"Terhapus: {result.deleted_count} | ID tidak valid: {invalid_ids}"
                ),
            }

        if action == "ban":
            if ban_hours < 1:
                ban_hours = 1
            if ban_hours > 24 * 30:
                ban_hours = 24 * 30

            current_time = now_utc()
            updates = {
                "ban_until": current_time + timedelta(hours=ban_hours),
                "ban_reason": reason or "Moderasi via dashboard web",
                "banned_at": current_time,
                "banned_by": "dashboard_web",
                "auto_report_ban": False,
                "auto_report_ban_count": 0,
                "last_updated": current_time,
            }
            result = self.users_repo.update_many_by_object_ids(parsed_ids, updates)
            return {
                "ok": True,
                "level": "warn",
                "message": (
                    f"Ban massal selesai. Target: {len(parsed_ids)} | "
                    f"Terupdate: {result.modified_count} | ID tidak valid: {invalid_ids}"
                ),
            }

        if action == "unban":
            updates = {
                "ban_until": None,
                "ban_reason": None,
                "banned_at": None,
                "banned_by": None,
                "auto_report_ban": False,
                "auto_report_ban_count": 0,
                "last_updated": now_utc(),
            }
            result = self.users_repo.update_many_by_object_ids(parsed_ids, updates)
            return {
                "ok": True,
                "level": "ok",
                "message": (
                    f"Unban massal selesai. Target: {len(parsed_ids)} | "
                    f"Terupdate: {result.modified_count} | ID tidak valid: {invalid_ids}"
                ),
            }

        return {
            "ok": False,
            "level": "error",
            "message": "Aksi tidak dikenal. Pilih ban, unban, atau delete.",
        }

    def reset_user_daily_limit(self, user_id_text: str):
        try:
            object_id = ObjectId(user_id_text.strip())
        except Exception:
            return {"ok": False, "level": "error", "message": "Format user ID tidak valid."}

        user = self.users_repo.find_by_object_id(object_id)
        if not user:
            return {"ok": False, "level": "error", "message": "User tidak ditemukan."}

        telegram_id = user.get("telegram_id")
        if telegram_id is None:
            return {
                "ok": False,
                "level": "error",
                "message": "User ini tidak punya Telegram ID, limit harian tidak bisa direset.",
            }

        day_key, day_start, day_end = self._current_day_context()
        result = self.seen_repo.delete_viewed_for_day(telegram_id, day_key, day_start, day_end)
        return {
            "ok": True,
            "level": "ok",
            "message": (
                f"Limit harian {user.get('name', '(tanpa nama)')} direset. "
                f"Profil hari ini yang dihapus dari riwayat: {result.deleted_count}"
            ),
        }

    def get_user_detail(self, user_id_text: str):
        try:
            object_id = ObjectId(user_id_text.strip())
        except Exception:
            return None

        user = self.users_repo.find_by_object_id(object_id)
        if not user:
            return None

        latitude = user.get("latitude")
        longitude = user.get("longitude")
        telegram_id = user.get("telegram_id")
        daily_views_used = self._daily_view_count(telegram_id)

        return {
            "id": str(user.get("_id")),
            "telegram_id": telegram_id if telegram_id is not None else "-",
            "name": user.get("name", "(tanpa nama)"),
            "age": user.get("age", "-"),
            "gender": user.get("gender", "-"),
            "username": format_username(user.get("username")),
            "description": user.get("description") or "(tidak ada bio)",
            "compatibility_value": user.get("compatibility_value") or "-",
            "compatibility_communication_style": user.get("compatibility_communication_style") or "-",
            "compatibility_relationship_goal": user.get("compatibility_relationship_goal") or "-",
            "is_active": user.get("is_active", True),
            "is_banned": is_temporarily_banned(user),
            "ban_until": format_utc(user.get("ban_until")) if user.get("ban_until") else "-",
            "ban_reason": user.get("ban_reason") or "-",
            "age_group": user.get("age_group") or "-",
            "created_at": format_utc(user.get("created_at")),
            "last_updated": format_utc(user.get("last_updated")),
            "last_seen": format_utc(user.get("last_seen")),
            "latitude": latitude,
            "longitude": longitude,
            "maps_url": self._build_maps_url(latitude, longitude),
            "approved_reports_count": self._approved_report_count(telegram_id),
            "open_reports_count": self._open_report_count(telegram_id),
            "rejected_reports_count": self._rejected_report_count(telegram_id),
            "daily_views_used": daily_views_used,
            "daily_view_limit": DAILY_PROFILE_VIEW_LIMIT,
            "daily_views_remaining": max(DAILY_PROFILE_VIEW_LIMIT - daily_views_used, 0),
            "auto_ban_threshold": AUTO_REPORT_BAN_THRESHOLD,
        }

    @staticmethod
    def _build_maps_url(latitude, longitude):
        if latitude is None or longitude is None:
            return None
        return f"https://www.google.com/maps?q={latitude},{longitude}"


dashboard_service = DashboardService(
    users_repo=user_repository,
    reports_repo=report_repository,
    moderation=moderation_service,
    seen_repo=seen_profile_repository,
)
