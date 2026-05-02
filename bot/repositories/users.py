from typing import Optional

from bson.objectid import ObjectId
from pymongo import ReturnDocument

from ..db import users_collection


class UserRepository:
    def __init__(self, collection):
        self.collection = collection

    def find_one(self, query: dict, projection: Optional[dict] = None):
        return self.collection.find_one(query, projection)

    def find_many(self, query: dict, projection: Optional[dict] = None):
        return self.collection.find(query, projection)

    def find_by_telegram_id(self, telegram_id: int, projection: Optional[dict] = None):
        return self.collection.find_one({"telegram_id": telegram_id}, projection)

    def find_active_by_telegram_id(self, telegram_id: int, projection: Optional[dict] = None):
        return self.collection.find_one({"telegram_id": telegram_id, "is_active": True}, projection)

    def find_by_object_id(self, mongo_id: ObjectId, projection: Optional[dict] = None):
        return self.collection.find_one({"_id": mongo_id}, projection)

    def insert_one(self, document: dict):
        return self.collection.insert_one(document)

    def update_by_telegram_id(self, telegram_id: int, updates: dict):
        return self.collection.update_one({"telegram_id": telegram_id}, {"$set": updates})

    def update_one(self, query: dict, updates: dict):
        return self.collection.update_one(query, {"$set": updates})

    def append_pending_notification(self, telegram_id: int, notification: dict):
        return self.collection.update_one(
            {"telegram_id": telegram_id},
            {"$push": {"pending_notifications": notification}},
        )

    def pull_pending_notifications(self, telegram_id: int) -> list[dict]:
        document = self.collection.find_one_and_update(
            {"telegram_id": telegram_id},
            {"$set": {"pending_notifications": []}},
            projection={"pending_notifications": 1},
            return_document=ReturnDocument.BEFORE,
        )
        if not document:
            return []
        pending_notifications = document.get("pending_notifications") or []
        return [item for item in pending_notifications if isinstance(item, dict)]

    def delete_by_object_id(self, mongo_id: ObjectId):
        return self.collection.delete_one({"_id": mongo_id})

    def update_many_by_object_ids(self, object_ids: list[ObjectId], updates: dict):
        return self.collection.update_many({"_id": {"$in": object_ids}}, {"$set": updates})

    def delete_many_by_object_ids(self, object_ids: list[ObjectId]):
        return self.collection.delete_many({"_id": {"$in": object_ids}})

    def list_recent(self, limit: int = 50, skip: int = 0):
        return list(self.collection.find().sort("created_at", -1).skip(skip).limit(limit))

    def count_all(self) -> int:
        return self.collection.count_documents({})

    def count_active(self) -> int:
        return self.collection.count_documents({"is_active": True})

    def count_temporarily_banned(self, reference_time) -> int:
        return self.collection.count_documents({"ban_until": {"$gt": reference_time}})

    def aggregate_gender_stats(self) -> list:
        pipeline = [
            {"$group": {"_id": "$gender", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        return list(self.collection.aggregate(pipeline))

    def list_unique_telegram_ids(self) -> list[int]:
        ids = self.collection.distinct("telegram_id", {"telegram_id": {"$type": "int"}})
        return [user_id for user_id in ids if isinstance(user_id, int)]


user_repository = UserRepository(users_collection)
