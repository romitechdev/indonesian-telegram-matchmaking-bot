from telegram import Update
from telegram.ext import ContextTypes

from ..config import logger
from ..keyboards import (
    active_chat_keyboard,
    main_menu_keyboard,
    waiting_chat_keyboard,
    report_reason_keyboard,
)
from ..services.chat_service import chat_service
from ..services.user_service import user_service
from ..utils import (
    escape_html,
    get_ban_notice,
    haversine,
    is_admin,
    is_temporarily_banned,
    telegram_call_with_retry,
)


async def _send_profile_preview(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    receiver_chat_id: int,
    receiver_profile: dict,
    partner_profile: dict,
    intro_text: str,
):
    name = escape_html(partner_profile.get("name", "Tanpa Nama"))
    age = escape_html(partner_profile.get("age", "?"))
    gender = escape_html(partner_profile.get("gender", "-"))
    description = escape_html((partner_profile.get("description") or "-").strip())
    receiver_lat = receiver_profile.get("latitude") if receiver_profile else None
    receiver_lon = receiver_profile.get("longitude") if receiver_profile else None
    partner_lat = partner_profile.get("latitude")
    partner_lon = partner_profile.get("longitude")

    if (
        receiver_lat is not None
        and receiver_lon is not None
        and partner_lat is not None
        and partner_lon is not None
    ):
        distance_km = haversine(receiver_lat, receiver_lon, partner_lat, partner_lon)
        if distance_km < 1:
            location_line = f"📍 Jarak: {distance_km * 1000:.0f} m"
        else:
            location_line = f"📍 Jarak: {distance_km:.1f} km"
    else:
        location_line = "📍 Jarak: tidak tersedia"

    caption = (
        f"{intro_text}\n\n"
        f"👤 {name}, {age}\n"
        f"🧭 Gender: {gender}\n"
        f"{location_line}\n"
        f"📝 {description}"
    )

    # Telegram photo caption has a tighter limit (1024 chars).
    photo_caption = caption
    if len(photo_caption) > 1000:
        photo_caption = f"{photo_caption[:997]}..."

    photo_file_id = partner_profile.get("photo_file_id")
    if photo_file_id:
        try:
            await telegram_call_with_retry(
                lambda: context.bot.send_photo(
                    chat_id=receiver_chat_id,
                    photo=photo_file_id,
                    caption=photo_caption,
                    parse_mode="HTML",
                    reply_markup=active_chat_keyboard(),
                )
            )
            return
        except Exception as exc:
            logger.warning(
                "Failed send_photo with stored file_id for user %s -> %s: %s",
                partner_profile.get("telegram_id"),
                receiver_chat_id,
                exc,
            )

            # Try refresh from Telegram profile photo in case stored file_id is stale.
            partner_id = partner_profile.get("telegram_id")
            if partner_id:
                try:
                    photos = await telegram_call_with_retry(
                        lambda: context.bot.get_user_profile_photos(
                            user_id=partner_id, limit=1
                        )
                    )
                    if (
                        photos
                        and photos.total_count > 0
                        and photos.photos
                        and photos.photos[0]
                    ):
                        refreshed_photo_id = photos.photos[0][-1].file_id
                        user_service.update_profile_fields(
                            partner_id,
                            {"photo_file_id": refreshed_photo_id},
                        )
                        await telegram_call_with_retry(
                            lambda: context.bot.send_photo(
                                chat_id=receiver_chat_id,
                                photo=refreshed_photo_id,
                                caption=photo_caption,
                                parse_mode="HTML",
                                reply_markup=active_chat_keyboard(),
                            )
                        )
                        return
                except Exception as refresh_exc:
                    logger.warning(
                        "Failed refresh photo_file_id for user %s: %s",
                        partner_id,
                        refresh_exc,
                    )

    await telegram_call_with_retry(
        lambda: context.bot.send_message(
            chat_id=receiver_chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=active_chat_keyboard(),
        )
    )


