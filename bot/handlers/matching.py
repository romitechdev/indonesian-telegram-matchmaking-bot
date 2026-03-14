from telegram import Update
from telegram.ext import ContextTypes

from ..keyboards import admin_menu_keyboard, main_menu_keyboard, next_profile_keyboard, report_reason_keyboard
from ..services.matching_service import matching_service
from ..services.user_service import user_service
from ..utils import (
    get_ban_notice,
    get_current_match,
    get_target_gender,
    haversine,
    is_admin,
    is_temporarily_banned,
    format_username,
)


async def find_nearby_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if is_admin(user):
        await update.message.reply_text(
            "Akun admin tidak bisa pakai fitur cari teman.",
            reply_markup=admin_menu_keyboard(),
        )
        return

    user_service.sync_identity(user)
    context.user_data.pop("pending_report", None)
    current_user = user_service.get_active_profile(user.id)

    if not current_user:
        await update.message.reply_text(
            "Kamu harus bikin profile dulu! Klik /start ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    if is_temporarily_banned(current_user):
        await update.message.reply_text(
            get_ban_notice(current_user),
            reply_markup=main_menu_keyboard(),
        )
        return

    target_gender = get_target_gender(current_user.get("gender"))
    if not target_gender:
        await update.message.reply_text(
            "Gender kamu belum valid untuk matching. Coba edit gender dulu ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    source_lat = current_user.get("latitude")
    source_lon = current_user.get("longitude")
    if source_lat is None or source_lon is None:
        await update.message.reply_text(
            "Lokasi kamu belum ada. Coba update lokasi dulu ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    matches = matching_service.find_matches_for_user(current_user)

    if not matches:
        await update.message.reply_text(
            "😢 *Waduh belum ada yang deket nih...*\n"
            "Coba lagi nanti ya atau cari yang lebih jauh~",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        return

    context.user_data["matches"] = matches
    context.user_data["current_match_index"] = 0

    await show_match(update, context)


async def show_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matches = context.user_data["matches"]
    current_index = context.user_data["current_match_index"]

    if current_index >= len(matches):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✨ *Udah kelar semua nih!* ✨\n"
            "Coba lagi nanti ya siapa tau ada yang baru~",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        return

    match = matches[current_index]

    matching_service.record_seen_profile(update.effective_user.id, match["_id"])

    current_user = user_service.get_profile(update.effective_user.id)
    if not current_user:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Terjadi kesalahan, profile kamu tidak ditemukan. Silahkan /start ulang ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    distance = haversine(
        current_user["latitude"],
        current_user["longitude"],
        match["latitude"],
        match["longitude"],
    )

    if distance < 1:
        distance_str = f"📍 {distance * 1000:.0f} m"
    else:
        distance_str = f"📍 {distance:.1f} km"

    caption = (
        f"✨ *{match['name']}*, {match['age']} {'♂️' if match['gender'] == 'Cowok' else '♀️'}\n"
        f"{distance_str}\n\n"
        f"_{match['description']}_\n\n"
    )

    if match.get("username"):
        caption += f"💬 Chat: {format_username(match.get('username'))}"
    else:
        caption += (
            "📵 Dia belum punya username Telegram\n"
            "👉 Minta dia aktifkan username dulu biar bisa langsung di-chat"
        )

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=match["photo_file_id"],
        caption=caption,
        reply_markup=next_profile_keyboard(),
        parse_mode="Markdown",
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✩♬₊˚.🎧⋆☾✩♬₊˚.🎧⋆☾⋆⁺₊✧",
        reply_markup=next_profile_keyboard(),
    )


async def next_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "matches" not in context.user_data or "current_match_index" not in context.user_data:
        await update.message.reply_text(
            "Belum ada sesi pencarian aktif. Klik 🔍 Cari Teman dulu ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    context.user_data.pop("pending_report", None)
    context.user_data["current_match_index"] += 1
    await show_match(update, context)


async def block_current_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user):
        await update.message.reply_text(
            "Fitur ini khusus akun user.",
            reply_markup=admin_menu_keyboard(),
        )
        return

    profile = user_service.get_profile(user.id)
    if is_temporarily_banned(profile):
        await update.message.reply_text(
            get_ban_notice(profile),
            reply_markup=main_menu_keyboard(),
        )
        return

    match = get_current_match(context)
    if not match:
        await update.message.reply_text(
            "Belum ada profil aktif. Klik 🔍 Cari Teman dulu ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    target_telegram_id = match.get("telegram_id")
    if target_telegram_id is None:
        await update.message.reply_text(
            "Gagal blokir profil ini. Coba lanjut ke profil berikutnya ya~",
            reply_markup=next_profile_keyboard(),
        )
        return

    matching_service.create_block(user.id, match, reason="Manual block")

    context.user_data.pop("pending_report", None)
    await update.message.reply_text(
        f"🚫 {match.get('name', 'Profil ini')} berhasil diblokir. Kita lanjut profil lain ya~",
        reply_markup=next_profile_keyboard(),
    )

    context.user_data["current_match_index"] += 1
    await show_match(update, context)


async def report_current_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user):
        await update.message.reply_text(
            "Fitur ini khusus akun user.",
            reply_markup=admin_menu_keyboard(),
        )
        return

    profile = user_service.get_profile(user.id)
    if is_temporarily_banned(profile):
        await update.message.reply_text(
            get_ban_notice(profile),
            reply_markup=main_menu_keyboard(),
        )
        return

    match = get_current_match(context)
    if not match:
        await update.message.reply_text(
            "Belum ada profil aktif. Klik 🔍 Cari Teman dulu ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    target_telegram_id = match.get("telegram_id")
    if target_telegram_id is None:
        await update.message.reply_text(
            "Gagal report profil ini. Coba lanjut ke profil berikutnya ya~",
            reply_markup=next_profile_keyboard(),
        )
        return

    context.user_data["pending_report"] = {
        "reported_telegram_id": target_telegram_id,
        "reported_profile_id": match.get("_id"),
        "reported_name": match.get("name"),
    }

    await update.message.reply_text(
        "Pilih alasan report untuk profil ini ya:",
        reply_markup=report_reason_keyboard(),
    )


async def submit_report_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_report = context.user_data.get("pending_report")
    if not pending_report:
        await update.message.reply_text(
            "Tidak ada report aktif. Klik ⚠️ Report saat lihat profil ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    reason = update.message.text.strip()
    if reason == "❌ Batal Report":
        context.user_data.pop("pending_report", None)
        await update.message.reply_text(
            "Oke, report dibatalkan.",
            reply_markup=next_profile_keyboard(),
        )
        return

    user = update.effective_user
    matching_service.create_report_and_block(user.id, pending_report, reason)

    context.user_data.pop("pending_report", None)
    await update.message.reply_text(
        "✅ Laporan diterima dan profil sudah diblokir. Terima kasih sudah bantu jaga komunitas 🙏",
        reply_markup=next_profile_keyboard(),
    )

    if "matches" in context.user_data and "current_match_index" in context.user_data:
        context.user_data["current_match_index"] += 1
        await show_match(update, context)
