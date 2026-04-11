from ..db import likes_collection


class LikeRepository:
    def __init__(self, collection):
        self.collection = collection

    def upsert_like(
        self,
        liker_telegram_id: int,
        liked_telegram_id: int,
        liked_profile_id,
        liked_name: str | None,
        created_at,
    ):
        query = {
            "liker_telegram_id": liker_telegram_id,
            "liked_telegram_id": liked_telegram_id,
        }
        updates = {
            "$set": {
                "liked_profile_id": liked_profile_id,
                "liked_name": liked_name,
                "updated_at": created_at,
            },
            "$setOnInsert": {
                "created_at": created_at,
            },
        }
        return self.collection.update_one(query, updates, upsert=True)

    def exists_like(self, liker_telegram_id: int, liked_telegram_id: int) -> bool:
        return (
            self.collection.count_documents(
                {
                    "liker_telegram_id": liker_telegram_id,
                    "liked_telegram_id": liked_telegram_id,
                },
                limit=1,
            )
            > 0
        )

    def count_all(self) -> int:
        return self.collection.count_documents({})


like_repository = LikeRepository(likes_collection)
