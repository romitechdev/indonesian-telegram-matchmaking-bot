from datetime import timedelta

from bson.objectid import ObjectId

from ..config import AUTO_REPORT_BAN_THRESHOLD, DAILY_PROFILE_VIEW_LIMIT
from .moderation_service import moderation_service
from ..repositories.reports import report_repository
from ..repositories.seen_profiles import seen_profile_repository
from ..repositories.users import user_repository
from ..repositories.matches import match_repository
from ..utils import (
    format_username,
    format_utc,
    get_local_day_key,
    get_local_day_window,
    is_temporarily_banned,
    now_utc,
)

from ..repositories.chat_events import chat_event_repository


class DashboardService:
    def __init__(
        self,
        users_repo,
        reports_repo,
        moderation,
        seen_repo,
        matches_repo,
        chat_events_repo,
    ):
        self.users_repo = users_repo
        self.reports_repo = reports_repo
        self.moderation = moderation
        self.seen_repo = seen_repo
        self.matches_repo = matches_repo
        self.chat_events_repo = chat_events_repo

    @staticmethod
    def _normalize_pair(first_telegram_id: int, second_telegram_id: int):
        low_id, high_id = sorted([first_telegram_id, second_telegram_id])
        return low_id, high_id, f"{low_id}:{high_id}"

    @staticmethod
    def _parse_pair_key(pair_key: str):
        try:
            low_text, high_text = pair_key.split(":")
            low = int(low_text)
            high = int(high_text)
        except Exception:
            return None, None
        if low > high:
            low, high = high, low
        return low, high

    def _list_realtime_pairs(self):
        pairs = {}
        query = {"chat_partner_id": {"$ne": None}}
        projection = {
            "telegram_id": 1,
            "chat_partner_id": 1,
            "chat_started_at": 1,
            "last_updated": 1,
            "name": 1,
            "username": 1,
            "is_active": 1,
        }
        for user in self.users_repo.find_many(query, projection):
            first = user.get("telegram_id")
            second = user.get("chat_partner_id")
            if not first or not second:
                continue
            low, high, key = self._normalize_pair(first, second)
            existing = pairs.get(key)
            if not existing:
                pairs[key] = {
                    "pair_key": key,
                    "first": low,
                    "second": high,
                    "started_at": user.get("chat_started_at"),
                    "updated_at": user.get("last_updated"),
                }
                continue

            current_started_at = user.get("chat_started_at")
            if current_started_at and (
                not existing.get("started_at") or current_started_at < existing.get("started_at")
            ):
                existing["started_at"] = current_started_at

            current_updated_at = user.get("last_updated")
            if current_updated_at and (
                not existing.get("updated_at") or current_updated_at > existing.get("updated_at")
            ):
                existing["updated_at"] = current_updated_at

        return list(pairs.values())

    def _build_user_map(self, telegram_ids: list[int]):
        unique_ids = sorted({item for item in telegram_ids if isinstance(item, int)})
        if not unique_ids:
            return {}

        users = self.users_repo.find_many(
            {"telegram_id": {"$in": unique_ids}},
            {
                "telegram_id": 1,
                "name": 1,
                "username": 1,
                "is_active": 1,
            },
        )

        return {
            user.get("telegram_id"): {
                "telegram_id": user.get("telegram_id"),
                "name": user.get("name") or "Tanpa Nama",
                "username": format_username(user.get("username")),
                "is_active": bool(user.get("is_active", True)),
            }
            for user in users
            if user.get("telegram_id") is not None
        }

    def _build_chat_overview_map(self, pair_keys: list[str]):
        overview_map = {}
        for doc in self.chat_events_repo.list_pair_overviews(pair_keys):
            key = doc.get("pair_key")
            if not key:
                continue
            messages = doc.get("messages") or []
            last_message = messages[-1] if messages else None
            overview_map[key] = {
                "message_count": len(messages),
                "last_message_text": (last_message or {}).get("text") if last_message else None,
                "last_message_sender": (last_message or {}).get("sender_id") if last_message else None,
                "last_message_at": (last_message or {}).get("sent_at") if last_message else None,
                "chat_started_at": doc.get("started_at"),
                "chat_updated_at": doc.get("updated_at"),
            }
        return overview_map

    def _normalize_messages(self, messages: list[dict], start_index: int = 0):
        sender_ids = [item.get("sender_id") for item in messages if isinstance(item.get("sender_id"), int)]
        user_map = self._build_user_map(sender_ids)

        normalized = []
        for offset, message in enumerate(messages):
            sender_id = message.get("sender_id")
            sender = user_map.get(sender_id, {})
            normalized.append(
                {
                    "message_index": start_index + offset,
                    "sender_id": sender_id,
                    "sender_name": sender.get("name") or str(sender_id) or "Tidak diketahui",
                    "sender_username": sender.get("username") or "-",
                    "sent_at_formatted": format_utc(message.get("sent_at")) if message.get("sent_at") else "-",
                    "text": message.get("text") or "",
                    "photo_id": message.get("photo_id"),
                }
            )
        return normalized

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

    def list_active_chats(self):
        realtime_pairs = self._list_realtime_pairs()
        pair_keys = [item["pair_key"] for item in realtime_pairs]
        chat_map = self._build_chat_overview_map(pair_keys)
        telegram_ids = []
        for item in realtime_pairs:
            telegram_ids.extend([item["first"], item["second"]])
        user_map = self._build_user_map(telegram_ids)

        rows = []
        for item in realtime_pairs:
            pair_key = item["pair_key"]
            first = item["first"]
            second = item["second"]
            first_user = user_map.get(first, {})
            second_user = user_map.get(second, {})
            chat_data = chat_map.get(pair_key, {})

            rows.append(
                {
                    "pair_key": pair_key,
                    "first": first,
                    "second": second,
                    "first_name": first_user.get("name") or "Tanpa Nama",
                    "second_name": second_user.get("name") or "Tanpa Nama",
                    "first_username": first_user.get("username") or "-",
                    "second_username": second_user.get("username") or "-",
                    "started_at": format_utc(item.get("started_at") or chat_data.get("chat_started_at")),
                    "updated_at": format_utc(item.get("updated_at") or chat_data.get("chat_updated_at")),
                    "message_count": chat_data.get("message_count", 0),
                    "last_message_at": format_utc(chat_data.get("last_message_at")),
                    "last_message_text": chat_data.get("last_message_text") or "-",
                }
            )

        rows.sort(key=lambda row: row.get("updated_at") or "", reverse=True)
        return rows

    def list_match_history(self, page: int = 1, per_page: int = 30):
        total_items = self.matches_repo.count_all()
        current_page = max(page, 1)
        total_pages = max((total_items + per_page - 1) // per_page, 1)
        if current_page > total_pages:
            current_page = total_pages

        skip = (current_page - 1) * per_page
        matches = self.matches_repo.list_recent(limit=per_page, skip=skip)

        realtime_pair_keys = {item.get("pair_key") for item in self._list_realtime_pairs()}
        pair_keys = [item.get("pair_key") for item in matches if item.get("pair_key")]
        chat_map = self._build_chat_overview_map(pair_keys)

        telegram_ids = []
        for match in matches:
            first = match.get("first_telegram_id")
            second = match.get("second_telegram_id")
            if isinstance(first, int):
                telegram_ids.append(first)
            if isinstance(second, int):
                telegram_ids.append(second)
        user_map = self._build_user_map(telegram_ids)

        rows = []
        for match in matches:
            pair_key = match.get("pair_key")
            first = match.get("first_telegram_id")
            second = match.get("second_telegram_id")
            first_user = user_map.get(first, {})
            second_user = user_map.get(second, {})
            chat_data = chat_map.get(pair_key, {})
            rows.append(
                {
                    "pair_key": pair_key,
                    "first": first,
                    "second": second,
                    "first_name": first_user.get("name") or match.get("first_name") or "Tanpa Nama",
                    "second_name": second_user.get("name") or match.get("second_name") or "Tanpa Nama",
                    "first_username": first_user.get("username") or "-",
                    "second_username": second_user.get("username") or "-",
                    "is_active_realtime": pair_key in realtime_pair_keys,
                    "created_at": format_utc(match.get("created_at")),
                    "updated_at": format_utc(match.get("updated_at")),
                    "message_count": chat_data.get("message_count", 0),
                    "last_message_at": format_utc(chat_data.get("last_message_at")),
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

    def get_match_detail(self, pair_key: str, message_limit: int = 500):
        first, second = self._parse_pair_key(pair_key)
        if first is None or second is None:
            return None

        match = self.matches_repo.find_by_pair_key(pair_key)
        if not match:
            return None

        realtime_pair_keys = {item.get("pair_key") for item in self._list_realtime_pairs()}
        user_map = self._build_user_map([first, second])
        chat_overview = self.chat_events_repo.get_pair_overview(first, second) or {}

        messages = self.chat_events_repo.list_messages_by_pair(first, second, limit=message_limit)
        normalized_messages = self._normalize_messages(messages)

        first_user = user_map.get(first, {})
        second_user = user_map.get(second, {})
        chat_messages = chat_overview.get("messages") or []
        last_message = chat_messages[-1] if chat_messages else None

        return {
            "pair_key": pair_key,
            "is_active_realtime": pair_key in realtime_pair_keys,
            "created_at": format_utc(match.get("created_at")),
            "updated_at": format_utc(match.get("updated_at")),
            "first": {
                "telegram_id": first,
                "name": first_user.get("name") or match.get("first_name") or "Tanpa Nama",
                "username": first_user.get("username") or "-",
                "is_active": first_user.get("is_active", True),
            },
            "second": {
                "telegram_id": second,
                "name": second_user.get("name") or match.get("second_name") or "Tanpa Nama",
                "username": second_user.get("username") or "-",
                "is_active": second_user.get("is_active", True),
            },
            "chat": {
                "started_at": format_utc(chat_overview.get("started_at")),
                "updated_at": format_utc(chat_overview.get("updated_at")),
                "message_count": len(chat_messages),
                "last_message_at": format_utc(last_message.get("sent_at")) if last_message else "-",
            },
            "messages": normalized_messages,
        }

    def get_chat_transcript(self, pair_key: str):
        low, high = self._parse_pair_key(pair_key)
        if low is None or high is None:
            return []
        messages = self.chat_events_repo.list_messages_by_pair(low, high, limit=1000)
        return self._normalize_messages(messages)

    def get_chat_transcript_incremental(self, pair_key: str, after_index: int = -1, limit: int = 200):
        low, high = self._parse_pair_key(pair_key)
        if low is None or high is None:
            return None

        doc = self.chat_events_repo.get_pair_overview(low, high)
        if not doc:
            return {
                "messages": [],
                "last_index": -1,
                "total_messages": 0,
                "has_more": False,
            }

        all_messages = doc.get("messages") or []
        total_messages = len(all_messages)

        safe_after = after_index if isinstance(after_index, int) else -1
        if safe_after < -1:
            safe_after = -1

        page_limit = max(min(limit, 500), 1)
        start = min(safe_after + 1, total_messages)
        end = min(start + page_limit, total_messages)
        chunk = all_messages[start:end]
        normalized_chunk = self._normalize_messages(chunk, start_index=start)

        return {
            "messages": normalized_chunk,
            "last_index": (end - 1) if end > 0 else -1,
            "total_messages": total_messages,
            "has_more": end < total_messages,
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
    matches_repo=match_repository,
    chat_events_repo=chat_event_repository,
)
