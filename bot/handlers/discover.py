"""Handlers for the Discover / Lihat Profil feature."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..config import DISCOVER_MESSAGE_MAX_LENGTH, logger
from ..keyboards import (
    admin_menu_keyboard,
    discover_profile_keyboard,
    main_menu_keyboard,
)
from ..services.matching_service import matching_service
from ..services.user_service import user_service
from ..utils import (
    escape_html,
    get_ban_notice,
    haversine,
    is_admin,
    is_temporarily_banned,
    telegram_call_with_retry,
)

# ─── helpers ────────────────────────────────────────────────────────────


def _get_discover_match(context):
    matches = context.user_data.get("discover_matches")
    idx = context.user_data.get("discover_match_index")
    if not matches or idx is None or idx < 0 or idx >= len(matches):
        return None
    return matches[idx]


def _build_profile_text(profile, viewer_profile=None):
    """Build profile display text WITHOUT contact info."""
    name = escape_html(profile.get("name", "Tanpa Nama"))
    age = escape_html(profile.get("age", "?"))
    gender = profile.get("gender", "")
    icon = "♂️" if gender == "Cowok" else "♀️" if gender == "Cewek" else "👤"
    lines = [f"✨ {name}, {age} {icon}"]

    if viewer_profile:
        v_lat, v_lon = viewer_profile.get("latitude"), viewer_profile.get("longitude")
        p_lat, p_lon = profile.get("latitude"), profile.get("longitude")
        if all(x is not None for x in [v_lat, v_lon, p_lat, p_lon]):
            d = haversine(v_lat, v_lon, p_lat, p_lon)
            lines.append(f"📍 {d*1000:.0f} m" if d < 1 else f"📍 {d:.1f} km")

    score = profile.get("compatibility_score", 0)
    if score:
        lines.append(f"💞 Kecocokan: {score}/3")

    desc = (profile.get("description") or "").strip()
    if desc:
        lines.extend(["", f"📝 {escape_html(desc)}"])
    return "\n".join(lines)


def _gender_label(gender):
    if gender == "Cowok":
        return "cowok"
    if gender == "Cewek":
        return "cewek"
    return "orang"


async def _edit_or_caption(query, text, **kwargs):
    """Edit message text or caption depending on message type."""
    try:
        if query.message and query.message.photo:
            await query.edit_message_caption(caption=text, **kwargs)
        else:
            await query.edit_message_text(text=text, **kwargs)
    except Exception:
        pass


async def _send_profile_with_photo(
    context, chat_id, profile, caption, reply_markup=None
):
    """Send profile photo + caption. Falls back to text if no photo."""
    photo = profile.get("photo_file_id")
    if photo:
        try:
            await telegram_call_with_retry(
                lambda: context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            )
            return
        except Exception:
            pass
    await telegram_call_with_retry(
        lambda: context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    )


# ─── browsing ───────────────────────────────────────────────────────────


async def start_discover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user):
        await update.message.reply_text(
            "Akun admin tidak bisa pakai fitur ini.", reply_markup=admin_menu_keyboard()
        )
        return

    user_service.sync_identity(user)
    context.user_data.pop("discover_matches", None)
    context.user_data.pop("discover_match_index", None)
    context.user_data.pop("discover_awaiting_message", None)

    current_user = user_service.get_profile(user.id)
    if not current_user:
        await update.message.reply_text(
            "Kamu harus bikin profile dulu! Klik /start ya~",
            reply_markup=main_menu_keyboard(),
        )
        return
    if not current_user.get("is_active"):
        user_service.set_active(user.id, True)
        current_user["is_active"] = True

    if is_temporarily_banned(current_user):
        await update.message.reply_text(
            get_ban_notice(current_user), reply_markup=main_menu_keyboard()
        )
        return

    if current_user.get("latitude") is None or current_user.get("longitude") is None:
        await update.message.reply_text(
            "Lokasi kamu belum ada. Coba update lokasi dulu ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Check pending likes for this user
    pending_count = matching_service.discover_actions_repo.count_pending_for_target(
        user.id
    )
    if pending_count > 0:
        inline_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👀 Tampilkan Semua", callback_data="dsc_showall"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🙈 Abaikan Semua", callback_data="dsc_ignore_all"
                    )
                ],
            ]
        )
        await update.message.reply_text(
            f"✨ Kami menemukan seseorang buat kamu ;)\n"
            f"Ada {pending_count} orang yang menyukai profilmu! Mau lihat sekarang?",
            reply_markup=inline_kb,
        )

    matches = matching_service.find_matches_for_user(current_user)
    if not matches:
        await update.message.reply_text(
            "😢 Belum ada yang deket nih... Coba lagi nanti ya~",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        return

    context.user_data["discover_matches"] = matches
    context.user_data["discover_match_index"] = 0
    await _show_discover_profile(update, context)


async def _show_discover_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matches = context.user_data.get("discover_matches")
    idx = context.user_data.get("discover_match_index")

    if not matches or idx is None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Klik 👁️ Lihat Profil dulu ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    if idx >= len(matches):
        context.user_data.pop("discover_matches", None)
        context.user_data.pop("discover_match_index", None)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✨ Udah kelar semua! Coba lagi nanti ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    match = matches[idx]
    matching_service.record_seen_profile(update.effective_user.id, match["_id"])

    current_user = user_service.get_profile(update.effective_user.id)
    if not current_user:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Profile tidak ditemukan. /start ulang ya~",
            reply_markup=main_menu_keyboard(),
        )
        return

    if None in (
        current_user.get("latitude"),
        current_user.get("longitude"),
        match.get("latitude"),
        match.get("longitude"),
    ):
        context.user_data["discover_match_index"] += 1
        await _show_discover_profile(update, context)
        return

    caption = _build_profile_text(match, current_user)
    await _send_profile_with_photo(
        context,
        update.effective_chat.id,
        match,
        caption,
        reply_markup=discover_profile_keyboard(),
    )


# ─── actions ────────────────────────────────────────────────────────────


async def discover_love(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user):
        await update.message.reply_text(
            "Fitur ini khusus akun user.", reply_markup=admin_menu_keyboard()
        )
        return

    profile = user_service.get_profile(user.id)
    if not profile:
        await update.message.reply_text(
            "Profil tidak ditemukan. /start dulu ya~", reply_markup=main_menu_keyboard()
        )
        return
    if is_temporarily_banned(profile):
        await update.message.reply_text(
            get_ban_notice(profile), reply_markup=main_menu_keyboard()
        )
        return

    match = _get_discover_match(context)
    if not match:
        await update.message.reply_text(
            "Klik 👁️ Lihat Profil dulu ya~", reply_markup=main_menu_keyboard()
        )
        return

    target_id = match.get("telegram_id")
    if target_id is None:
        context.user_data["discover_match_index"] = (
            context.user_data.get("discover_match_index", 0) + 1
        )
        await _show_discover_profile(update, context)
        return

    result = matching_service.discover_love(profile, match)
    if result["status"] == "love_sent":
        action_id = result["action_id"]
        gender = _gender_label(profile.get("gender"))

        inline_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👀 Tunjukkan", callback_data=f"dsc_show_{action_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🙅 Nggak, makasih", callback_data=f"dsc_nope_{action_id}"
                    )
                ],
            ]
        )

        # If target is currently in a chat session, queue the notification instead
        target_profile = user_service.get_profile(target_id)
        is_target_chatting = (
            target_profile and target_profile.get("chat_partner_id") is not None
        )
        try:
            if is_target_chatting:
                user_service.enqueue_pending_notification(
                    target_id, "💖 Seseorang telah ❤️ Like profilmu! Coba buka nanti~"
                )
                logger.info(f"Discover love queued for {target_id} (in chat)")
            else:
                await telegram_call_with_retry(
                    lambda: context.bot.send_message(
                        chat_id=target_id,
                        text=f"💖 Kamu disukai oleh 1 {gender}, tampilkan dia?",
                        reply_markup=inline_kb,
                    )
                )
        except Exception as e:
            logger.error(f"Failed discover love notif to {target_id}: {e}")
            user_service.enqueue_pending_notification(
                target_id, f"💖 Kamu disukai oleh 1 {gender}! Buka bot untuk lihat~"
            )

        await update.message.reply_text(
            "💖 Love terkirim!", reply_markup=discover_profile_keyboard()
        )

    if "discover_matches" in context.user_data:
        context.user_data["discover_match_index"] = (
            context.user_data.get("discover_match_index", 0) + 1
        )
        await _show_discover_profile(update, context)


async def discover_dislike(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _get_discover_match(context):
        await update.message.reply_text(
            "Klik 👁️ Lihat Profil dulu ya~", reply_markup=main_menu_keyboard()
        )
        return
    context.user_data["discover_match_index"] = (
        context.user_data.get("discover_match_index", 0) + 1
    )
    await _show_discover_profile(update, context)


async def discover_send_message_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    if is_admin(user):
        await update.message.reply_text(
            "Fitur ini khusus akun user.", reply_markup=admin_menu_keyboard()
        )
        return
    profile = user_service.get_profile(user.id)
    if not profile:
        await update.message.reply_text(
            "Profil tidak ditemukan. /start dulu ya~", reply_markup=main_menu_keyboard()
        )
        return
    if is_temporarily_banned(profile):
        await update.message.reply_text(
            get_ban_notice(profile), reply_markup=main_menu_keyboard()
        )
        return
    match = _get_discover_match(context)
    if not match:
        await update.message.reply_text(
            "Klik 👁️ Lihat Profil dulu ya~", reply_markup=main_menu_keyboard()
        )
        return

    context.user_data["discover_awaiting_message"] = True
    await update.message.reply_text(
        f"💌 Tulis pesan kamu untuk <b>{escape_html(match.get('name', 'dia'))}</b> (max {DISCOVER_MESSAGE_MAX_LENGTH} huruf):\n\n"
        "<i>Ketik pesanmu lalu kirim. Ketik /cancel untuk batal.</i>",
        parse_mode="HTML",
    )


async def discover_send_message_submit(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not context.user_data.get("discover_awaiting_message"):
        return False

    text = update.message.text.strip()
    if text.startswith("/"):
        context.user_data.pop("discover_awaiting_message", None)
        await update.message.reply_text(
            "Pengiriman pesan dibatalkan.", reply_markup=discover_profile_keyboard()
        )
        return True

    if len(text) > DISCOVER_MESSAGE_MAX_LENGTH:
        await update.message.reply_text(
            f"Terlalu panjang! Max {DISCOVER_MESSAGE_MAX_LENGTH} huruf."
        )
        return True

    context.user_data.pop("discover_awaiting_message", None)
    user = update.effective_user
    profile = user_service.get_profile(user.id)
    match = _get_discover_match(context)
    if not profile or not match:
        await update.message.reply_text(
            "Sesi habis. Coba Lihat Profil lagi ya~", reply_markup=main_menu_keyboard()
        )
        return True

    target_id = match.get("telegram_id")
    if target_id is None:
        await update.message.reply_text(
            "Profil tidak valid.", reply_markup=discover_profile_keyboard()
        )
        return True

    result = matching_service.discover_send_message(profile, match, text)
    if result["status"] == "message_sent":
        action_id = result["action_id"]
        inline_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👀 Tampilkan", callback_data=f"dsc_showmsg_{action_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🙈 Abaikan", callback_data=f"dsc_ignore_{action_id}"
                    )
                ],
            ]
        )
        try:
            await telegram_call_with_retry(
                lambda: context.bot.send_message(
                    chat_id=target_id,
                    text="💌 Ada yang mengirimu pesan! Mau lihat?",
                    reply_markup=inline_kb,
                )
            )
        except Exception as e:
            logger.error(f"Failed msg notif to {target_id}: {e}")
            user_service.enqueue_pending_notification(
                target_id, "💌 Seseorang mengirimu pesan! Buka bot ya~"
            )
        await update.message.reply_text(
            "💌 Pesan terkirim!", reply_markup=discover_profile_keyboard()
        )
    else:
        await update.message.reply_text(
            "Gagal mengirim pesan.", reply_markup=discover_profile_keyboard()
        )

    if "discover_matches" in context.user_data:
        context.user_data["discover_match_index"] = (
            context.user_data.get("discover_match_index", 0) + 1
        )
        await _show_discover_profile(update, context)
    return True


# ─── inline keyboard callbacks ──────────────────────────────────────────


async def handle_discover_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    responder = query.from_user

    handlers = {
        "dsc_show_": _handle_show_profile,
        "dsc_showall": _handle_show_all,
        "dsc_nope_": _handle_nope,
        "dsc_loveback_": _handle_love_back,
        "dsc_dislike_": _handle_dislike,
        "dsc_showmsg_": _handle_show_message,
        "dsc_ignore_": _handle_ignore,
        "dsc_ignore_all": _handle_ignore_all,
        "dsc_msglove_": _handle_love_back,
        "dsc_msgdislike_": _handle_dislike,
    }

    for prefix, handler in handlers.items():
        if data.startswith(prefix):
            action_id = data[len(prefix) :]
            await handler(query, context, action_id, responder)
            return


async def _handle_show_all(query, context, _unused, responder):
    """Show a paginated summary/list of pending 'love' actions for this user.

    Supports optional page parameter in the callback suffix: e.g. 'dsc_showall_p2'.
    """
    action_arg = _unused or ""
    # parse page from possible suffix like '_p2' or 'p2'
    page = 0
    try:
        if action_arg and action_arg.startswith("_p"):
            page = int(action_arg[2:])
        elif action_arg.startswith("p"):
            page = int(action_arg[1:])
    except Exception:
        page = 0

    actions_cursor = matching_service.discover_actions_repo.list_pending_for_target(
        responder.id
    )
    actions = list(actions_cursor)
    total = len(actions)
    if total == 0:
        await query.edit_message_text("Tidak ada notifikasi pending.")
        return

    page_size = 5
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_actions = actions[start_idx:end_idx]

    kb = []
    lines = [f"✨ Kamu punya {total} notifikasi: pilih untuk lihat profilnya (halaman {page+1}/{(total-1)//page_size+1}):"]
    for act in page_actions:
        sender_id = act.get("sender_telegram_id")
        sender_profile = user_service.get_profile(sender_id) if sender_id else None
        label = "Seseorang"
        if sender_profile:
            label = sender_profile.get("name") or label
        action_id = str(act.get("_id"))
        kb.append(
            [
                InlineKeyboardButton(
                    f"👀 Tampilkan {label}", callback_data=f"dsc_show_{action_id}"
                )
            ]
        )

    nav_row = []
    if start_idx > 0:
        prev_page = page - 1
        nav_row.append(InlineKeyboardButton("⬅️ Sebelumnya", callback_data=f"dsc_showall_p{prev_page}"))
    if end_idx < total:
        next_page = page + 1
        nav_row.append(InlineKeyboardButton("➡️ Berikutnya", callback_data=f"dsc_showall_p{next_page}"))
    if nav_row:
        kb.append(nav_row)

    kb.append([InlineKeyboardButton("🙈 Abaikan Semua", callback_data="dsc_ignore_all")])
    inline_kb = InlineKeyboardMarkup(kb)
    await query.edit_message_text("\n".join(lines), reply_markup=inline_kb)


async def _handle_ignore_all(query, context, _unused, responder):
    matching_service.discover_actions_repo.ignore_pending_for_target(responder.id)
    await query.edit_message_text("Oke, semua notifikasi diabaikan.")


async def _handle_show_profile(query, context, action_id, responder):
    """Target clicks 'Tunjukkan' → show sender's full profile."""
    action = matching_service.discover_actions_repo.find_action_by_id(action_id)
    if not action:
        await query.edit_message_text("Notifikasi ini sudah tidak valid.")
        return
    if action.get("response") is not None:
        await query.edit_message_text("Kamu sudah merespons ini sebelumnya ✨")
        return
    if action.get("target_telegram_id") != responder.id:
        await query.edit_message_text("Bukan untukmu.")
        return

    sender_id = action.get("sender_telegram_id")
    sender_profile = user_service.get_profile(sender_id) if sender_id else None
    responder_profile = user_service.get_profile(responder.id)

    if not sender_profile:
        await query.edit_message_text("Profil pengirim tidak ditemukan.")
        return

    caption = "💖 <b>Seseorang menyukai profil kamu:</b>\n\n" + _build_profile_text(
        sender_profile, responder_profile
    )

    inline_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "❤️ Love", callback_data=f"dsc_loveback_{action_id}"
                ),
                InlineKeyboardButton(
                    "👎 Dislike", callback_data=f"dsc_dislike_{action_id}"
                ),
            ]
        ]
    )

    await query.edit_message_text("✅ Profil ditampilkan di bawah 👇")
    await _send_profile_with_photo(
        context, query.message.chat_id, sender_profile, caption, reply_markup=inline_kb
    )