async def start_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user):
        await update.message.reply_text(
            "Akun admin tidak bisa pakai fitur obrolan.",
            reply_markup=main_menu_keyboard(),
        )
        return

    profile = chat_service.get_profile(user.id)
    if not profile:
        await update.message.reply_text(
            "Kamu harus daftar dulu. Klik /start ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    if is_temporarily_banned(profile):
        await update.message.reply_text(
            get_ban_notice(profile),
            reply_markup=main_menu_keyboard(),
        )
        return

    result = chat_service.start_or_match(user.id)
    status = result.get("status")

    if status == "invalid_gender":
        await update.message.reply_text(
            "Gender profil kamu belum valid untuk matching. Edit profil dulu ya.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if status == "waiting":
        await update.message.reply_text(
            "🔎 Menunggu partner ngobrol...",
            reply_markup=waiting_chat_keyboard(),
        )
        return

    if status == "already_chatting":
        await update.message.reply_text(
            "Kamu masih dalam sesi chat. Pakai ⏭️ Next atau ⛔ Stop kalau mau ganti.",
            reply_markup=active_chat_keyboard(),
        )
        return

    if status != "matched":
        await update.message.reply_text(
            "Gagal mulai obrolan. Coba lagi ya.",
            reply_markup=main_menu_keyboard(),
        )
        return

    partner_id = result.get("partner_id")
    partner_profile = chat_service.get_profile(partner_id) if partner_id else None
    if not partner_profile:
        await update.message.reply_text(
            "Partner tidak ditemukan. Coba mulai obrolan lagi.",
            reply_markup=main_menu_keyboard(),
        )
        return

    self_profile = profile or {}
    await _send_profile_preview(
        context=context,
        receiver_chat_id=user.id,
        receiver_profile=self_profile,
        partner_profile=partner_profile,
        intro_text="🎉 Match ditemukan! Ini profil partner kamu:",
    )

    try:
        await _send_profile_preview(
            context=context,
            receiver_chat_id=partner_id,
            receiver_profile=partner_profile,
            partner_profile=self_profile,
            intro_text="🎉 Match ditemukan! Ini profil partner kamu:",
        )
    except Exception:
        # If partner cannot be reached, end both sides to avoid dead session.
        chat_service.stop_chat(user.id)
        await update.message.reply_text(
            "Partner tidak bisa dihubungi saat ini. Silakan coba lagi.",
            reply_markup=main_menu_keyboard(),
        )


async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    partner_id = chat_service.stop_chat(user.id)

    await update.message.reply_text(
        "Sesi obrolan dihentikan.",
        reply_markup=main_menu_keyboard(),
    )

    if partner_id:
        try:
            await context.bot.send_message(
                chat_id=partner_id,
                text="Partner kamu menghentikan obrolan.",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            pass

    # Show pending notifications after chat ends
    pending_notifications = user_service.consume_pending_notifications(user.id)
    for notification in pending_notifications:
        notice_text = notification.get("text")
        if notice_text:
            try:
                await update.message.reply_text(notice_text)
            except Exception:
                pass


async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    previous_partner_id = chat_service.stop_chat(user.id)

    if previous_partner_id:
        try:
            await context.bot.send_message(
                chat_id=previous_partner_id,
                text="Partner kamu memilih Next dan meninggalkan obrolan.",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            pass

    await start_chat(update, context)


async def relay_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user):
        return

    if not update.message:
        return

    text = update.message.text
    photo = None
    image_document = None
    caption = None

    if update.message.photo:
        photo = update.message.photo[-1]
        caption = update.message.caption
    elif update.message.document and (
        update.message.document.mime_type or ""
    ).startswith("image/"):
        image_document = update.message.document
        caption = update.message.caption
    elif not text:
        return

    check_text = text or caption or ""

    blocked_commands = {
        "💬 Mulai Obrolan",
        "👀 Profile Saya",
        "✏️ Edit Profile",
        "🚪 Keluar",
        "🏠 Menu Utama",
        "⏭️ Next",
        "⛔ Stop",
        "❌ Batal Cari",
        "👁️ Lihat Profil",
        "❤️",
        "💌",
        "👎",
    }
    if check_text.strip() in blocked_commands:
        return

    # If user is composing a discover message, intercept the text
    if context.user_data.get("discover_awaiting_message") and text:
        from .discover import discover_send_message_submit

        handled = await discover_send_message_submit(update, context)
        if handled:
            return

    partner_id = chat_service.get_partner_id(user.id)
    if not partner_id:
        if chat_service.is_waiting(user.id):
            await update.message.reply_text(
                "Masih menunggu partner. Sabar sebentar ya...",
                reply_markup=waiting_chat_keyboard(),
            )
        return

    try:
        if photo:
            await telegram_call_with_retry(
                lambda: context.bot.send_photo(
                    chat_id=partner_id,
                    photo=photo.file_id,
                    caption=caption,
                    reply_markup=active_chat_keyboard(),
                )
            )
            record_text = caption or ""
            photo_file_id = photo.file_id
        elif image_document:
            await telegram_call_with_retry(
                lambda: context.bot.send_document(
                    chat_id=partner_id,
                    document=image_document.file_id,
                    caption=caption,
                    reply_markup=active_chat_keyboard(),
                )
            )
            record_text = caption or ""
            photo_file_id = image_document.file_id
        else:
            await telegram_call_with_retry(
                lambda: context.bot.send_message(
                    chat_id=partner_id,
                    text=text,
                    reply_markup=active_chat_keyboard(),
                )
            )
            record_text = text
            photo_file_id = None

        # store transcript
        try:
            chat_service.record_message(
                update.effective_user.id, partner_id, record_text, photo_file_id
            )
        except Exception:
            logger.exception(
                "Failed to record chat message for %s -> %s",
                update.effective_user.id,
                partner_id,
            )
    except Exception:
        chat_service.stop_chat(user.id)
        await update.message.reply_text(
            "Partner tidak bisa dihubungi. Sesi chat dihentikan.",
            reply_markup=main_menu_keyboard(),
        )


async def report_current_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user):
        await update.message.reply_text(
            "Fitur ini khusus akun user.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if not update.message:
        return

    partner_id = chat_service.get_partner_id(user.id)
    if not partner_id:
        await update.message.reply_text(
            "Belum ada partner aktif untuk dilaporkan.",
            reply_markup=main_menu_keyboard(),
        )
        return

    context.user_data["pending_report"] = {
        "reported_telegram_id": partner_id,
        "reported_profile_id": None,
        "reported_name": None,
    }

    await update.message.reply_text(
        "Pilih alasan report untuk partner ini:",
        reply_markup=report_reason_keyboard(),
    )


async def submit_chat_report_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_report = context.user_data.get("pending_report")
    if not pending_report:
        await update.message.reply_text(
            "Tidak ada report aktif. Klik ⚠️ Laporkan saat chat untuk lapor partner.",
            reply_markup=main_menu_keyboard(),
        )
        return

    reason = update.message.text.strip()
    if reason == "❌ Batal Report":
        context.user_data.pop("pending_report", None)
        await update.message.reply_text(
            "Oke, report dibatalkan.",
            reply_markup=active_chat_keyboard(),
        )
        return

    user = update.effective_user
    from ..services.matching_service import matching_service

    matching_service.create_report_and_block(user.id, pending_report, reason)

    context.user_data.pop("pending_report", None)
    await update.message.reply_text(
        "✅ Laporan diterima dan partner diblokir. Terima kasih.",
        reply_markup=active_chat_keyboard(),
    )
