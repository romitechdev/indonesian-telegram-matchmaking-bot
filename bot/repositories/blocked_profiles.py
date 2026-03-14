from ..db import blocked_profiles_collection


class BlockedProfileRepository:
    def __init__(self, collection):
        self.collection = collection

    def blocked_by_user(self, blocker_telegram_id: int) -> set:
        return set(
            self.collection.distinct(
                "blocked_telegram_id",
                {"blocker_telegram_id": blocker_telegram_id},
            )
        )

    def blockers_of_user(self, blocked_telegram_id: int) -> set:
        return set(
            self.collection.distinct(
                "blocker_telegram_id",
                {"blocked_telegram_id": blocked_telegram_id},
            )
        )

    def excluded_telegram_ids(self, telegram_id: int) -> set:
        return self.blocked_by_user(telegram_id) | self.blockers_of_user(telegram_id)

    def upsert_block(
        self,
        blocker_telegram_id: int,
        blocked_telegram_id: int,
        blocked_profile_id,
        blocked_name: str,
        reason: str,
        created_at,
    ):
        return self.collection.update_one(
            {
                "blocker_telegram_id": blocker_telegram_id,
                "blocked_telegram_id": blocked_telegram_id,
            },
            {
                "$set": {
                    "blocked_profile_id": blocked_profile_id,
                    "blocked_name": blocked_name,
                    "reason": reason,
                    "created_at": created_at,
                }
            },
            upsert=True,
        )


blocked_profile_repository = BlockedProfileRepository(blocked_profiles_collection)