async def _handle_nope(query, context, action_id, responder):
    """Target clicks 'Nggak, makasih'."""
    result = matching_service.respond_to_discover_action(
        action_id, "dislike", responder.id
    )
    if result["status"] == "already_responded":
        await query.edit_message_text("Kamu sudah merespons ini sebelumnya ✨")
    elif result["status"] in ("not_found", "not_authorized"):
        await query.edit_message_text("Notifikasi tidak valid.")
    else:
        await query.edit_message_text("Oke, tidak apa-apa 👋")


async def _handle_love_back(query, context, action_id, responder):
    """Target loves back → MATCH."""
    result = matching_service.respond_to_discover_action(
        action_id, "love_back", responder.id
    )

    if result["status"] == "already_responded":
        await _edit_or_caption(query, "Kamu sudah merespons ini sebelumnya ✨")
        return
    if result["status"] in ("not_found", "not_authorized"):
        await _edit_or_caption(query, "Notifikasi tidak valid.")
        return

    if result["status"] == "matched":
        sender_profile = result.get("sender_profile")
        responder_profile = result.get("responder_profile")
        sender_id = result.get("sender_telegram_id")

        # Build match text with profile info
        def _match_text(partner, viewer=None):
            profile_info = _build_profile_text(partner, viewer)
            tg_id = partner.get("telegram_id", "-")
            name = escape_html(partner.get("name", "-"))
            # Always show a masked link using the partner's name that opens their Telegram profile.
            contact = f'<a href="tg://user?id={tg_id}">{name}</a>'
            return (
                f"{profile_info}\n\n"
                "Mantap! Aku harap kalian bisa menghabiskan waktu bersama dengan baik 🙌\n\n"
                f"Ayo mulai ngobrol 👉 {contact}"
            )

        # Notify responder (target) — match reveal with profile + photo
        if sender_profile:
            match_caption = _match_text(sender_profile, responder_profile)
            # Remove inline buttons from current message
            await _edit_or_caption(query, "🎉 IT'S A MATCH! Lihat di bawah 👇")
            await _send_profile_with_photo(
                context, query.message.chat_id, sender_profile, match_caption
            )
        else:
            await _edit_or_caption(
                query, "🎉 MATCH! Tapi profil pasangan tidak ditemukan."
            )

        # Notify original sender — show responder profile + match
        if sender_id and responder_profile:
            try:
                sender_match_caption = (
                    "💖 <b>Seseorang juga menyukai profil kamu:</b>\n\n"
                    + _match_text(responder_profile, sender_profile)
                )
                await _send_profile_with_photo(
                    context, sender_id, responder_profile, sender_match_caption
                )
            except Exception as e:
                logger.error(f"Failed match notif to sender {sender_id}: {e}")
    else:
        await _edit_or_caption(query, "Terjadi kesalahan.")


