from ..db import seen_profiles_collection


class SeenProfileRepository:
    def __init__(self, collection):
        self.collection = collection

    def list_viewed_since(self, viewer_id: int, since):
        return list(
            self.collection.find(
                {
                    "viewer_id": viewer_id,
                    "viewed_at": {"$gte": since},
                }
            )
        )

    def insert_seen(self, viewer_id: int, profile_id, viewed_at):
        return self.collection.insert_one(
            {
                "viewer_id": viewer_id,
                "profile_id": profile_id,
                "viewed_at": viewed_at,
            }
        )


seen_profile_repository = SeenProfileRepository(seen_profiles_collection)
