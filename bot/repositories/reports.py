from bson.objectid import ObjectId

from ..db import reports_collection


class ReportRepository:
    def __init__(self, collection):
        self.collection = collection

    def insert_one(self, document: dict):
        return self.collection.insert_one(document)

    def list_recent(self, limit: int = 30):
        return list(self.collection.find().sort("created_at", -1).limit(limit))

    def find_by_id(self, report_id: ObjectId):
        return self.collection.find_one({"_id": report_id})

    def resolve_report(self, report_id: ObjectId, resolved_by: int, resolved_at):
        return self.collection.update_one(
            {"_id": report_id},
            {
                "$set": {
                    "status": "resolved",
                    "resolved_at": resolved_at,
                    "resolved_by": resolved_by,
                }
            },
        )


report_repository = ReportRepository(reports_collection)