async def _handle_dislike(query, context, action_id, responder):
    result = matching_service.respond_to_discover_action(
        action_id, "dislike", responder.id
    )
    if result["status"] == "already_responded":
        await _edit_or_caption(query, "Kamu sudah merespons ini sebelumnya ✨")
    elif result["status"] in ("not_found", "not_authorized"):
        await _edit_or_caption(query, "Notifikasi tidak valid.")
    else:
        await _edit_or_caption(query, "👎 Di-skip. Tidak terjadi apa-apa~")


async def _handle_show_message(query, context, action_id, responder):
    """Target clicks 'Tampilkan' → show message + sender profile + love/dislike."""
    action = matching_service.discover_actions_repo.find_action_by_id(action_id)
    if not action:
        await query.edit_message_text("Notifikasi tidak valid.")
        return
    if action.get("response") is not None:
        await query.edit_message_text("Kamu sudah merespons ini sebelumnya ✨")
        return
    if action.get("target_telegram_id") != responder.id:
        await query.edit_message_text("Bukan untukmu.")
        return

    sender_id = action.get("sender_telegram_id")
    msg_text = action.get("message_text", "")
    sender_profile = user_service.get_profile(sender_id) if sender_id else None
    responder_profile = user_service.get_profile(responder.id)

    lines = ["💌 <b>Pesan dari seseorang:</b>\n", f'<i>"{escape_html(msg_text)}"</i>\n']
    if sender_profile:
        lines.append(_build_profile_text(sender_profile, responder_profile))
    else:
        lines.append("👤 Profil pengirim tidak ditemukan.")
    lines.append("\nMau love atau skip?")

    inline_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "❤️ Love", callback_data=f"dsc_msglove_{action_id}"
                ),
                InlineKeyboardButton(
                    "👎 Dislike", callback_data=f"dsc_msgdislike_{action_id}"
                ),
            ]
        ]
    )

    caption = "\n".join(lines)
    await query.edit_message_text("✅ Pesan ditampilkan di bawah 👇")
    if sender_profile:
        await _send_profile_with_photo(
            context,
            query.message.chat_id,
            sender_profile,
            caption,
            reply_markup=inline_kb,
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=inline_kb,
        )


async def _handle_ignore(query, context, action_id, responder):
    result = matching_service.respond_to_discover_action(
        action_id, "ignore", responder.id
    )
    if result["status"] == "already_responded":
        await query.edit_message_text("Kamu sudah merespons ini sebelumnya ✨")
    elif result["status"] in ("not_found", "not_authorized"):
        await query.edit_message_text("Notifikasi tidak valid.")
    else:
        await query.edit_message_text("🙈 Pesan diabaikan.")
