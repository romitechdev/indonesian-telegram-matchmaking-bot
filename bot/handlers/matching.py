from telegram import Update
from telegram.ext import ContextTypes

from ..keyboards import admin_menu_keyboard, main_menu_keyboard, next_profile_keyboard, report_reason_keyboard
from ..services.matching_service import matching_service
from ..services.user_service import user_service
from ..utils import (
    escape_html,
    get_ban_notice,
    get_current_match,
    get_target_gender,
    haversine,
    is_admin,
    is_temporarily_banned,
    format_username,
    telegram_call_with_retry,
)


async def send_daily_limit_notice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit = matching_service.get_daily_view_limit()
    await telegram_call_with_retry(
        lambda: context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"⏳ Batas lihat profil harian kamu sudah habis ({limit} profil/hari).\n"
                "Limit akan reset otomatis setiap hari. Coba lagi besok ya~"
            ),
            reply_markup=main_menu_keyboard(),
        )
    )


async def disabled_chat_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Fitur Match/Chat otomatis sudah dinonaktifkan ya.",
        reply_markup=next_profile_keyboard(),
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

    pending_notifications = user_service.consume_pending_notifications(user.id)
    for notification in pending_notifications:
        notice_text = notification.get("text")
        if notice_text:
            await update.message.reply_text(notice_text)

    context.user_data.pop("pending_report", None)
    context.user_data.pop("recent_mutual_match_target_id", None)
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

    if not matching_service.has_remaining_daily_views(user.id):
        context.user_data.pop("matches", None)
        context.user_data.pop("current_match_index", None)
        await send_daily_limit_notice(update, context)
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
    matches = context.user_data.get("matches")
    current_index = context.user_data.get("current_match_index")

    if not matches or current_index is None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Belum ada sesi pencarian aktif. Klik 🔍 Cari Teman dulu ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    if current_index >= len(matches):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✨ *Udah kelar semua nih!* ✨\n"
            "Coba lagi nanti ya siapa tau ada yang baru~",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        return

    if not matching_service.has_remaining_daily_views(update.effective_user.id):
        context.user_data.pop("matches", None)
        context.user_data.pop("current_match_index", None)
        context.user_data.pop("pending_report", None)
        await send_daily_limit_notice(update, context)
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

    source_lat = current_user.get("latitude")
    source_lon = current_user.get("longitude")
    target_lat = match.get("latitude")
    target_lon = match.get("longitude")
    if source_lat is None or source_lon is None or target_lat is None or target_lon is None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Profil ini belum punya data lokasi lengkap. Kita lanjut ke profil berikutnya ya~",
            reply_markup=next_profile_keyboard(),
        )
        context.user_data["current_match_index"] += 1
        await show_match(update, context)
        return

    distance = haversine(
        source_lat,
        source_lon,
        target_lat,
        target_lon,
    )

    if distance < 1:
        distance_str = f"📍 {distance * 1000:.0f} m"
    else:
        distance_str = f"📍 {distance:.1f} km"

    compatibility_score = match.get("compatibility_score", 0)
    gender_icon = (
        "♂️"
        if match.get("gender") == "Cowok"
        else "♀️" if match.get("gender") == "Cewek" else "👤"
    )
    escaped_name = escape_html(match.get("name", "Tanpa Nama"))
    escaped_age = escape_html(match.get("age", "?"))
    caption_lines = [
        f"✨ {escaped_name}, {escaped_age} {gender_icon}",
        distance_str,
    ]
    if compatibility_score:
        caption_lines.append(f"💞 Kecocokan jawaban: {compatibility_score}/3")

    description = (match.get("description") or "").strip()
    if description:
        caption_lines.extend(["", escape_html(description)])

    caption = "\n".join(caption_lines)

    photo_file_id = match.get("photo_file_id")
    if photo_file_id:
        try:
            await telegram_call_with_retry(
                lambda: context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo_file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=next_profile_keyboard(),
                )
            )
        except Exception:
            await telegram_call_with_retry(
                lambda: context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=next_profile_keyboard(),
                )
            )
    else:
        await telegram_call_with_retry(
            lambda: context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption,
                parse_mode="HTML",
                reply_markup=next_profile_keyboard(),
            )
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


