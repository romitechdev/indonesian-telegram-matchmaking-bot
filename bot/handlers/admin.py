from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

from ..config import (
    ADMIN_ACTION,
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
    format_username,
    format_utc,
    is_admin,
    is_temporarily_banned,
)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_service.sync_identity(update.effective_user)
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "✨ *Admin Panel* ✨\n\nPilih menu dibawah ini:",
        reply_markup=admin_menu_keyboard(),
        parse_mode="Markdown",
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

    header = "📋 *Daftar Pengguna* (50 terbaru):\n\n"
    current_msg = header
    for user in users:
        status = "🟢" if user.get("is_active", True) else "🔴"
        ban_status = "⛔ BANNED" if is_temporarily_banned(user) else ""
        entry = (
            f"{status} *{user['name']}*, {user['age']}\n"
            f"ID: `{user['_id']}`\n"
            f"Username: {format_username(user.get('username'))}\n"
            f"Ban: {ban_status or 'tidak'}\n"
            f"Terdaftar: {user['created_at'].strftime('%d/%m/%Y')}\n\n"
        )
        if len(current_msg) + len(entry) > 4000:
            await update.message.reply_text(current_msg, parse_mode="Markdown")
            current_msg = entry
        else:
            current_msg += entry

    await update.message.reply_text(
        current_msg,
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard(),
    )


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    stats = user_service.get_stats()

    message = (
        "📊 *Statistik Pengguna*\n\n"
        f"👥 Total Pengguna: *{stats['total_users']}*\n"
        f"🟢 Aktif: *{stats['active_users']}* | 🔴 Nonaktif: *{stats['inactive_users']}*\n"
    )

    message += "\n🚻 *Gender*:\n"
    for gender in stats["gender_stats"]:
        message += f"- {gender['_id']}: {gender['count']}\n"

    await update.message.reply_text(
        message,
        parse_mode="Markdown",
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

    header = "🚨 *Laporan Keamanan* (30 terbaru):\n\n"
    current_msg = header

    for report in reports:
        entry = (
            f"ID Report: `{report['id']}`\n"
            f"🚨 *{report['reason']}*\n"
            f"Pelapor: {report['reporter_name']} ({report['reporter_username']}) | `{report['reporter_id']}`\n"
            f"Dilaporkan: {report['reported_name']} ({report['reported_username']}) | `{report['reported_id']}`\n"
            f"Waktu: {report['created_at']} | Status: {report['status']} | Resolved: {report['resolved_at']}\n\n"
        )

        if len(current_msg) + len(entry) > 4000:
            await update.message.reply_text(current_msg, parse_mode="Markdown")
            current_msg = entry
        else:
            current_msg += entry

    await update.message.reply_text(
        current_msg,
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard(),
    )

    return ADMIN_ACTION


async def resolve_report_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ Masukkan *ID Report* yang mau di-resolve:\n"
        "(Lihat ID dari menu 🚨 Reports)",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADMIN_RESOLVE_REPORT


async def resolve_report_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report_id_text = update.message.text.strip()

    result = moderation_service.resolve_report(report_id_text, update.effective_user.id)
    if result["status"] == "invalid_id":
        await update.message.reply_text(
            "❌ Format ID report tidak valid.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION
    if result["status"] == "not_found":
        await update.message.reply_text(
            "❌ Report tidak ditemukan.",
            reply_markup=admin_menu_keyboard(),
        )
        return ADMIN_ACTION

    await update.message.reply_text(
        f"✅ Report `{result['report_id']}` sudah di-resolve.",
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard(),
    )
    return ADMIN_ACTION


async def temp_ban_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "⛔ Kirim data ban dengan format:\n"
        "`telegram_id durasi_jam alasan`\n"
        "Contoh: `6347607133 24 Report penipuan`\n"
        f"Default durasi: {TEMP_BAN_DEFAULT_HOURS} jam",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADMIN_TEMP_BAN


async def temp_ban_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    parts = raw_text.split()

    if len(parts) < 1 or not parts[0].isdigit():
        await update.message.reply_text(
            "❌ Format salah. Minimal isi `telegram_id`.",
            parse_mode="Markdown",
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

    reason = " ".join(parts[reason_start_index:]).strip() or "Pelanggaran aturan komunitas"
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
        f"User ID: `{target_telegram_id}`\n"
        f"Sampai: {format_utc(ban_result['ban_until'])}\n"
        f"Alasan: {ban_result['reason']}",
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard(),
    )
    return ADMIN_ACTION


async def find_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Akses ditolak!")
        return ConversationHandler.END

    await update.message.reply_text(
        "🔍 Masukkan ID atau username pengguna (tanpa @):",
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
        "📋 *Detail Pengguna*\n\n"
        f"🆔 ID: `{user['_id']}`\n"
        f"👤 Nama: *{user['name']}*, {user['age']}\n"
        f"🚻 Gender: {user['gender']}\n"
        f"📱 Username: {format_username(user.get('username'))}\n"
        f"📍 Lokasi: {user.get('latitude', '?')}, {user.get('longitude', '?')}\n"
        f"📅 Terdaftar: {user['created_at'].strftime('%d/%m/%Y %H:%M')}\n"
        f"🔄 Terakhir update: {user.get('last_updated', user['created_at']).strftime('%d/%m/%Y %H:%M')}\n"
        f"🔘 Status: {status}\n\n"
        f"⛔ Ban Status: {ban_status}\n"
        f"⏳ Ban Sampai: {ban_until}\n"
        f"🧾 Alasan Ban: {ban_reason}\n\n"
        f"📝 Bio:\n_{user.get('description', 'tidak ada')}_"
    )

    if user.get("photo_file_id"):
        await update.message.reply_photo(
            photo=user["photo_file_id"],
            caption=message,
            parse_mode="Markdown",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
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
            f"✅ Pengguna dengan ID `{user_id}` berhasil dihapus!",
            parse_mode="Markdown",
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
