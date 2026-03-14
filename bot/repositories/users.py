from typing import Iterable, Optional

from bson.objectid import ObjectId

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

    def find_by_username(self, username: str, projection: Optional[dict] = None):
        return self.collection.find_one({"username": username}, projection)

    def insert_one(self, document: dict):
        return self.collection.insert_one(document)

    def update_by_telegram_id(self, telegram_id: int, updates: dict):
        return self.collection.update_one({"telegram_id": telegram_id}, {"$set": updates})

    def update_one(self, query: dict, updates: dict):
        return self.collection.update_one(query, {"$set": updates})

    def delete_by_object_id(self, mongo_id: ObjectId):
        return self.collection.delete_one({"_id": mongo_id})

    def list_recent(self, limit: int = 50):
        return list(self.collection.find().sort("created_at", -1).limit(limit))

    def count_all(self) -> int:
        return self.collection.count_documents({})

    def count_active(self) -> int:
        return self.collection.count_documents({"is_active": True})

    def aggregate_gender_stats(self) -> list:
        pipeline = [
            {"$group": {"_id": "$gender", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        return list(self.collection.aggregate(pipeline))


user_repository = UserRepository(users_collection)
