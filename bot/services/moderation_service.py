from bson.objectid import ObjectId

from ..repositories.reports import report_repository
from ..repositories.users import user_repository
from ..utils import format_username, format_utc, now_utc


class ModerationService:
    def __init__(self, reports_repo, users_repo):
        self.reports_repo = reports_repo
        self.users_repo = users_repo

    def list_reports_enriched(self, limit: int = 30):
        reports = self.reports_repo.list_recent(limit)
        enriched_reports = []

        for report in reports:
            reporter_id = report.get("reporter_telegram_id")
            reported_id = report.get("reported_telegram_id")

            reporter = self.users_repo.find_by_telegram_id(
                reporter_id,
                {"name": 1, "username": 1},
            )
            reported = self.users_repo.find_by_telegram_id(
                reported_id,
                {"name": 1, "username": 1},
            )

            enriched_reports.append(
                {
                    "id": str(report.get("_id")),
                    "reason": report.get("reason", "(tanpa alasan)"),
                    "status": report.get("status", "open"),
                    "created_at": format_utc(report.get("created_at")),
                    "resolved_at": format_utc(report.get("resolved_at")) if report.get("resolved_at") else "-",
                    "reporter_id": reporter_id,
                    "reported_id": reported_id,
                    "reporter_name": reporter.get("name") if reporter else "(tidak diketahui)",
                    "reported_name": (
                        reported.get("name")
                        if reported
                        else report.get("reported_name", "(tidak diketahui)")
                    ),
                    "reporter_username": (
                        format_username(reporter.get("username"))
                        if reporter
                        else "tidak ada username"
                    ),
                    "reported_username": (
                        format_username(reported.get("username"))
                        if reported
                        else "tidak ada username"
                    ),
                }
            )

        return enriched_reports

    def resolve_report(self, report_id_text: str, resolved_by: int):
        try:
            report_id = ObjectId(report_id_text.strip())
        except Exception:
            return {"status": "invalid_id"}

        report = self.reports_repo.find_by_id(report_id)
        if not report:
            return {"status": "not_found"}

        self.reports_repo.resolve_report(report_id, resolved_by, now_utc())
        return {"status": "resolved", "report_id": str(report_id)}


moderation_service = ModerationService(report_repository, user_repository)
