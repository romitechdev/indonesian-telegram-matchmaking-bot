import asyncio

from telegram import ReplyKeyboardRemove, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes, ConversationHandler

from ..config import (
    ADMIN_ACTION,
    ADMIN_BROADCAST,
    ADMIN_DELETE_CONFIRM,
    ADMIN_RESOLVE_REPORT,
    ADMIN_TEMP_BAN,
    ADMIN_VIEW_USER,
    TEMP_BAN_DEFAULT_HOURS,
    TEMP_BAN_MAX_HOURS,
)
from ..keyboards import admin_menu_keyboard
from ..services.moderation_service import moderation_service
from ..services.user_service import user_service
from ..utils import (
    escape_html,
    format_username,
    format_utc,
    is_admin,
    is_temporarily_banned,
    telegram_call_with_retry,
)


def _parse_report_review_input(raw_text: str):
    parts = [part for part in raw_text.strip().split() if part]
    if len(parts) != 2:
        return None, None

    first, second = parts[0], parts[1]
    first_lower = first.lower()
    second_lower = second.lower()
    valid_actions = {
        "approve",
        "approved",
        "setuju",
        "acc",
        "reject",
        "rejected",
        "tolak",
        "unreport",
    }

    if first_lower in valid_actions:
        return second, first_lower
    if second_lower in valid_actions:
        return first, second_lower
    return None, None


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_service.sync_identity(update.effective_user)
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "✨ <b>Admin Panel</b> ✨\n\nPilih menu dibawah ini:",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )
    return ADMIN_ACTION


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    users = user_service.list_recent_users(limit=50)

    if not users:
        await update.message.reply_text(
            "Tidak ada pengguna terdaftar.", reply_markup=admin_menu_keyboard()
        )
        return ADMIN_ACTION

    header = "📋 <b>Daftar Pengguna</b> (50 terbaru):\n\n"
    current_msg = header
    for user in users:
        status = "🟢" if user.get("is_active", True) else "🔴"
        ban_status = "⛔ BANNED" if is_temporarily_banned(user) else ""
        entry = (
            f"{status} <b>{escape_html(user['name'])}</b>, {escape_html(user['age'])}\n"
            f"ID: <code>{escape_html(user['_id'])}</code>\n"
            f"Username: {escape_html(format_username(user.get('username')))}\n"
            f"Ban: {escape_html(ban_status or 'tidak')}\n"
            f"Terdaftar: {escape_html(user['created_at'].strftime('%d/%m/%Y'))}\n\n"
        )
        if len(current_msg) + len(entry) > 4000:
            await update.message.reply_text(current_msg, parse_mode="HTML")
            current_msg = entry
        else:
            current_msg += entry

    await update.message.reply_text(
        current_msg,
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    stats = user_service.get_stats()

    message = (
        "📊 <b>Statistik Pengguna</b>\n\n"
        f"👥 Total Pengguna: <b>{escape_html(stats['total_users'])}</b>\n"
        f"🟢 Aktif: <b>{escape_html(stats['active_users'])}</b> | 🔴 Nonaktif: <b>{escape_html(stats['inactive_users'])}</b>\n"
    )

    message += "\n🚻 <b>Gender</b>:\n"
    for gender in stats["gender_stats"]:
        message += f"- {escape_html(gender['_id'])}: {escape_html(gender['count'])}\n"

    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )


