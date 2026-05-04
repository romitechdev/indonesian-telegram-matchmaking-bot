from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

from ..config import (
    EDIT_AGE,
    EDIT_CHOICE,
    EDIT_DESCRIPTION,
    EDIT_GENDER,
    EDIT_LOCATION,
    EDIT_NAME,
    EDIT_PHOTO,
)
from ..keyboards import admin_menu_keyboard, main_menu_keyboard
from ..services.user_service import user_service
from ..utils import (
    escape_html,
    get_age_group,
    get_ban_notice,
    is_admin,
    is_temporarily_banned,
    format_username,
)


async def view_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if is_admin(user):
        await update.message.reply_text(
            "Akun admin tidak memakai profile user.",
            reply_markup=admin_menu_keyboard(),
        )
        return

    user_service.sync_identity(user)
    profile = user_service.get_profile(user.id)

    if is_temporarily_banned(profile):
        await update.message.reply_text(
            get_ban_notice(profile),
            reply_markup=main_menu_keyboard(),
        )
        return

    if not profile:
        await update.message.reply_text(
            "Kamu belum punya profile nih! Klik /start untuk buat profile dulu~",
            reply_markup=main_menu_keyboard(),
        )
        return

    age = profile.get("age", "?")

    caption = (
        "✨ <b>Profile Kamu</b> ✨\n\n"
        f"👤 Nama: {escape_html(profile['name'])}\n"
        f"🪪 Telegram ID: {escape_html(profile.get('telegram_id', '-'))}\n"
        f"🎂 Umur: {escape_html(age)}\n"
        f"🚻 Gender: {escape_html(profile['gender'])}\n"
        f"📱 Username (opsional): {escape_html(format_username(profile.get('username')))}\n"
        f"📝 Tentang Kamu:\n{escape_html(profile['description'])}"
    )

    if profile.get("photo_file_id"):
        await update.message.reply_photo(
            photo=profile["photo_file_id"],
            caption=caption,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            caption,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )


async def edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user):
        await update.message.reply_text(
            "Akun admin tidak bisa mengedit profile user.",
            reply_markup=admin_menu_keyboard(),
        )
        return ConversationHandler.END

    user_service.sync_identity(update.effective_user)
    profile = user_service.get_profile(update.effective_user.id)
    if is_temporarily_banned(profile):
        await update.message.reply_text(
            get_ban_notice(profile),
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    keyboard = [
        ["✏️ Nama", "🎂 Umur", "🚻 Gender"],
        ["📝 Bio"],
        ["📍 Lokasi", "📸 Foto"],
        ["🔙 Menu Utama"],
    ]
    await update.message.reply_text(
        "Mau edit bagian mana nih? Pilih ya~ ✨",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return EDIT_CHOICE


async def edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.lower()

    if "nama" in choice:
        await update.message.reply_text(
            "Tulis nama barunya ya~", reply_markup=ReplyKeyboardRemove()
        )
        return EDIT_NAME
    if "umur" in choice:
        age_buttons = [
            [str(age) for age in range(14, 31)[i : i + 5]] for i in range(0, 17, 5)
        ]
        await update.message.reply_text(
            "Pilih umur barunya nih~ 🎂",
            reply_markup=ReplyKeyboardMarkup(
                age_buttons, one_time_keyboard=True, resize_keyboard=True
            ),
        )
        return EDIT_AGE
    if "gender" in choice:
        gender_buttons = [["♂️ Cowok", "♀️ Cewek"]]
        await update.message.reply_text(
            "Pilih gender kamu ya~ 💁‍♂️💁‍♀️",
            reply_markup=ReplyKeyboardMarkup(
                gender_buttons, one_time_keyboard=True, resize_keyboard=True
            ),
        )
        return EDIT_GENDER
    if "bio" in choice:
        await update.message.reply_text(
            "Tulis bio barunya ya~ (max 250 huruf)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return EDIT_DESCRIPTION
    if "lokasi" in choice:
        location_button = KeyboardButton("📍 Share Lokasi Baru", request_location=True)
        await update.message.reply_text(
            "Share lokasi barunya ya~ 🌍",
            reply_markup=ReplyKeyboardMarkup(
                [[location_button]], one_time_keyboard=True, resize_keyboard=True
            ),
        )
        return EDIT_LOCATION
    if "foto" in choice:
        await update.message.reply_text(
            "Kirim foto profil barunya ya~ 📸", reply_markup=ReplyKeyboardRemove()
        )
        return EDIT_PHOTO
    if "menu" in choice:
        await update.message.reply_text(
            "Kembali ke menu utama~", reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Waduh pilih yang bener dong~", reply_markup=main_menu_keyboard()
    )
    return EDIT_CHOICE


async def edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) > 50:
        await update.message.reply_text("Nama kepanjangan! Max 50 huruf ya~")
        return EDIT_NAME

    user = update.effective_user
    user_service.update_profile_fields(user.id, {"name": name})
    await update.message.reply_text(
        f"✨ <b>Nama berhasil diupdate!</b> ✨\n\nSekarang kamu bisa dipanggil {escape_html(name)} ya~",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def edit_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 14 or age > 30:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Waduh pilih yang bener dong, 14-30 tahun ya~")
        return EDIT_AGE

    user = update.effective_user
    user_service.update_profile_fields(
        user.id,
        {
            "age": age,
            "age_group": get_age_group(age),
        },
    )
    await update.message.reply_text(
        f"🎂 *Umur berhasil diupdate!* 🎂\n\nSekarang umur kamu *{age} tahun* ya~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def edit_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gender = update.message.text.strip().lower()
    if "cowok" in gender:
        gender = "Cowok"
    elif "cewek" in gender:
        gender = "Cewek"
    else:
        await update.message.reply_text("Pilih yang bener dong, cowok atau cewek~")
        return EDIT_GENDER

    user = update.effective_user
    user_service.update_profile_fields(user.id, {"gender": gender})
    await update.message.reply_text(
        f"🚻 *Gender berhasil diupdate!* 🚻\n\nSekarang gender kamu *{gender}* ya~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text.strip()
    if len(description) > 250:
        await update.message.reply_text("Bio kepanjangan! Max 250 huruf ya~")
        return EDIT_DESCRIPTION

    user = update.effective_user
    user_service.update_profile_fields(user.id, {"description": description})
    await update.message.reply_text(
        "📝 *Bio berhasil diupdate!* 📝\n\nDeskripsi profil kamu sudah diperbarui~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def edit_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    updates = {
        "latitude": location.latitude,
        "longitude": location.longitude,
    }
    user_service.update_profile_fields(update.effective_user.id, updates)
    await update.message.reply_text(
        "📍 *Lokasi berhasil diupdate!* 📍\n\nSekarang kita bisa cari teman lebih akurat~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def edit_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    user_service.update_profile_fields(
        update.effective_user.id,
        {
            "photo_file_id": photo.file_id,
        },
    )
    await update.message.reply_text(
        "📸 *Foto profil berhasil diupdate!* 📸\n\nSekarang foto profil kamu lebih fresh~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END
