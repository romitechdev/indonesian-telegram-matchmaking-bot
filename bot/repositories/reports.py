from bson.objectid import ObjectId

from ..db import reports_collection


class ReportRepository:
    def __init__(self, collection):
        self.collection = collection

    def insert_one(self, document: dict):
        return self.collection.insert_one(document)

    def list_recent(self, limit: int = 30, query: dict | None = None):
        return list(self.collection.find(query or {}).sort("created_at", -1).limit(limit))

    def count_all(self) -> int:
        return self.collection.count_documents({})

    def count_open(self) -> int:
        return self.collection.count_documents({"status": "open"})

    def count_by_status(self, status: str) -> int:
        return self.collection.count_documents({"status": status})

    def count_by_reported_telegram_id(self, reported_telegram_id: int, status: str | None = None) -> int:
        query = {"reported_telegram_id": reported_telegram_id}
        if status:
            query["status"] = status
        return self.collection.count_documents(query)

    def find_by_id(self, report_id: ObjectId):
        return self.collection.find_one({"_id": report_id})

    def review_report(self, report_id: ObjectId, status: str, reviewed_by, reviewed_at):
        return self.collection.update_one(
            {"_id": report_id},
            {
                "$set": {
                    "status": status,
                    "reviewed_at": reviewed_at,
                    "reviewed_by": reviewed_by,
                    "resolved_at": reviewed_at,
                    "resolved_by": reviewed_by,
                }
            },
        )

    def resolve_report(self, report_id: ObjectId, resolved_by: int, resolved_at):
        return self.review_report(report_id, "approved", resolved_by, resolved_at)


report_repository = ReportRepository(reports_collection)
