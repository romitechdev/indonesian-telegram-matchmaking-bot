from bson.objectid import ObjectId

from ..db import discover_actions_collection


class DiscoverActionRepository:
    def __init__(self, collection):
        self.collection = collection

    def insert_action(
        self,
        sender_telegram_id: int,
        target_telegram_id: int,
        action_type: str,
        message_text: str | None,
        created_at,
    ):
        """Insert a new discover action (love or message).

        action_type: 'love' or 'message'
        """
        document = {
            "sender_telegram_id": sender_telegram_id,
            "target_telegram_id": target_telegram_id,
            "action_type": action_type,
            "message_text": message_text,
            "response": None,  # pending
            "created_at": created_at,
        }
        return self.collection.insert_one(document)

    def find_action_by_id(self, action_id):
        """Find a discover action by its MongoDB _id."""
        try:
            oid = (
                ObjectId(action_id)
                if not isinstance(action_id, ObjectId)
                else action_id
            )
        except Exception:
            return None
        return self.collection.find_one({"_id": oid})

    def update_response(self, action_id, response: str, responded_at):
        """Update the target's response to a discover action.

        response: 'love_back', 'dislike', 'ignore'
        """
        try:
            oid = (
                ObjectId(action_id)
                if not isinstance(action_id, ObjectId)
                else action_id
            )
        except Exception:
            return None
        return self.collection.update_one(
            {"_id": oid},
            {"$set": {"response": response, "responded_at": responded_at}},
        )

    def exists_love(self, sender_telegram_id: int, target_telegram_id: int) -> bool:
        """Check if sender has already sent a love action to target."""
        return (
            self.collection.count_documents(
                {
                    "sender_telegram_id": sender_telegram_id,
                    "target_telegram_id": target_telegram_id,
                    "action_type": "love",
                },
                limit=1,
            )
            > 0
        )

    def exists_pending_for_pair(
        self, sender_telegram_id: int, target_telegram_id: int
    ) -> bool:
        """Check if there is already a pending action from sender to target."""
        return (
            self.collection.count_documents(
                {
                    "sender_telegram_id": sender_telegram_id,
                    "target_telegram_id": target_telegram_id,
                    "response": None,
                },
                limit=1,
            )
            > 0
        )

    def count_pending_for_target(self, target_telegram_id: int) -> int:
        """Count pending (unresponded) actions targeting this user."""
        return self.collection.count_documents(
            {"target_telegram_id": target_telegram_id, "response": None}
        )

    def count_all(self) -> int:
        return self.collection.count_documents({})

    def list_pending_for_target(self, target_telegram_id: int):
        """Return cursor of pending actions targeting this user (response is None)."""
        return self.collection.find(
            {"target_telegram_id": target_telegram_id, "response": None}
        )

    def ignore_pending_for_target(self, target_telegram_id: int):
        """Mark all pending actions for target as ignored."""
        return self.collection.update_many(
            {"target_telegram_id": target_telegram_id, "response": None},
            {"$set": {"response": "ignore"}},
        )


discover_action_repository = DiscoverActionRepository(discover_actions_collection)
