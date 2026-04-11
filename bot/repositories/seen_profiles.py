from ..db import seen_profiles_collection


class SeenProfileRepository:
    def __init__(self, collection):
        self.collection = collection

    def list_viewed_for_day(self, viewer_id: int, day_key: str, day_start, day_end):
        return list(
            self.collection.find(
                {
                    "viewer_id": viewer_id,
                    "$or": [
                        {"viewed_day": day_key},
                        {
                            "viewed_day": {"$exists": False},
                            "viewed_at": {"$gte": day_start, "$lt": day_end},
                        },
                    ],
                }
            )
        )

    def insert_seen(self, viewer_id: int, profile_id, viewed_at, viewed_day: str | None = None):
        document = {
            "viewer_id": viewer_id,
            "profile_id": profile_id,
            "viewed_at": viewed_at,
        }
        if viewed_day:
            document["viewed_day"] = viewed_day
        return self.collection.insert_one(document)

    def count_viewed_for_day(self, viewer_id: int, day_key: str, day_start, day_end) -> int:
        return self.collection.count_documents(
            {
                "viewer_id": viewer_id,
                "$or": [
                    {"viewed_day": day_key},
                    {
                        "viewed_day": {"$exists": False},
                        "viewed_at": {"$gte": day_start, "$lt": day_end},
                    },
                ],
            }
        )

    def delete_viewed_for_day(self, viewer_id: int, day_key: str, day_start, day_end):
        return self.collection.delete_many(
            {
                "viewer_id": viewer_id,
                "$or": [
                    {"viewed_day": day_key},
                    {
                        "viewed_day": {"$exists": False},
                        "viewed_at": {"$gte": day_start, "$lt": day_end},
                    },
                ],
            }
        )

    def count_all(self) -> int:
        return self.collection.count_documents({})


seen_profile_repository = SeenProfileRepository(seen_profiles_collection)
