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

    def append_message(self, first_telegram_id: int, second_telegram_id: int, sender_id: int, text: str, sent_at, photo_id: str = None):
        pair_key = self._pair_key(first_telegram_id, second_telegram_id)
        doc = {
            "sender_id": sender_id,
            "text": text,
            "sent_at": sent_at,
        }
        if photo_id:
            doc["photo_id"] = photo_id

        return self.collection.update_one(
            {"pair_key": pair_key},
            {
                "$push": {"messages": doc},
                "$setOnInsert": {"pair_key": pair_key, "created_at": sent_at},
                "$set": {"updated_at": sent_at},
            },
            upsert=True,
        )

    def list_messages_by_pair(self, first_telegram_id: int, second_telegram_id: int, limit: int = 100):
        pair_key = self._pair_key(first_telegram_id, second_telegram_id)
        doc = self.collection.find_one({"pair_key": pair_key}, {"messages": 1})
        if not doc:
            return []
        messages = doc.get("messages") or []
        # return newest first limited
        return messages[-limit:]

    def get_pair_overview(self, first_telegram_id: int, second_telegram_id: int):
        pair_key = self._pair_key(first_telegram_id, second_telegram_id)
        return self.collection.find_one(
            {"pair_key": pair_key},
            {
                "pair_key": 1,
                "updated_at": 1,
                "started_at": 1,
                "messages": 1,
            },
        )

    def list_pair_overviews(self, pair_keys: list[str]):
        if not pair_keys:
            return []
        return list(
            self.collection.find(
                {"pair_key": {"$in": pair_keys}},
                {
                    "pair_key": 1,
                    "updated_at": 1,
                    "started_at": 1,
                    "messages": 1,
                },
            )
        )


chat_event_repository = ChatEventRepository(chat_events_collection)
