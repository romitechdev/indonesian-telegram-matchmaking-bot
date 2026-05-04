from bot.repositories.users import user_repository
from bot.services.matching_service import matching_service

print("Fetching recent users...")
users = user_repository.list_recent(limit=10)
ids = [u.get("telegram_id") for u in users if u.get("telegram_id")]
print("Found telegram ids:", ids)
if len(ids) < 4:
    print("Not enough users with telegram_id to run test. Need >=4 users.")
    raise SystemExit(1)

reporters = ids[0:3]
target = ids[3]
print("Reporters:", reporters)
print("Target:", target)

for i, r in enumerate(reporters, start=1):
    pending = {
        "reported_telegram_id": target,
        "reported_profile_id": None,
        "reported_name": None,
    }
    print(f"Creating report {i} from {r} -> {target}")
    matching_service.create_report_and_block(r, pending, f"Test report {i}")
    count = matching_service.reports_repo.count_by_reported_telegram_id(target)
    print(f"Report count for target {target}:", count)

# show user ban status
user = user_repository.find_by_telegram_id(target)
print("Target user document (ban fields):")
print(
    {
        "telegram_id": user.get("telegram_id"),
        "ban_until": user.get("ban_until"),
        "ban_reason": user.get("ban_reason"),
        "banned_by": user.get("banned_by"),
        "auto_report_ban": user.get("auto_report_ban"),
        "auto_report_ban_count": user.get("auto_report_ban_count"),
    }
)
print("Done")
