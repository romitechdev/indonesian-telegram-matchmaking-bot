from telegram import ReplyKeyboardMarkup

from .config import REPORT_REASON_OPTIONS


def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [["💬 Mulai Obrolan", "👀 Profile Saya"], ["✏️ Edit Profile", "🚪 Keluar"]],
        resize_keyboard=True,
        input_field_placeholder="Pilih menu yuk~",
    )


def waiting_chat_keyboard():
    return ReplyKeyboardMarkup(
        [["❌ Batal Cari"], ["🏠 Menu Utama"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def active_chat_keyboard():
    return ReplyKeyboardMarkup(
        [["⏭️ Next", "⛔ Stop"], ["⚠️ Laporkan", "🏠 Menu Utama"]],
        resize_keyboard=True,
    )


def next_profile_keyboard():
    return ReplyKeyboardMarkup(
        [["❤️ Love", "👎 Dislike"], ["⚠️ Report", "🏠 Menu Utama"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def report_reason_keyboard():
    return ReplyKeyboardMarkup(
        [
            [REPORT_REASON_OPTIONS[0], REPORT_REASON_OPTIONS[1]],
            [REPORT_REASON_OPTIONS[2], REPORT_REASON_OPTIONS[3]],
            [REPORT_REASON_OPTIONS[4], REPORT_REASON_OPTIONS[5]],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Pilih alasan report",
    )


def admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["👥 List Users", "📊 Stats"],
            ["🔍 Find User", "❌ Delete User"],
            ["🧾 Review Report", "⛔ Ban Sementara"],
            ["🚨 Reports", "📣 Broadcast"],
            ["🏠 Main Menu"],
        ],
        resize_keyboard=True,
    )
