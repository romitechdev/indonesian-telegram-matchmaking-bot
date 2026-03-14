from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

from ..config import logger
from ..keyboards import admin_menu_keyboard, main_menu_keyboard
from ..services.user_service import user_service
from ..utils import is_admin


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
        try:
            await update.effective_message.reply_text(
                "😅 Terjadi kesalahan, coba lagi ya~ Kalau masih error, hubungi admin."
            )
        except Exception:
            pass
