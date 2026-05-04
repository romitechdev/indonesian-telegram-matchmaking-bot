from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

from ..config import ERROR_NOTICE_COOLDOWN_SECONDS, logger
from ..keyboards import admin_menu_keyboard, main_menu_keyboard
from ..services.user_service import user_service
from ..utils import ensure_utc, is_admin, now_utc


def should_send_error_notice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    if ERROR_NOTICE_COOLDOWN_SECONDS <= 0:
        return True

    if update.effective_user:
        cache_key = f"user:{update.effective_user.id}"
    elif update.effective_chat:
        cache_key = f"chat:{update.effective_chat.id}"
    else:
        return True

    error_notice_cache = context.application.bot_data.setdefault(
        "error_notice_cache", {}
    )
    current_time = now_utc()
    last_notice_time = ensure_utc(error_notice_cache.get(cache_key))
    if (
        last_notice_time
        and (current_time - last_notice_time).total_seconds()
        < ERROR_NOTICE_COOLDOWN_SECONDS
    ):
        return False

    error_notice_cache[cache_key] = current_time
    return True


async def exit_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_service.set_active(update.effective_user.id, False)
    await update.message.reply_text(
        "😢 *Profile kamu sekarang disembunyikan...*\n\n"
        "Klik /start kapan aja kalo mau balik lagi ya~",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_admin(update.effective_user):
        await update.message.reply_text(
            "Oke dibatalin ya~",
            reply_markup=admin_menu_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Oke dibatalin ya~",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user):
        await update.message.reply_text(
            "Dashboard admin ada di sini 👇",
            reply_markup=admin_menu_keyboard(),
        )
        return

    await update.message.reply_text(
        "Mau ngapain nih? Pilih menu dibawah ya~ 👇",
        reply_markup=main_menu_keyboard(),
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch all unhandled exceptions and log them without crashing the bot."""
    logger.error("Unhandled exception:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        if not should_send_error_notice(update, context):
            return
        try:
            await update.effective_message.reply_text(
                "😅 Terjadi kesalahan, coba lagi ya~ Kalau masih error, hubungi admin."
            )
        except Exception:
            pass
