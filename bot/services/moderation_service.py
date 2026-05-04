from datetime import timedelta

from bson.objectid import ObjectId

from ..config import AUTO_REPORT_BAN_DAYS, AUTO_REPORT_BAN_THRESHOLD
from ..repositories.reports import report_repository
from ..repositories.users import user_repository
from ..utils import format_username, format_utc, now_utc


class ModerationService:
    AUTO_BAN_SOURCE = "auto_report_threshold"

    def __init__(self, reports_repo, users_repo):
        self.reports_repo = reports_repo
        self.users_repo = users_repo

    @staticmethod
    def _normalize_review_action(action: str | None):
        normalized = (action or "").strip().lower()
        if normalized in {"approve", "approved", "setuju", "acc", "yes"}:
            return "approved"
        if normalized in {"reject", "rejected", "tolak", "unreport", "no"}:
            return "rejected"
        return None

    def _sync_auto_ban(
        self, reported_telegram_id: int, approved_reports_count: int, review_time
    ):
        if reported_telegram_id is None:
            return "skipped"

        reported_user = self.users_repo.find_by_telegram_id(
            reported_telegram_id,
            {
                "ban_until": 1,
                "banned_by": 1,
                "auto_report_ban": 1,
            },
        )
        if not reported_user:
            return "missing_user"

        if approved_reports_count >= AUTO_REPORT_BAN_THRESHOLD:
            if reported_user.get("banned_by") not in {
                None,
                self.AUTO_BAN_SOURCE,
            } and not reported_user.get("auto_report_ban"):
                return "already_banned"

            self.users_repo.update_by_telegram_id(
                reported_telegram_id,
                {
                    "ban_until": review_time + timedelta(days=AUTO_REPORT_BAN_DAYS),
                    "ban_reason": (
                        f"Auto-ban: {approved_reports_count} report disetujui admin"
                    ),
                    "banned_at": review_time,
                    "banned_by": self.AUTO_BAN_SOURCE,
                    "auto_report_ban": True,
                    "auto_report_ban_count": approved_reports_count,
                    "last_updated": review_time,
                },
            )
            return "applied"

        if (
            reported_user.get("auto_report_ban")
            and reported_user.get("banned_by") == self.AUTO_BAN_SOURCE
        ):
            self.users_repo.update_by_telegram_id(
                reported_telegram_id,
                {
                    "ban_until": None,
                    "ban_reason": None,
                    "banned_at": None,
                    "banned_by": None,
                    "auto_report_ban": False,
                    "auto_report_ban_count": approved_reports_count,
                    "last_updated": review_time,
                },
            )
            return "removed"

        return "not_needed"

    def list_reports_enriched(self, limit: int = 30, query: dict | None = None):
        reports = self.reports_repo.list_recent(limit, query=query)
        enriched_reports = []
        approved_count_cache = {}

        for report in reports:
            reporter_id = report.get("reporter_telegram_id")
            reported_id = report.get("reported_telegram_id")

            if reported_id not in approved_count_cache:
                approved_count_cache[reported_id] = (
                    self.reports_repo.count_by_reported_telegram_id(
                        reported_id, "approved"
                    )
                    if reported_id is not None
                    else 0
                )

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
                    "reviewed_at": (
                        format_utc(
                            report.get("reviewed_at") or report.get("resolved_at")
                        )
                        if report.get("reviewed_at") or report.get("resolved_at")
                        else "-"
                    ),
                    "reporter_id": reporter_id,
                    "reported_id": reported_id,
                    "approved_reports_count": approved_count_cache[reported_id],
                    "reporter_name": (
                        reporter.get("name") if reporter else "(tidak diketahui)"
                    ),
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

    def review_report(self, report_id_text: str, action: str, reviewed_by):
        try:
            report_id = ObjectId(report_id_text.strip())
        except Exception:
            return {"status": "invalid_id"}

        review_status = self._normalize_review_action(action)
        if not review_status:
            return {"status": "invalid_action"}

        report = self.reports_repo.find_by_id(report_id)
        if not report:
            return {"status": "not_found"}

        review_time = now_utc()
        self.reports_repo.review_report(
            report_id, review_status, reviewed_by, review_time
        )

        reported_telegram_id = report.get("reported_telegram_id")
        approved_reports_count = (
            self.reports_repo.count_by_reported_telegram_id(
                reported_telegram_id, "approved"
            )
            if reported_telegram_id is not None
            else 0
        )
        auto_ban_status = self._sync_auto_ban(
            reported_telegram_id,
            approved_reports_count,
            review_time,
        )

        return {
            "status": "reviewed",
            "report_id": str(report_id),
            "review_status": review_status,
            "approved_reports_count": approved_reports_count,
            "auto_ban_status": auto_ban_status,
            "reported_telegram_id": reported_telegram_id,
        }

    def resolve_report(self, report_id_text: str, resolved_by: int):
        return self.review_report(report_id_text, "approve", resolved_by)


moderation_service = ModerationService(report_repository, user_repository)
