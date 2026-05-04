from datetime import timedelta

from bson.objectid import ObjectId

from ..repositories.users import user_repository
from ..utils import get_age_group, normalize_username, now_utc


class UserService:
    def __init__(self, users_repo):
        self.users_repo = users_repo

    def sync_identity(self, user):
        if not user:
            return
        self.users_repo.update_by_telegram_id(
            user.id,
            {
                "username": normalize_username(user.username),
                "last_seen": now_utc(),
            },
        )

    def get_profile(self, telegram_id: int):
        return self.users_repo.find_by_telegram_id(telegram_id)

    def get_active_profile(self, telegram_id: int):
        return self.users_repo.find_active_by_telegram_id(telegram_id)

    def create_profile_from_context(self, user, context_user_data: dict):
        document = {
            "telegram_id": user.id,
            "name": context_user_data["name"],
            "age": context_user_data["age"],
            "gender": context_user_data["gender"],
            "description": context_user_data["description"],
            "compatibility_value": context_user_data.get("compatibility_value"),
            "compatibility_communication_style": context_user_data.get(
                "compatibility_communication_style"
            ),
            "compatibility_relationship_goal": context_user_data.get(
                "compatibility_relationship_goal"
            ),
            "latitude": context_user_data["latitude"],
            "longitude": context_user_data["longitude"],
            "photo_file_id": context_user_data["photo_file_id"],
            "username": normalize_username(user.username),
            "age_group": get_age_group(context_user_data["age"]),
            "is_active": True,
            "created_at": now_utc(),
            "last_updated": now_utc(),
            "last_seen": now_utc(),
        }
        return self.users_repo.insert_one(document)

    def update_profile_fields(self, telegram_id: int, fields: dict):
        updates = {
            **fields,
            "last_updated": now_utc(),
        }
        return self.users_repo.update_by_telegram_id(telegram_id, updates)

    def set_active(self, telegram_id: int, is_active: bool):
        return self.users_repo.update_by_telegram_id(
            telegram_id, {"is_active": is_active}
        )

    def list_recent_users(self, limit: int = 50):
        return self.users_repo.list_recent(limit)

    def get_stats(self):
        total_users = self.users_repo.count_all()
        active_users = self.users_repo.count_active()
        gender_stats = self.users_repo.aggregate_gender_stats()
        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "gender_stats": gender_stats,
        }

    def find_user_for_admin(self, query: str):
        query = query.strip()
        try:
            return self.users_repo.find_by_object_id(ObjectId(query))
        except Exception:
            pass

        if query.isdigit():
            return self.users_repo.find_by_telegram_id(int(query))
        return None

    def delete_user_by_id_text(self, user_id_text: str):
        try:
            object_id = ObjectId(user_id_text.strip())
        except Exception:
            return {"status": "invalid_id"}

        result = self.users_repo.delete_by_object_id(object_id)
        if result.deleted_count > 0:
            return {"status": "deleted"}
        return {"status": "not_found"}

    def set_temp_ban(
        self,
        target_telegram_id: int,
        duration_hours: int,
        reason: str,
        admin_user_id: int,
    ):
        ban_until = now_utc() + timedelta(hours=duration_hours)
        updates = {
            "ban_until": ban_until,
            "ban_reason": reason,
            "banned_at": now_utc(),
            "banned_by": admin_user_id,
            "last_updated": now_utc(),
        }
        result = self.users_repo.update_by_telegram_id(target_telegram_id, updates)
        return {
            "matched_count": result.matched_count,
            "ban_until": ban_until,
            "reason": reason,
        }

    def get_user_identity(self, telegram_id: int):
        return self.users_repo.find_by_telegram_id(
            telegram_id,
            {
                "name": 1,
                "username": 1,
            },
        )

    def list_broadcast_targets(self) -> list[int]:
        return self.users_repo.list_unique_telegram_ids()

    def enqueue_pending_notification(self, target_telegram_id: int, text: str):
        return self.users_repo.append_pending_notification(
            target_telegram_id,
            {
                "type": "like_notice",
                "text": text,
                "created_at": now_utc(),
            },
        )

    def consume_pending_notifications(self, telegram_id: int) -> list[dict]:
        return self.users_repo.pull_pending_notifications(telegram_id)


user_service = UserService(user_repository)
