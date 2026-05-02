from pymongo import ReturnDocument

from ..repositories.users import user_repository
from ..repositories.chat_events import chat_event_repository
from ..utils import get_target_gender, haversine, not_banned_query, now_utc


class ChatService:
    def __init__(self, users_repo, chat_events_repo):
        self.users_repo = users_repo
        self.chat_events_repo = chat_events_repo

    def get_profile(self, telegram_id: int):
        return self.users_repo.find_by_telegram_id(telegram_id)

    def get_partner_id(self, telegram_id: int):
        profile = self.users_repo.find_by_telegram_id(
            telegram_id,
            {"chat_partner_id": 1, "waiting_chat": 1},
        )
        if not profile:
            return None
        return profile.get("chat_partner_id")

    def is_waiting(self, telegram_id: int) -> bool:
        profile = self.users_repo.find_by_telegram_id(telegram_id, {"waiting_chat": 1})
        if not profile:
            return False
        return bool(profile.get("waiting_chat"))

    @staticmethod
    def _distance_km(source_profile: dict, candidate_profile: dict):
        source_lat = source_profile.get("latitude")
        source_lon = source_profile.get("longitude")
        candidate_lat = candidate_profile.get("latitude")
        candidate_lon = candidate_profile.get("longitude")
        if (
            source_lat is None
            or source_lon is None
            or candidate_lat is None
            or candidate_lon is None
        ):
            return None
        return haversine(source_lat, source_lon, candidate_lat, candidate_lon)

    def _ordered_candidate_ids(self, telegram_id: int, target_gender: str, current_time, profile: dict):
        query = {
            "telegram_id": {"$ne": telegram_id},
            "waiting_chat": True,
            "is_active": True,
            "gender": target_gender,
            **not_banned_query(current_time),
        }
        projection = {
            "telegram_id": 1,
            "latitude": 1,
            "longitude": 1,
            "last_updated": 1,
        }
        candidates = list(self.users_repo.find_many(query, projection))
        if not candidates:
            return []

        with_distance = []
        without_distance = []

        for candidate in candidates:
            candidate_id = candidate.get("telegram_id")
            if candidate_id is None:
                continue
            distance = self._distance_km(profile, candidate)
            if distance is None:
                without_distance.append(candidate)
                continue
            with_distance.append((distance, candidate.get("last_updated") or current_time, candidate_id))

        with_distance.sort(key=lambda item: (item[0], item[1]))
        without_distance.sort(key=lambda item: item.get("last_updated") or current_time)

        ordered_ids = [item[2] for item in with_distance]
        ordered_ids.extend(
            [candidate.get("telegram_id") for candidate in without_distance if candidate.get("telegram_id")]
        )
        return ordered_ids

    def start_or_match(self, telegram_id: int):
        profile = self.get_profile(telegram_id)
        if not profile:
            return {"status": "profile_not_found"}

        target_gender = get_target_gender(profile.get("gender"))
        if not target_gender:
            return {"status": "invalid_gender"}

        if profile.get("chat_partner_id"):
            return {
                "status": "already_chatting",
                "partner_id": profile.get("chat_partner_id"),
            }

        if profile.get("waiting_chat"):
            return {"status": "waiting"}

        current_time = now_utc()
        candidate_ids = self._ordered_candidate_ids(
            telegram_id=telegram_id,
            target_gender=target_gender,
            current_time=current_time,
            profile=profile,
        )

        for candidate_id in candidate_ids:
            claimed = self.users_repo.collection.find_one_and_update(
                {
                    "telegram_id": candidate_id,
                    "waiting_chat": True,
                    "is_active": True,
                    "gender": target_gender,
                    **not_banned_query(current_time),
                },
                {
                    "$set": {
                        "waiting_chat": False,
                        "chat_partner_id": telegram_id,
                        "chat_started_at": current_time,
                        "last_updated": current_time,
                    }
                },
                projection={"telegram_id": 1},
                return_document=ReturnDocument.BEFORE,
            )
            if not claimed:
                continue

            self.users_repo.update_by_telegram_id(
                telegram_id,
                {
                    "waiting_chat": False,
                    "chat_partner_id": candidate_id,
                    "chat_started_at": current_time,
                    "last_updated": current_time,
                },
            )
            return {
                "status": "matched",
                "partner_id": candidate_id,
            }

        self.users_repo.update_by_telegram_id(
            telegram_id,
            {
                "waiting_chat": True,
                "chat_partner_id": None,
                "chat_started_at": None,
                "last_updated": current_time,
            },
        )
        return {"status": "waiting"}

    def stop_chat(self, telegram_id: int):
        current_time = now_utc()
        profile = self.users_repo.find_by_telegram_id(
            telegram_id,
            {"chat_partner_id": 1},
        )
        partner_id = profile.get("chat_partner_id") if profile else None

        self.users_repo.update_by_telegram_id(
            telegram_id,
            {
                "waiting_chat": False,
                "chat_partner_id": None,
                "chat_started_at": None,
                "last_updated": current_time,
            },
        )

        if partner_id:
            self.users_repo.update_one(
                {
                    "telegram_id": partner_id,
                    "chat_partner_id": telegram_id,
                },
                {
                    "waiting_chat": False,
                    "chat_partner_id": None,
                    "chat_started_at": None,
                    "last_updated": current_time,
                },
            )

        return partner_id

    def record_message(self, sender_id: int, recipient_id: int, text: str, photo_id: str = None):
        try:
            first = min(sender_id, recipient_id)
            second = max(sender_id, recipient_id)
            return self.chat_events_repo.append_message(first, second, sender_id, text, now_utc(), photo_id)
        except Exception:
            return None

    def get_transcript(self, telegram_id_a: int, telegram_id_b: int, limit: int = 500):
        first = min(telegram_id_a, telegram_id_b)
        second = max(telegram_id_a, telegram_id_b)
        return self.chat_events_repo.list_messages_by_pair(first, second, limit=limit)


chat_service = ChatService(user_repository, chat_event_repository)