from bson.objectid import ObjectId

from ..config import DAILY_PROFILE_VIEW_LIMIT
from ..repositories.blocked_profiles import blocked_profile_repository
from ..repositories.chat_events import chat_event_repository
from ..repositories.likes import like_repository
from ..repositories.matches import match_repository
from ..repositories.reports import report_repository
from ..repositories.seen_profiles import seen_profile_repository
from ..repositories.users import user_repository
from ..utils import (
    get_local_day_key,
    get_local_day_window,
    get_target_gender,
    haversine,
    not_banned_query,
    now_utc,
)


class MatchingService:
    COMPATIBILITY_KEYS = (
        "compatibility_value",
        "compatibility_communication_style",
        "compatibility_relationship_goal",
    )

    def __init__(
        self,
        users_repo,
        seen_repo,
        blocked_repo,
        reports_repo,
        likes_repo,
        matches_repo,
        chat_events_repo,
        daily_view_limit: int = DAILY_PROFILE_VIEW_LIMIT,
    ):
        self.users_repo = users_repo
        self.seen_repo = seen_repo
        self.blocked_repo = blocked_repo
        self.reports_repo = reports_repo
        self.likes_repo = likes_repo
        self.matches_repo = matches_repo
        self.chat_events_repo = chat_events_repo
        self.daily_view_limit = max(daily_view_limit, 1)

    @staticmethod
    def _to_object_id(raw_value):
        if isinstance(raw_value, ObjectId):
            return raw_value
        try:
            return ObjectId(raw_value)
        except Exception:
            return None

    def _current_day_context(self):
        current_time = now_utc()
        day_key = get_local_day_key(current_time)
        day_start, day_end = get_local_day_window(current_time)
        return day_key, day_start, day_end

    def get_seen_profile_ids(self, viewer_id: int):
        day_key, day_start, day_end = self._current_day_context()
        seen_profiles = self.seen_repo.list_viewed_for_day(viewer_id, day_key, day_start, day_end)

        seen_ids = []
        for profile in seen_profiles:
            profile_id = self._to_object_id(profile.get("profile_id"))
            if profile_id:
                seen_ids.append(profile_id)
        return seen_ids

    def get_daily_view_count(self, viewer_id: int) -> int:
        day_key, day_start, day_end = self._current_day_context()
        return self.seen_repo.count_viewed_for_day(viewer_id, day_key, day_start, day_end)

    def get_daily_view_limit(self) -> int:
        return self.daily_view_limit

    def remaining_daily_views(self, viewer_id: int) -> int:
        viewed_count = self.get_daily_view_count(viewer_id)
        return max(self.daily_view_limit - viewed_count, 0)

    def has_remaining_daily_views(self, viewer_id: int) -> bool:
        return self.remaining_daily_views(viewer_id) > 0

    def get_excluded_telegram_ids(self, telegram_id: int):
        blocked_ids = self.blocked_repo.excluded_telegram_ids(telegram_id)
        excluded_telegram_ids = [
            user_id for user_id in (blocked_ids | {telegram_id}) if user_id is not None
        ]
        return excluded_telegram_ids

    def find_matches_for_user(self, current_user: dict):
        target_gender = get_target_gender(current_user.get("gender"))
        if not target_gender:
            return []

        source_lat = current_user.get("latitude")
        source_lon = current_user.get("longitude")
        if source_lat is None or source_lon is None:
            return []

        seen_profile_ids = self.get_seen_profile_ids(current_user["telegram_id"])
        excluded_telegram_ids = self.get_excluded_telegram_ids(current_user["telegram_id"])

        current_time = now_utc()
        base_query = {
            "_id": {"$nin": seen_profile_ids},
            "telegram_id": {"$nin": excluded_telegram_ids},
            "is_active": True,
            "gender": target_gender,
            **not_banned_query(current_time),
        }

        def sort_by_distance(candidates):
            valid_matches = []
            for candidate in candidates:
                candidate_lat = candidate.get("latitude")
                candidate_lon = candidate.get("longitude")
                if candidate_lat is None or candidate_lon is None:
                    continue
                candidate["distance"] = haversine(
                    source_lat,
                    source_lon,
                    candidate_lat,
                    candidate_lon,
                )
                candidate["compatibility_score"] = self._compatibility_score(
                    current_user,
                    candidate,
                )
                valid_matches.append(candidate)
            valid_matches.sort(
                key=lambda candidate: (
                    -candidate.get("compatibility_score", 0),
                    candidate["distance"],
                )
            )
            return valid_matches

        query_stage1 = {
            **base_query,
            "age_group": current_user["age_group"],
        }
        stage1_matches = sort_by_distance(list(self.users_repo.find_many(query_stage1)))

        if stage1_matches:
            return stage1_matches

        return sort_by_distance(list(self.users_repo.find_many(base_query)))

    def record_seen_profile(self, viewer_id: int, profile_id):
        current_time = now_utc()
        return self.seen_repo.insert_seen(
            viewer_id,
            profile_id,
            current_time,
            viewed_day=get_local_day_key(current_time),
        )

    def like_profile(self, liker_profile: dict, liked_profile: dict):
        liker_telegram_id = liker_profile.get("telegram_id")
        liked_telegram_id = liked_profile.get("telegram_id")
        if liker_telegram_id is None or liked_telegram_id is None:
            return {
                "status": "invalid_target",
                "is_match": False,
                "is_new_match": False,
            }

        current_time = now_utc()
        self.likes_repo.upsert_like(
            liker_telegram_id=liker_telegram_id,
            liked_telegram_id=liked_telegram_id,
            liked_profile_id=liked_profile.get("_id"),
            liked_name=liked_profile.get("name"),
            created_at=current_time,
        )

        is_mutual = self.likes_repo.exists_like(
            liker_telegram_id=liked_telegram_id,
            liked_telegram_id=liker_telegram_id,
        )
        if not is_mutual:
            return {
                "status": "liked",
                "is_match": False,
                "is_new_match": False,
            }

        match_result = self.matches_repo.upsert_match(
            first_telegram_id=liker_telegram_id,
            second_telegram_id=liked_telegram_id,
            first_name=liker_profile.get("name", "Tanpa Nama"),
            second_name=liked_profile.get("name", "Tanpa Nama"),
            created_at=current_time,
        )
        return {
            "status": "matched",
            "is_match": True,
            "is_new_match": match_result.upserted_id is not None,
            "target_telegram_id": liked_telegram_id,
        }

    def mark_chat_started(self, first_telegram_id: int, second_telegram_id: int, started_by: int):
        return self.chat_events_repo.upsert_chat_started(
            first_telegram_id=first_telegram_id,
            second_telegram_id=second_telegram_id,
            started_by=started_by,
            started_at=now_utc(),
        )

    def generate_icebreakers(self, current_user: dict, target_user: dict) -> list[str]:
        shared_answers = []
        for field in self.COMPATIBILITY_KEYS:
            current_value = current_user.get(field)
            target_value = target_user.get(field)
            if current_value and target_value and current_value == target_value:
                shared_answers.append(current_value)

        if shared_answers:
            first_line = (
                f"Kalian sama-sama pilih '{shared_answers[0]}'. "
                "Cerita dong kenapa itu penting buat kamu?"
            )
        else:
            first_line = "Lagi semangat di hal apa minggu ini? Boleh saling update biar nyambung obrolannya."

        target_name = target_user.get("name", "dia")
        second_line = (
            f"Ajak {target_name} main Q&A cepat: 3 hal favorit saat weekend versi kalian masing-masing."
        )

        goal = current_user.get("compatibility_relationship_goal") or "🌈 Lihat dulu cocoknya"
        third_line = (
            f"Kamu pilih '{goal}'. Menurutmu first date ideal itu ngobrol santai di mana?"
        )

        return [first_line, second_line, third_line]

    @classmethod
    def _compatibility_score(cls, current_user: dict, candidate: dict) -> int:
        score = 0
        for field in cls.COMPATIBILITY_KEYS:
            current_value = current_user.get(field)
            candidate_value = candidate.get(field)
            if current_value and candidate_value and current_value == candidate_value:
                score += 1
        return score

    def create_block(self, blocker_telegram_id: int, match: dict, reason: str = "Manual block"):
        return self.blocked_repo.upsert_block(
            blocker_telegram_id=blocker_telegram_id,
            blocked_telegram_id=match.get("telegram_id"),
            blocked_profile_id=match.get("_id"),
            blocked_name=match.get("name"),
            reason=reason,
            created_at=now_utc(),
        )

    def create_report_and_block(self, reporter_telegram_id: int, pending_report: dict, reason: str):
        self.reports_repo.insert_one(
            {
                "reporter_telegram_id": reporter_telegram_id,
                "reported_telegram_id": pending_report["reported_telegram_id"],
                "reported_profile_id": pending_report.get("reported_profile_id"),
                "reported_name": pending_report.get("reported_name"),
                "reason": reason,
                "status": "open",
                "created_at": now_utc(),
            }
        )

        self.blocked_repo.upsert_block(
            blocker_telegram_id=reporter_telegram_id,
            blocked_telegram_id=pending_report["reported_telegram_id"],
            blocked_profile_id=pending_report.get("reported_profile_id"),
            blocked_name=pending_report.get("reported_name"),
            reason=f"Report: {reason}",
            created_at=now_utc(),
        )


matching_service = MatchingService(
    users_repo=user_repository,
    seen_repo=seen_profile_repository,
    blocked_repo=blocked_profile_repository,
    reports_repo=report_repository,
    likes_repo=like_repository,
    matches_repo=match_repository,
    chat_events_repo=chat_event_repository,
)
