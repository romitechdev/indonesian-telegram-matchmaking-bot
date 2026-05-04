import os
import json
import urllib.request
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
    Response,
)

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
    raise RuntimeError(
        "DASHBOARD_AUTH_USERNAME dan DASHBOARD_AUTH_PASSWORD wajib diisi di environment."
    )


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

    next_value = (
        request.args.get("next")
        or request.form.get("next")
        or url_for("dashboard_home")
    )
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

    return render_template(
        "login.html", error_message=error_message, next_value=next_value
    )


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
    realtime_matches = dashboard_service.list_active_chats()
    match_history_preview = dashboard_service.list_match_history(page=page, per_page=5)
    message_text = request.args.get("msg", "")
    message_level = request.args.get("level", "ok")

    return render_template(
        "dashboard.html",
        summary=summary,
        realtime_matches_count=len(realtime_matches),
        match_history_total=match_history_preview["total_items"],
        message_text=message_text,
        message_level=message_level,
        dashboard_username=session.get("dashboard_username", "admin"),
    )


@app.route("/users")
@login_required
def users_list():
    try:
        page = max(int(request.args.get("page", "1")), 1)
    except ValueError:
        page = 1

    user_page = dashboard_service.list_recent_users(page=page, per_page=20)
    summary = dashboard_service.get_summary()
    message_text = request.args.get("msg", "")
    message_level = request.args.get("level", "ok")

    return render_template(
        "users.html",
        users=user_page["items"],
        user_page=user_page,
        summary=summary,
        message_text=message_text,
        message_level=message_level,
        dashboard_username=session.get("dashboard_username", "admin"),
    )


@app.route("/reports")
@login_required
def reports_list():
    reports = dashboard_service.list_recent_reports(limit=50)
    summary = dashboard_service.get_summary()
    message_text = request.args.get("msg", "")
    message_level = request.args.get("level", "ok")

    return render_template(
        "reports.html",
        reports=reports,
        summary=summary,
        user_page={"page": 1},
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
    next_page = request.form.get("next") or "dashboard_home"
    redirect_params = {
        "msg": result["message"],
        "level": result["level"],
    }
    if page:
        redirect_params["page"] = page

    if next_page == "users":
        return redirect(url_for("users_list", **redirect_params))
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
    result = dashboard_service.review_report(
        report_id, action, reviewed_by="dashboard_web"
    )

    if result["status"] == "reviewed":
        action_label = (
            "disetujui" if result["review_status"] == "approved" else "ditolak"
        )
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
    next_page = request.form.get("next") or "dashboard_home"
    redirect_params = {"msg": message, "level": level}
    if page:
        redirect_params["page"] = page

    if next_page == "reports":
        return redirect(url_for("reports_list", **redirect_params))
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


@app.route("/chats")
@login_required
def chats_list():
    active = dashboard_service.list_active_chats()
    return render_template(
        "chats.html",
        active_chats=active,
        dashboard_username=session.get("dashboard_username", "admin"),
    )


@app.route("/matches")
@login_required
def matches_dashboard():
    try:
        page = max(int(request.args.get("page", "1")), 1)
    except ValueError:
        page = 1

    realtime_matches = dashboard_service.list_active_chats()
    match_history = dashboard_service.list_match_history(page=page, per_page=20)

    return render_template(
        "matches.html",
        realtime_matches=realtime_matches,
        match_history=match_history,
        match_history_rows=match_history["items"],
        dashboard_username=session.get("dashboard_username", "admin"),
        auto_refresh_seconds=15,
    )


@app.route("/matches/<pair_key>")
@login_required
def match_detail(pair_key: str):
    detail = dashboard_service.get_match_detail(pair_key, message_limit=1000)
    if not detail:
        abort(404)

    return render_template(
        "match_detail.html",
        detail=detail,
        dashboard_username=session.get("dashboard_username", "admin"),
    )


@app.route("/chats/<pair_key>")
@login_required
def chat_transcript(pair_key: str):
    messages = dashboard_service.get_chat_transcript(pair_key)
    return render_template(
        "chat_transcript.html",
        pair_key=pair_key,
        messages=messages,
        dashboard_username=session.get("dashboard_username", "admin"),
    )


@app.route("/api/chats/<pair_key>/messages")
@login_required
def chat_transcript_updates(pair_key: str):
    try:
        after_index = int(request.args.get("after", "-1"))
    except ValueError:
        after_index = -1

    payload = dashboard_service.get_chat_transcript_incremental(
        pair_key, after_index=after_index, limit=200
    )
    if payload is None:
        abort(404)
    return payload


@app.route("/api/photo/<file_id>")
@login_required
def proxy_telegram_photo(file_id: str):
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        abort(404)

    get_file_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
    try:
        req = urllib.request.Request(get_file_url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            if not data.get("ok"):
                abort(404)
            file_path = data["result"]["file_path"]
    except Exception:
        abort(404)

    file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    try:
        req = urllib.request.Request(file_url)
        with urllib.request.urlopen(req) as response:
            content = response.read()
            content_type = (
                response.headers.get_content_type() if response.headers else None
            )
            return Response(
                content, mimetype=content_type or "application/octet-stream"
            )
    except Exception:
        abort(404)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)
