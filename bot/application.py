from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from .config import (
    ADMIN_ACTION,
    ADMIN_BROADCAST,
    ADMIN_DELETE_CONFIRM,
    ADMIN_RESOLVE_REPORT,
    ADMIN_TEMP_BAN,
    ADMIN_VIEW_USER,
    AGE,
    QUIZ_COMM_STYLE,
    QUIZ_RELATIONSHIP_GOAL,
    QUIZ_VALUE,
    DESCRIPTION,
    EDIT_AGE,
    EDIT_CHOICE,
    EDIT_DESCRIPTION,
    EDIT_GENDER,
    EDIT_LOCATION,
    EDIT_NAME,
    EDIT_PHOTO,
    GENDER,
    LOCATION,
    NAME,
    PHOTO,
    TELEGRAM_CONNECT_TIMEOUT,
    TELEGRAM_GET_UPDATES_READ_TIMEOUT,
    TELEGRAM_POOL_TIMEOUT,
    TELEGRAM_READ_TIMEOUT,
    TELEGRAM_TOKEN,
    TELEGRAM_WRITE_TIMEOUT,
)
from .handlers import admin as admin_handlers
from .handlers import chat as chat_handlers
from .handlers import core as core_handlers
from .handlers import profile as profile_handlers
from .handlers import user as user_handlers


def build_admin_action_handlers():
    return [
        MessageHandler(filters.Regex("^👥 List Users$"), admin_handlers.list_users),
        MessageHandler(filters.Regex("^📊 Stats$"), admin_handlers.show_stats),
        MessageHandler(
            filters.Regex("^(🧾 Review Report|✅ Resolve Report)$"),
            admin_handlers.resolve_report_prompt,
        ),
        MessageHandler(filters.Regex("^⛔ Ban Sementara$"), admin_handlers.temp_ban_prompt),
        MessageHandler(filters.Regex("^🚨 Reports$"), admin_handlers.list_reports),
        MessageHandler(filters.Regex("^📣 Broadcast$"), admin_handlers.broadcast_prompt),
        MessageHandler(filters.Regex("^🔍 Find User$"), admin_handlers.find_user),
        MessageHandler(filters.Regex("^❌ Delete User$"), admin_handlers.delete_user_prompt),
        MessageHandler(filters.Regex("^🏠 Main Menu$"), admin_handlers.admin_main_menu),
    ]


def build_admin_states():
    return {
        ADMIN_ACTION: build_admin_action_handlers(),
        ADMIN_VIEW_USER: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.view_user)
        ],
        ADMIN_DELETE_CONFIRM: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.delete_user_confirm)
        ],
        ADMIN_RESOLVE_REPORT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.resolve_report_confirm)
        ],
        ADMIN_TEMP_BAN: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.temp_ban_confirm)
        ],
        ADMIN_BROADCAST: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.broadcast_send)
        ],
    }


def create_application() -> Application:
    bot_request = HTTPXRequest(
        connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
        read_timeout=TELEGRAM_READ_TIMEOUT,
        write_timeout=TELEGRAM_WRITE_TIMEOUT,
        pool_timeout=TELEGRAM_POOL_TIMEOUT,
    )
    get_updates_request = HTTPXRequest(
        connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
        read_timeout=TELEGRAM_GET_UPDATES_READ_TIMEOUT,
        write_timeout=TELEGRAM_WRITE_TIMEOUT,
        pool_timeout=TELEGRAM_POOL_TIMEOUT,
    )

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .request(bot_request)
        .get_updates_request(get_updates_request)
        .build()
    )

    user_states = {
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_name)],
        AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_age)],
        GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_gender)],
        DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_description)
        ],
        QUIZ_VALUE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_quiz_value)
        ],
        QUIZ_COMM_STYLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_quiz_communication_style)
        ],
        QUIZ_RELATIONSHIP_GOAL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_quiz_relationship_goal)
        ],
        LOCATION: [MessageHandler(filters.LOCATION, user_handlers.get_location)],
        PHOTO: [MessageHandler(filters.PHOTO, user_handlers.get_photo)],
    }
    user_states.update(build_admin_states())

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", user_handlers.start)],
        states=user_states,
        fallbacks=[CommandHandler("cancel", core_handlers.cancel)],
        allow_reentry=True,
    )

    edit_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✏️ Edit Profile$"), profile_handlers.edit_profile)
        ],
        states={
            EDIT_CHOICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_handlers.edit_choice)
            ],
            EDIT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_handlers.edit_name)
            ],
            EDIT_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_handlers.edit_age)],
            EDIT_GENDER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_handlers.edit_gender)
            ],
            EDIT_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_handlers.edit_description)
            ],
            EDIT_LOCATION: [
                MessageHandler(filters.LOCATION, profile_handlers.edit_location)
            ],
            EDIT_PHOTO: [MessageHandler(filters.PHOTO, profile_handlers.edit_photo)],
        },
        fallbacks=[CommandHandler("cancel", core_handlers.cancel)],
    )

    admin_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_handlers.admin_panel)],
        states=build_admin_states(),
        fallbacks=[CommandHandler("cancel", core_handlers.cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(edit_handler)
    application.add_handler(admin_handler)

    application.add_handler(
        MessageHandler(filters.Regex("^💬 Mulai Obrolan$"), chat_handlers.start_chat)
    )
    application.add_handler(MessageHandler(filters.Regex("^⏭️ Next$"), chat_handlers.next_chat))
    application.add_handler(
        MessageHandler(filters.Regex("^(⛔ Stop|❌ Batal Cari)$"), chat_handlers.stop_chat)
    )
    application.add_handler(MessageHandler(filters.Regex(r"^⚠️ Laporkan$"), chat_handlers.report_current_chat))
    from .config import REPORT_REASON_PATTERN
    application.add_handler(MessageHandler(filters.Regex(REPORT_REASON_PATTERN), chat_handlers.submit_chat_report_reason))
    application.add_handler(
        MessageHandler(filters.Regex("^👀 Profile Saya$"), profile_handlers.view_my_profile)
    )
    application.add_handler(MessageHandler(filters.Regex("^🚪 Keluar$"), core_handlers.exit_bot))
    application.add_handler(MessageHandler(filters.Regex("^🏠 Menu Utama$"), core_handlers.main_menu))
    application.add_handler(
        MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, chat_handlers.relay_chat_message)
    )
    application.add_error_handler(core_handlers.error_handler)

    return application


def main() -> None:
    application = create_application()
    print("Bot starting...")
    application.run_polling(bootstrap_retries=10)
