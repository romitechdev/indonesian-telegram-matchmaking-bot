import os
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import Flask, abort, redirect, render_template, request, session, url_for

from bot.services.dashboard_service import dashboard_service


app = Flask(__name__)

DASHBOARD_AUTH_USERNAME = os.getenv("DASHBOARD_AUTH_USERNAME", "").strip()
DASHBOARD_AUTH_PASSWORD = os.getenv("DASHBOARD_AUTH_PASSWORD", "")
DASHBOARD_SESSION_SECRET = (
    os.getenv("DASHBOARD_SESSION_SECRET")
    or os.getenv("TELEGRAM_TOKEN")
    or "lovematchid-dashboard-secret"
)
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8090"))
app.secret_key = DASHBOARD_SESSION_SECRET


if not DASHBOARD_AUTH_USERNAME or not DASHBOARD_AUTH_PASSWORD:
    raise RuntimeError("DASHBOARD_AUTH_USERNAME dan DASHBOARD_AUTH_PASSWORD wajib diisi di environment.")


def _is_logged_in() -> bool:
    return session.get("dashboard_auth") is True


def _is_safe_next_url(target: str) -> bool:
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def _redirect_to_login():
    next_value = request.full_path if request.query_string else request.path
    return redirect(url_for("dashboard_login", next=next_value))


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not _is_logged_in():
            return _redirect_to_login()
        return view_func(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def dashboard_login():
    if _is_logged_in():
        return redirect(url_for("dashboard_home"))

    next_value = request.args.get("next") or request.form.get("next") or url_for("dashboard_home")
    if not _is_safe_next_url(next_value):
        next_value = url_for("dashboard_home")

    error_message = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == DASHBOARD_AUTH_USERNAME and password == DASHBOARD_AUTH_PASSWORD:
            session["dashboard_auth"] = True
            session["dashboard_username"] = username
            return redirect(next_value)
        error_message = "Username atau password salah."

    return render_template("login.html", error_message=error_message, next_value=next_value)


@app.post("/logout")
def dashboard_logout():
    session.clear()
    return redirect(url_for("dashboard_login"))


@app.route("/")
@login_required
def dashboard_home():
    try:
        page = max(int(request.args.get("page", "1")), 1)
    except ValueError:
        page = 1

    summary = dashboard_service.get_summary()
    user_page = dashboard_service.list_recent_users(page=page, per_page=20)
    reports = dashboard_service.list_recent_reports(limit=20)
    message_text = request.args.get("msg", "")
    message_level = request.args.get("level", "ok")

    return render_template(
        "dashboard.html",
        summary=summary,
        users=user_page["items"],
        user_page=user_page,
        reports=reports,
        message_text=message_text,
        message_level=message_level,
        dashboard_username=session.get("dashboard_username", "admin"),
    )


@app.post("/users/bulk-action")
@login_required
def users_bulk_action():
    selected_user_ids = request.form.getlist("selected_user_ids")
    action = request.form.get("action", "")
    reason = request.form.get("reason", "Moderasi via dashboard web")

    try:
        ban_hours = int(request.form.get("ban_hours", "24"))
    except ValueError:
        ban_hours = 24

    result = dashboard_service.apply_bulk_user_action(
        user_id_texts=selected_user_ids,
        action=action,
        ban_hours=ban_hours,
        reason=reason,
    )

    page = request.args.get("page") or request.form.get("page")
    redirect_params = {
        "msg": result["message"],
        "level": result["level"],
    }
    if page:
        redirect_params["page"] = page

    return redirect(url_for("dashboard_home", **redirect_params))


@app.post("/users/<user_id>/reset-daily-limit")
@login_required
def reset_daily_limit(user_id: str):
    result = dashboard_service.reset_user_daily_limit(user_id)
    page = request.args.get("page") or request.form.get("page")
    next_page = request.form.get("next") or "home"

    redirect_params = {
        "msg": result["message"],
        "level": result["level"],
    }
    if page:
        redirect_params["page"] = page

    if next_page == "detail":
        return redirect(url_for("user_detail", user_id=user_id, **redirect_params))
    return redirect(url_for("dashboard_home", **redirect_params))


@app.post("/reports/<report_id>/review")
@login_required
def review_report(report_id: str):
    action = request.form.get("action", "")
    result = dashboard_service.review_report(report_id, action, reviewed_by="dashboard_web")

    if result["status"] == "reviewed":
        action_label = "disetujui" if result["review_status"] == "approved" else "ditolak"
        message = (
            f"Report {result['report_id']} {action_label}. "
            f"Approved report user: {result['approved_reports_count']}"
        )
        if result["auto_ban_status"] == "applied":
            message += " | Auto-ban aktif."
        elif result["auto_ban_status"] == "removed":
            message += " | Auto-ban dilepas."
        level = "ok"
    elif result["status"] == "invalid_id":
        message = "Format report ID tidak valid."
        level = "error"
    elif result["status"] == "invalid_action":
        message = "Aksi review tidak valid."
        level = "error"
    else:
        message = "Report tidak ditemukan."
        level = "error"

    page = request.args.get("page") or request.form.get("page")
    redirect_params = {"msg": message, "level": level}
    if page:
        redirect_params["page"] = page
    return redirect(url_for("dashboard_home", **redirect_params))


@app.route("/users/<user_id>")
@login_required
def user_detail(user_id: str):
    user = dashboard_service.get_user_detail(user_id)
    if not user:
        abort(404)

    return render_template(
        "user_detail.html",
        user=user,
        message_text=request.args.get("msg", ""),
        message_level=request.args.get("level", "ok"),
        dashboard_username=session.get("dashboard_username", "admin"),
    )


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)