async def like_current_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user):
        await update.message.reply_text(
            "Fitur ini khusus akun user.",
            reply_markup=admin_menu_keyboard(),
        )
        return

    profile = user_service.get_profile(user.id)
    if not profile:
        await update.message.reply_text(
            "Profil kamu tidak ditemukan. Klik /start dulu ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

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

    result = matching_service.like_profile(profile, match)
    if result["status"] == "invalid_target":
        await update.message.reply_text(
            "Profil ini belum bisa di-like. Coba profil berikutnya ya~",
            reply_markup=next_profile_keyboard(),
        )
        return

    target_telegram_id = match.get("telegram_id")
    target_name = match.get("name", "Seseorang")
    
    from ..config import logger
    logger.info(f"Like action - result: {result}, target_id: {target_telegram_id}")

    if result["status"] == "liked":
        # One-sided like - send notification to target without revealing who
        logger.info(f"One-sided like detected. Sending notification to {target_telegram_id}")
        if target_telegram_id is not None:
            try:
                logger.info(f"About to send message to {target_telegram_id}")
                response = await context.bot.send_message(
                    chat_id=target_telegram_id,
                    text="💖 Seseorang telah ❤️ Like profilmu!\n\nCoba cari tahu siapa dengan like balik mereka~\nKalau kalian saling like, kalian bisa terhubung 😊"
                )
                logger.info(f"✅ Notification sent successfully to {target_telegram_id}, message_id={response.message_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send like notification to {target_telegram_id}: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                user_service.enqueue_pending_notification(
                    target_telegram_id,
                    "💖 Seseorang telah ❤️ Like profilmu!\n\n"
                    "Coba cari tahu siapa dengan like balik mereka~\n"
                    "Kalau kalian saling like, kalian bisa terhubung 😊",
                )
        else:
            logger.warning(f"target_telegram_id is None, cannot send notification")

    if result["is_match"]:
        # Mutual match - reveal Telegram IDs
        context.user_data["recent_mutual_match_target_id"] = target_telegram_id

        target_profile = (
            user_service.get_profile(target_telegram_id)
            if target_telegram_id is not None
            else None
        )
        icebreakers = matching_service.generate_icebreakers(profile, target_profile or match)
        if match.get("telegram_id") is not None:
            contact_line = f"Kontak dia via Telegram ID: {match['telegram_id']}"
        else:
            contact_line = "Kontak dia belum tersedia."

        await update.message.reply_text(
            "🎉 MATCH! Kalian saling like 💖\n"
            f"{contact_line}\n\n"
            "Icebreaker buat mulai chat:\n"
            f"1) {icebreakers[0]}\n"
            f"2) {icebreakers[1]}\n"
            f"3) {icebreakers[2]}\n\n"
            "Setelah chat jalan, klik tombol 💬 Sudah Chat ya.",
            reply_markup=next_profile_keyboard(),
        )

        if result.get("is_new_match"):
            liker_name = profile.get("name", "Seseorang")
            liker_telegram_id = profile.get("telegram_id", "-")
            notify_icebreakers = matching_service.generate_icebreakers(target_profile or match, profile)
            if target_telegram_id is not None:
                try:
                    await telegram_call_with_retry(
                        lambda: context.bot.send_message(
                            chat_id=target_telegram_id,
                            text=(
                                f"🎉 MATCH! Kamu juga dilike oleh {liker_name}! 💖\n"
                                f"Kontak Telegram ID: {liker_telegram_id}\n\n"
                                "Coba mulai dari icebreaker ini:\n"
                                f"1) {notify_icebreakers[0]}\n"
                                f"2) {notify_icebreakers[1]}\n"
                                f"3) {notify_icebreakers[2]}"
                            ),
                            reply_markup=main_menu_keyboard(),
                        )
                    )
                except Exception:
                    pass

    if "matches" in context.user_data and "current_match_index" in context.user_data:
        context.user_data["current_match_index"] += 1
        await show_match(update, context)


async def mark_chat_started(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user):
        await update.message.reply_text(
            "Fitur ini khusus akun user.",
            reply_markup=admin_menu_keyboard(),
        )
        return

    target_telegram_id = context.user_data.get("recent_mutual_match_target_id")
    if target_telegram_id is None:
        await update.message.reply_text(
            "Belum ada match terbaru yang bisa dicatat. Like dulu sampai dapat mutual match ya~",
            reply_markup=next_profile_keyboard(),
        )
        return

    matching_service.mark_chat_started(
        first_telegram_id=user.id,
        second_telegram_id=target_telegram_id,
        started_by=user.id,
    )

    await update.message.reply_text(
        "✅ Dicatat! Semoga obrolannya lancar ya ✨",
        reply_markup=main_menu_keyboard(),
    )


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
