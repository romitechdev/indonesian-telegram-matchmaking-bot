from datetime import timedelta

from bson.objectid import ObjectId

from ..repositories.blocked_profiles import blocked_profile_repository
from ..repositories.reports import report_repository
from ..repositories.seen_profiles import seen_profile_repository
from ..repositories.users import user_repository
from ..utils import get_target_gender, haversine, not_banned_query, now_utc


class MatchingService:
    def __init__(self, users_repo, seen_repo, blocked_repo, reports_repo):
        self.users_repo = users_repo
        self.seen_repo = seen_repo
        self.blocked_repo = blocked_repo
        self.reports_repo = reports_repo

    def get_seen_profile_ids(self, viewer_id: int):
        yesterday = now_utc() - timedelta(days=1)
        seen_profiles = self.seen_repo.list_viewed_since(viewer_id, yesterday)
        return [ObjectId(profile["profile_id"]) for profile in seen_profiles]

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
                valid_matches.append(candidate)
            valid_matches.sort(key=lambda candidate: candidate["distance"])
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
        return self.seen_repo.insert_seen(viewer_id, profile_id, now_utc())

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
)
