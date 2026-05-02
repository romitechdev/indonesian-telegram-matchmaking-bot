from ..db import matches_collection


class MatchRepository:
    def __init__(self, collection):
        self.collection = collection

    @staticmethod
    def _normalize_pair(first_telegram_id: int, second_telegram_id: int):
        low_id, high_id = sorted([first_telegram_id, second_telegram_id])
        return low_id, high_id, f"{low_id}:{high_id}"

    def upsert_match(
        self,
        first_telegram_id: int,
        second_telegram_id: int,
        first_name: str,
        second_name: str,
        created_at,
    ):
        low_id, high_id, pair_key = self._normalize_pair(first_telegram_id, second_telegram_id)

        name_by_id = {
            first_telegram_id: first_name,
            second_telegram_id: second_name,
        }

        query = {"pair_key": pair_key}
        updates = {
            "$set": {
                "first_telegram_id": low_id,
                "second_telegram_id": high_id,
                "first_name": name_by_id.get(low_id, "Tanpa Nama"),
                "second_name": name_by_id.get(high_id, "Tanpa Nama"),
                "updated_at": created_at,
            },
            "$setOnInsert": {
                "created_at": created_at,
                "pair_key": pair_key,
            },
        }
        return self.collection.update_one(query, updates, upsert=True)

    def count_all(self) -> int:
        return self.collection.count_documents({})

    def list_recent(self, limit: int = 50, skip: int = 0):
        return list(
            self.collection.find().sort([("updated_at", -1), ("created_at", -1)]).skip(skip).limit(limit)
        )

    def find_by_pair_key(self, pair_key: str):
        return self.collection.find_one({"pair_key": pair_key})


match_repository = MatchRepository(matches_collection)
