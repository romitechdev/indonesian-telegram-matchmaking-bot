from ..db import chat_events_collection


class ChatEventRepository:
    def __init__(self, collection):
        self.collection = collection

    @staticmethod
    def _pair_key(first_telegram_id: int, second_telegram_id: int) -> str:
        low_id, high_id = sorted([first_telegram_id, second_telegram_id])
        return f"{low_id}:{high_id}"

    def upsert_chat_started(
        self,
        first_telegram_id: int,
        second_telegram_id: int,
        started_by: int,
        started_at,
    ):
        pair_key = self._pair_key(first_telegram_id, second_telegram_id)
        query = {"pair_key": pair_key}
        updates = {
            "$set": {
                "first_telegram_id": first_telegram_id,
                "second_telegram_id": second_telegram_id,
                "started_by": started_by,
                "started_at": started_at,
                "updated_at": started_at,
            },
            "$setOnInsert": {
                "pair_key": pair_key,
                "created_at": started_at,
            },
        }
        return self.collection.update_one(query, updates, upsert=True)

    def count_all(self) -> int:
        return self.collection.count_documents({"started_at": {"$exists": True}})


chat_event_repository = ChatEventRepository(chat_events_collection)
