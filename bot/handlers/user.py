from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

from ..config import (
    ADMIN_ACTION,
    AGE,
    DESCRIPTION,
    GENDER,
    LOCATION,
    NAME,
    PHOTO,
)
from ..keyboards import admin_menu_keyboard, main_menu_keyboard
from ..services.user_service import user_service
from ..utils import (
    get_ban_notice,
    is_admin,
    is_temporarily_banned,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_service.sync_identity(user)

    if is_admin(user):
        await update.message.reply_text(
            "✨ *Admin Dashboard* ✨\n\n"
            "Akun admin tidak bisa membuat profile user."
            "\nPakai menu admin di bawah ini ya 👇",
            reply_markup=admin_menu_keyboard(),
            parse_mode="Markdown",
        )
        return ADMIN_ACTION

    existing_user = user_service.get_profile(user.id)

    if is_temporarily_banned(existing_user):
        await update.message.reply_text(
            get_ban_notice(existing_user),
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    if existing_user:
        await update.message.reply_text(
            f"✨ *Haii {existing_user['name']}!* ✨\n"
            "Balik lagi nih~ Mau ngapain hari ini? 😊",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"✨ *Haii {user.first_name}!* ✨\n\n"
        "Yuk bikin *Love Match ID* mu dulu biar bisa cari teman deket-deket! 💖\n\n"
        "Pertama, namanya siapa nih? (Pake nama depan aja gapapa kok!)",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) > 50:
        await update.message.reply_text("Waduh kepanjangan namanya! Max 50 huruf ya~")
        return NAME

    context.user_data["name"] = name

    age_buttons = [[str(age) for age in range(14, 31)[i : i + 5]] for i in range(0, 17, 5)]

    await update.message.reply_text(
        f"*{name}*, umurnya berapa nih? 🎂",
        reply_markup=ReplyKeyboardMarkup(age_buttons, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown",
    )
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        age = int(update.message.text)
        if age < 14 or age > 30:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Waduh pilih yang bener dong, 14-30 tahun ya~")
        return AGE

    context.user_data["age"] = age

    gender_buttons = [["♂️ Cowok", "♀️ Cewek"]]
    await update.message.reply_text(
        "Oke sip! Kamu cowok atau cewek nih? 💁‍♂️💁‍♀️",
        reply_markup=ReplyKeyboardMarkup(gender_buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return GENDER


async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gender = update.message.text.strip().lower()
    if "cowok" in gender:
        gender = "Cowok"
    elif "cewek" in gender:
        gender = "Cewek"
    else:
        await update.message.reply_text("Pilih yang bener dong, cowok atau cewek~")
        return GENDER

    context.user_data["gender"] = gender

    await update.message.reply_text(
        "✨ *Ceritain dikit tentang kamu* ✨ (max 250 huruf):\n\n"
        "Contoh: _'Anak musik yang suka kopi. Yuk ngobrol santai!'_",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return DESCRIPTION


async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    description = update.message.text.strip()
    if len(description) > 250:
        await update.message.reply_text("Kepanjangan deskripsinya! Max 250 huruf ya~")
        return DESCRIPTION

    context.user_data["description"] = description

    location_button = KeyboardButton("📍 Share Lokasi", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[location_button]], one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Tinggal dikit lagi nih! Kita butuh lokasi kamu biar bisa cari orang terdekat~ 🌍\n\n"
        "_Lokasi cuma buat hitung jarak, gak bakal dishare ke siapa-siapa kok!_",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return LOCATION


async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    location = update.message.location
    context.user_data["latitude"] = location.latitude
    context.user_data["longitude"] = location.longitude

    await update.message.reply_text(
        "Terakhir nih! Kirim foto profil kamu ya~ 📸 (Satu aja dulu)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo = update.message.photo[-1]
    context.user_data["photo_file_id"] = photo.file_id

    user = update.effective_user
    user_service.create_profile_from_context(user, context.user_data)

    await update.message.reply_text(
        "🎉 *Profile selesai!* 🎉\n\n"
        "Sekarang kamu bisa cari teman-teman terdekat pake menu dibawah ini! 💫",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END
