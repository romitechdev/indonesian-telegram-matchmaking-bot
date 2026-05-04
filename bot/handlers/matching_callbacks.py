"""Callback handlers for match notifications."""

from telegram import Update
from telegram.ext import ContextTypes
from bson.objectid import ObjectId

from ..keyboards import next_profile_keyboard
from ..services.user_service import user_service
from ..services.matching_service import matching_service
from ..config import logger
from ..utils import telegram_call_with_retry, escape_html


async def handle_match_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle match notification buttons (show/ignore)."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    responder = query.from_user

    handlers = {
        "match_show_": _handle_match_show,
        "match_nope_": _handle_match_ignore,
    }

    for prefix, handler in handlers.items():
        if data.startswith(prefix):
            match_id = data[len(prefix) :]
            await handler(query, context, match_id, responder)
            return


async def _handle_match_show(query, context, match_id, responder):
    """Target clicks 'Tunjukkan' → show the match profile."""
    try:
        # Try to get match details from the ID
        try:
            oid = ObjectId(match_id) if not isinstance(match_id, ObjectId) else match_id
        except Exception:
            await query.edit_message_text("ID match tidak valid.")
            return

        match_doc = matching_service.matches_repo.collection.find_one({"_id": oid})
        if not match_doc:
            await query.edit_message_text("Data match tidak ditemukan.")
            return

        # Determine the other party in the match
        first_id = match_doc.get("first_telegram_id")
        second_id = match_doc.get("second_telegram_id")
        other_id = second_id if first_id == responder.id else first_id

        if other_id is None:
            await query.edit_message_text("Tidak bisa menampilkan profil match.")
            return

        other_profile = user_service.get_profile(other_id)
        if not other_profile:
            await query.edit_message_text("Profil match tidak ditemukan.")
            return

        # Get responder's profile for distance calculation
        responder_profile = user_service.get_profile(responder.id)

        # Build match display text
        name = escape_html(other_profile.get("name", "Tanpa Nama"))
        age = escape_html(str(other_profile.get("age", "?")))
        gender = escape_html(other_profile.get("gender", "-"))
        description = escape_html((other_profile.get("description") or "-").strip())
        telegram_id = other_profile.get("telegram_id", "-")

        # Calculate distance
        resp_lat = responder_profile.get("latitude") if responder_profile else None
        resp_lon = responder_profile.get("longitude") if responder_profile else None
        other_lat = other_profile.get("latitude")
        other_lon = other_profile.get("longitude")

        if resp_lat and resp_lon and other_lat and other_lon:
            from ..utils import haversine

            distance_km = haversine(resp_lat, resp_lon, other_lat, other_lon)
            if distance_km < 1:
                location_line = f"📍 Jarak: {distance_km * 1000:.0f} m"
            else:
                location_line = f"📍 Jarak: {distance_km:.1f} km"
        else:
            location_line = "📍 Jarak: tidak tersedia"

        if telegram_id and telegram_id != "-":
            contact_line = f'Kontak: <a href="tg://user?id={telegram_id}">{name}</a>'
        else:
            contact_line = "Kontak Telegram ID: -"

        caption = (
            f"🎉 <b>MATCH! Ini profil match kamu:</b>\n\n"
            f"👤 {name}, {age}\n"
            f"🧭 Gender: {gender}\n"
            f"{location_line}\n"
            f"📝 {description}\n\n"
            f"{contact_line}"
        )

        await query.edit_message_text("✨ Profil ditunjukkan di bawah 👇")
        await telegram_call_with_retry(
            lambda: context.bot.send_message(
                chat_id=query.message.chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=next_profile_keyboard(),
            )
        )
    except Exception as e:
        logger.error(f"Failed to handle match show: {e}")
        try:
            await query.edit_message_text("Terjadi kesalahan saat menampilkan profil.")
        except Exception:
            pass


async def _handle_match_ignore(query, context, match_id, responder):
    """Target clicks 'Nggak, makasih' → dismiss the match."""
    try:
        await query.edit_message_text("Oke, tidak apa-apa 👋")
    except Exception as e:
        logger.error(f"Failed to handle match ignore: {e}")
        try:
            await query.edit_message_text("Terjadi kesalahan.")
        except Exception:
            pass