async def list_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    reports = moderation_service.list_reports_enriched(limit=30)
    if not reports:
        await update.message.reply_text(
            "Belum ada laporan masuk.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    header = "🚨 <b>Laporan Keamanan</b> (30 terbaru):\n\n"
    current_msg = header

    for report in reports:
        entry = (
            f"ID Report: <code>{escape_html(report['id'])}</code>\n"
            f"🚨 <b>{escape_html(report['reason'])}</b>\n"
            f"Pelapor: {escape_html(report['reporter_name'])} ({escape_html(report['reporter_username'])}) | <code>{escape_html(report['reporter_id'])}</code>\n"
            f"Dilaporkan: {escape_html(report['reported_name'])} ({escape_html(report['reported_username'])}) | <code>{escape_html(report['reported_id'])}</code>\n"
            f"Status: {escape_html(report['status'])} | Approved Count: {escape_html(report['approved_reports_count'])}\n"
            f"Dibuat: {escape_html(report['created_at'])} | Direview: {escape_html(report['reviewed_at'])}\n\n"
        )

        if len(current_msg) + len(entry) > 4000:
            await update.message.reply_text(current_msg, parse_mode="HTML")
            current_msg = entry
        else:
            current_msg += entry

    await update.message.reply_text(
        current_msg,
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )

    return ADMIN_ACTION


async def resolve_report_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "🧾 Kirim review report dengan format:\n"
        "<code>approve &lt;report_id&gt;</code> atau <code>reject &lt;report_id&gt;</code>\n"
        "Alias <code>setuju</code> / <code>tolak</code> / <code>unreport</code> juga bisa dipakai.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADMIN_RESOLVE_REPORT


async def resolve_report_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report_id_text, action = _parse_report_review_input(update.message.text)

    if not report_id_text or not action:
        await update.message.reply_text(
            "❌ Format salah. Pakai <code>approve &lt;report_id&gt;</code> atau <code>reject &lt;report_id&gt;</code>.",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    result = moderation_service.review_report(
        report_id_text, action, update.effective_user.id
    )
    if result["status"] == "invalid_id":
        await update.message.reply_text(
            "❌ Format ID report tidak valid.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION
    if result["status"] == "invalid_action":
        await update.message.reply_text(
            "❌ Aksi report tidak valid. Pakai approve atau reject.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION
    if result["status"] == "not_found":
        await update.message.reply_text(
            "❌ Report tidak ditemukan.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    action_label = "disetujui" if result["review_status"] == "approved" else "ditolak"
    extra_note = ""
    if result["auto_ban_status"] == "applied":
        extra_note = "\n⛔ Auto-ban aktif karena threshold report tercapai."
    elif result["auto_ban_status"] == "removed":
        extra_note = "\n✅ Auto-ban dilepas karena jumlah report disetujui turun lagi."

    await update.message.reply_text(
        (
            f"✅ Report <code>{escape_html(result['report_id'])}</code> {escape_html(action_label)}.\n"
            f"Approved report user ini: {escape_html(result['approved_reports_count'])}"
            f"{extra_note}"
        ),
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )
    return ADMIN_ACTION


async def temp_ban_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "⛔ Kirim data ban dengan format:\n"
        "<code>telegram_id durasi_jam alasan</code>\n"
        "Contoh: <code>6347607133 24 Report penipuan</code>\n"
        f"Default durasi: {TEMP_BAN_DEFAULT_HOURS} jam",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADMIN_TEMP_BAN


async def temp_ban_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    parts = raw_text.split()

    if len(parts) < 1 or not parts[0].isdigit():
        await update.message.reply_text(
            "❌ Format salah. Minimal isi <code>telegram_id</code>.",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    target_telegram_id = int(parts[0])
    duration_hours = TEMP_BAN_DEFAULT_HOURS
    reason_start_index = 1

    if len(parts) >= 2 and parts[1].isdigit():
        duration_hours = int(parts[1])
        reason_start_index = 2

    if duration_hours < 1 or duration_hours > TEMP_BAN_MAX_HOURS:
        await update.message.reply_text(
            f"❌ Durasi harus 1-{TEMP_BAN_MAX_HOURS} jam.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    reason = (
        " ".join(parts[reason_start_index:]).strip() or "Pelanggaran aturan komunitas"
    )
    ban_result = user_service.set_temp_ban(
        target_telegram_id,
        duration_hours,
        reason,
        update.effective_user.id,
    )

    if ban_result["matched_count"] == 0:
        await update.message.reply_text(
            "❌ Pengguna tidak ditemukan. Pastikan telegram_id benar.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    await update.message.reply_text(
        "✅ Ban sementara aktif\n"
        f"User ID: <code>{escape_html(target_telegram_id)}</code>\n"
        f"Sampai: {escape_html(format_utc(ban_result['ban_until']))}\n"
        f"Alasan: {escape_html(ban_result['reason'])}",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )
    return ADMIN_ACTION


async def find_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "🔍 Masukkan ID MongoDB atau Telegram ID:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADMIN_VIEW_USER


async def view_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    user = user_service.find_user_for_admin(query)

    if not user:
        await update.message.reply_text(
            "Pengguna tidak ditemukan!",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    status = "🟢 Aktif" if user.get("is_active", True) else "🔴 Nonaktif"
    ban_status = "⛔ Sedang diban" if is_temporarily_banned(user) else "✅ Tidak diban"
    ban_until = format_utc(user.get("ban_until")) if user.get("ban_until") else "-"
    ban_reason = user.get("ban_reason", "-")
    message = (
        "📋 <b>Detail Pengguna</b>\n\n"
        f"🆔 ID: <code>{escape_html(user['_id'])}</code>\n"
        f"🪪 Telegram ID: <code>{escape_html(user.get('telegram_id', '-'))}</code>\n"
        f"👤 Nama: <b>{escape_html(user['name'])}</b>, {escape_html(user['age'])}\n"
        f"🚻 Gender: {escape_html(user['gender'])}\n"
        f"📱 Username: {escape_html(format_username(user.get('username')))}\n"
        f"📍 Lokasi: {escape_html(user.get('latitude', '?'))}, {escape_html(user.get('longitude', '?'))}\n"
        f"📅 Terdaftar: {escape_html(user['created_at'].strftime('%d/%m/%Y %H:%M'))}\n"
        f"🔄 Terakhir update: {escape_html(user.get('last_updated', user['created_at']).strftime('%d/%m/%Y %H:%M'))}\n"
        f"🔘 Status: {escape_html(status)}\n\n"
        f"⛔ Ban Status: {escape_html(ban_status)}\n"
        f"⏳ Ban Sampai: {escape_html(ban_until)}\n"
        f"🧾 Alasan Ban: {escape_html(ban_reason)}\n\n"
        f"📝 Bio:\n<i>{escape_html(user.get('description', 'tidak ada'))}</i>"
    )

    if user.get("photo_file_id"):
        await update.message.reply_photo(
            photo=user["photo_file_id"],
            caption=message,
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )

    return ADMIN_ACTION


async def delete_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "❌ Masukkan ID pengguna yang akan dihapus:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADMIN_DELETE_CONFIRM


async def delete_user_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()

    result = user_service.delete_user_by_id_text(user_id)

    if result["status"] == "invalid_id":
        await update.message.reply_text(
            "❌ Format ID tidak valid!",
            reply_markup=admin_menu_keyboard(),
        )
    elif result["status"] == "not_found":
        await update.message.reply_text(
            "❌ Pengguna tidak ditemukan!",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            f"✅ Pengguna dengan ID <code>{escape_html(user_id)}</code> berhasil dihapus!",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )

    return ADMIN_ACTION


async def admin_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "Kembali ke dashboard admin 👇",
        reply_markup=admin_menu_keyboard(),
    )
    return ADMIN_ACTION


async def broadcast_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "📣 Kirim pesan broadcast ke semua user.\n"
        "Tulis isi pesannya dalam 1 chat (maks 3500 karakter).\n"
        "Ketik /cancel untuk batal.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADMIN_BROADCAST


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    message_text = (update.message.text or "").strip()
    if not message_text:
        await update.message.reply_text(
            "❌ Pesan broadcast tidak boleh kosong.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    if len(message_text) > 3500:
        await update.message.reply_text(
            "❌ Pesan terlalu panjang. Maksimum 3500 karakter.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    target_ids = user_service.list_broadcast_targets()
    if not target_ids:
        await update.message.reply_text(
            "Belum ada user yang bisa dikirimi broadcast.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    await update.message.reply_text(
        f"⏳ Broadcast dimulai ke {len(target_ids)} user...",
        reply_markup=admin_menu_keyboard(),
    )

    sent_count = 0
    forbidden_count = 0
    bad_request_count = 0
    other_error_count = 0

    for chat_id in target_ids:
        try:
            await telegram_call_with_retry(
                lambda chat_id=chat_id: context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                )
            )
            sent_count += 1
        except Forbidden:
            forbidden_count += 1
        except BadRequest:
            bad_request_count += 1
        except Exception:
            other_error_count += 1

        await asyncio.sleep(0.05)

    await update.message.reply_text(
        (
            "✅ Broadcast selesai.\n"
            f"Target: {len(target_ids)}\n"
            f"Terkirim: {sent_count}\n"
            f"Blocked/Forbidden: {forbidden_count}\n"
            f"Bad Request: {bad_request_count}\n"
            f"Error Lain: {other_error_count}"
        ),
        reply_markup=admin_menu_keyboard(),
    )
    return ADMIN_ACTION
