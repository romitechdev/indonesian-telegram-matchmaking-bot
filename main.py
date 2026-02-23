import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    InputMediaPhoto
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from pymongo import MongoClient, DESCENDING
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import os
from math import radians, sin, cos, sqrt, atan2
from dotenv import load_dotenv
import random
import time 
from keep_alive import keep_alive 


# Load environment variables
load_dotenv()


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB Atlas connection
MONGODB_URI = os.environ['MONGODB_URI']
DB_NAME = "love_match"
client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
users_collection = db.users
seen_profiles_collection = db.seen_profiles

# Admin configuration
ADMIN_USERNAMES = ["romiscript"]  # Add more admins as needed

# Conversation states
(
    NAME, AGE, GENDER, CITY, DESCRIPTION, LOCATION, PHOTO,
    EDIT_CHOICE, EDIT_NAME, EDIT_AGE, EDIT_GENDER, EDIT_CITY,
    EDIT_DESCRIPTION, EDIT_LOCATION, EDIT_PHOTO,
    ADMIN_ACTION, ADMIN_VIEW_USER, ADMIN_DELETE_CONFIRM
) = range(18)

# Helper functions
def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula"""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return 6371 * c  # Earth's radius in km

def is_admin(username):
    """Check if user is admin"""
    return username in ADMIN_USERNAMES

def normalize_city_name(city):
    """Normalize city name to title case for consistency"""
    return city.title().strip()

def get_age_group(age):
    """Group ages for better matching"""
    if age < 18: return "teen"
    elif age < 25: return "young_adult"
    else: return "adult"

# Keyboard layouts
def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🔍 Cari Teman", "👀 Profile Saya"],
            ["✏️ Edit Profile"]
        ],
        resize_keyboard=True,
        input_field_placeholder="Pilih menu yuk~"
    )

def next_profile_keyboard():
    return ReplyKeyboardMarkup(
        [["➡️ Lanjut", "🏠 Menu Utama"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["👥 List Users", "📊 Stats"],
            ["🔍 Find User", "❌ Delete User"],
            ["🏠 Main Menu"]
        ],
        resize_keyboard=True
    )

# ======================
# USER FLOW HANDLERS
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    existing_user = users_collection.find_one({"telegram_id": user.id})
    
    if existing_user:
        await update.message.reply_text(
            f"✨ *Haii {existing_user['name']}!* ✨\n"
            "Balik lagi nih~ Mau ngapain hari ini? 😊",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"✨ *Haii {user.first_name}!* ✨\n\n"
        "Yuk bikin *Love Match ID* mu dulu biar bisa cari teman deket-deket! 💖\n\n"
        "Pertama, namanya siapa nih? (Pake nama depan aja gapapa kok!)",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) > 50:
        await update.message.reply_text("Waduh kepanjangan namanya! Max 50 huruf ya~")
        return NAME
    
    context.user_data["name"] = name
    
    # Create age selection buttons
    age_buttons = [[str(age) for age in range(14, 31)[i:i+5]] for i in range(0, 17, 5)]
    
    await update.message.reply_text(
        f"*{name}*, umurnya berapa nih? 🎂",
        reply_markup=ReplyKeyboardMarkup(age_buttons, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown"
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
        reply_markup=ReplyKeyboardMarkup(gender_buttons, one_time_keyboard=True, resize_keyboard=True)
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
        "Kota kamu dimana nih? 🌆 (Biar kita bisa cari orang terdekat!)",
        reply_markup=ReplyKeyboardRemove()
    )
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    city = normalize_city_name(update.message.text)
    if len(city) > 50:
        await update.message.reply_text("Nama kota kepanjangan! Max 50 huruf ya~")
        return CITY
    
    context.user_data["city"] = city
    
    await update.message.reply_text(
        "✨ *Ceritain dikit tentang kamu* ✨ (max 250 huruf):\n\n"
        "Contoh: _'Anak musik yang suka kopi. Yuk ngobrol santai!'_",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
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
        parse_mode="Markdown"
    )
    return LOCATION

async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    location = update.message.location
    context.user_data["latitude"] = location.latitude
    context.user_data["longitude"] = location.longitude
    
    await update.message.reply_text(
        "Terakhir nih! Kirim foto profil kamu ya~ 📸 (Satu aja dulu)",
        reply_markup=ReplyKeyboardRemove()
    )
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo = update.message.photo[-1]
    context.user_data["photo_file_id"] = photo.file_id
    
    # Save to MongoDB
    user = update.effective_user
    user_data = {
        "telegram_id": user.id,
        "name": context.user_data["name"],
        "age": context.user_data["age"],
        "gender": context.user_data["gender"],
        "city": context.user_data["city"],
        "description": context.user_data["description"],
        "latitude": context.user_data["latitude"],
        "longitude": context.user_data["longitude"],
        "photo_file_id": context.user_data["photo_file_id"],
        "username": user.username,
        "age_group": get_age_group(context.user_data["age"]),
        "is_active": True,
        "created_at": datetime.utcnow(),
        "last_updated": datetime.utcnow()
    }
    
    users_collection.insert_one(user_data)
    
    await update.message.reply_text(
        "🎉 *Profile selesai!* 🎉\n\n"
        "Sekarang kamu bisa cari teman-teman terdekat pake menu dibawah ini! 💫",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ======================
# IMPROVED MATCHING SYSTEM
# ======================

async def find_nearby_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    current_user = users_collection.find_one({"telegram_id": user.id, "is_active": True})
    
    if not current_user:
        await update.message.reply_text(
            "Kamu harus bikin profile dulu! Klik /start ya~",
            reply_markup=main_menu_keyboard()
        )
        return
    
    # Get already seen profiles in last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)
    seen_profiles = list(seen_profiles_collection.find({
        "viewer_id": user.id,
        "viewed_at": {"$gte": yesterday}
    }))
    seen_profile_ids = [ObjectId(p["profile_id"]) for p in seen_profiles]
    
    # Stage 1: Find opposite gender, same city, similar age
    query_stage1 = {
        "_id": {"$nin": seen_profile_ids},
        "telegram_id": {"$ne": user.id},
        "is_active": True,
        "gender": {"$ne": current_user["gender"]},
        "city": current_user["city"],
        "age_group": current_user["age_group"]
    }
    stage1_matches = list(users_collection.find(query_stage1))
    
    # Stage 2: Opposite gender, nearby locations, similar age
    if not stage1_matches:
        query_stage2 = {
            "_id": {"$nin": seen_profile_ids},
            "telegram_id": {"$ne": user.id},
            "is_active": True,
            "gender": {"$ne": current_user["gender"]},
            "age_group": current_user["age_group"]
        }
        stage2_matches = list(users_collection.find(query_stage2))
        
        # Calculate distances and sort
        for match in stage2_matches:
            match["distance"] = haversine(
                current_user["latitude"], current_user["longitude"],
                match["latitude"], match["longitude"]
            )
        stage2_matches.sort(key=lambda x: x["distance"])
        matches = stage2_matches
    else:
        matches = stage1_matches
    
    # Stage 3: Random active profiles if no good matches
    if not matches:
        query_stage3 = {
            "_id": {"$nin": seen_profile_ids},
            "telegram_id": {"$ne": user.id},
            "is_active": True
        }
        matches = list(users_collection.find(query_stage3))
        random.shuffle(matches)
    
    if not matches:
        await update.message.reply_text(
            "😢 *Waduh belum ada yang deket nih...*\n"
            "Coba lagi nanti ya atau cari yang lebih jauh~",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown"
        )
        return
    
    context.user_data["matches"] = matches
    context.user_data["current_match_index"] = 0
    
    await show_match(update, context)

async def show_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matches = context.user_data["matches"]
    current_index = context.user_data["current_match_index"]
    
    if current_index >= len(matches):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✨ *Udah kelar semua nih!* ✨\n"
                 "Coba lagi nanti ya siapa tau ada yang baru~",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown"
        )
        return
    
    match = matches[current_index]
    
    # Record that this profile has been seen
    seen_profiles_collection.insert_one({
        "viewer_id": update.effective_user.id,
        "profile_id": match["_id"],
        "viewed_at": datetime.utcnow()
    })
    
    # Calculate precise distance
    current_user = users_collection.find_one({"telegram_id": update.effective_user.id})
    distance = haversine(
        current_user["latitude"], current_user["longitude"],
        match["latitude"], match["longitude"]
    )
    
    # Format distance precisely
    if distance < 0.1:  # Less than 100m
        distance_str = f"📍 {distance * 1000:.0f} m"
    elif distance < 1:  # Less than 1km
        distance_str = f"📍 {distance * 1000:.0f} m"
    else:
        distance_str = f"📍 {distance:.1f} km"
    
    # Prepare clean caption
    caption = (
        f"✨ *{match['name']}*, {match['age']} {'♂️' if match['gender'] == 'Cowok' else '♀️'}\n"
        f"🏙 {match['city']} | {distance_str}\n\n"
        f"_{match['description']}_\n\n"
    )
    
    if match.get("username"):
        caption += f"💬 Chat: @{match['username']}"
    else:
        caption += "📵 Tidak ada username"
    
    # Send profile
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=match["photo_file_id"],
        caption=caption,
        reply_markup=next_profile_keyboard(),
        parse_mode="Markdown"
    )
    
    # Pink flower separator
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✩♬₊˚.🎧⋆☾✩♬₊˚.🎧⋆☾⋆⁺₊✧",
        reply_markup=next_profile_keyboard()
    )

async def next_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_match_index"] += 1
    await show_match(update, context)

# ======================
# PROFILE EDITING
# ======================

async def view_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    profile = users_collection.find_one({"telegram_id": user.id})
    
    if not profile:
        await update.message.reply_text(
            "Kamu belum punya profile nih! Klik /start untuk buat profile dulu~",
            reply_markup=main_menu_keyboard()
        )
        return
    
    # Calculate age if needed
    age = profile.get('age', '?')
    
    # Prepare caption
    caption = (
        f"✨ *Profile Kamu* ✨\n\n"
        f"👤 *Nama*: {profile['name']}\n"
        f"🎂 *Umur*: {age}\n"
        f"🚻 *Gender*: {profile['gender']}\n"
        f"🏙 *Kota*: {profile['city']}\n"
        f"📝 *Tentang Kamu*:\n_{profile['description']}_"
    )
    
    # Send profile photo if available
    if profile.get('photo_file_id'):
        await update.message.reply_photo(
            photo=profile['photo_file_id'],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            caption,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

async def edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["✏️ Nama", "🎂 Umur", "🚻 Gender"],
        ["🏙 Kota", "📝 Bio"],
        ["📍 Lokasi", "📸 Foto"],
        ["🔙 Menu Utama"]
    ]
    await update.message.reply_text(
        "Mau edit bagian mana nih? Pilih ya~ ✨",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return EDIT_CHOICE

async def edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.lower()
    
    if "nama" in choice:
        await update.message.reply_text("Tulis nama barunya ya~", reply_markup=ReplyKeyboardRemove())
        return EDIT_NAME
    elif "umur" in choice:
        age_buttons = [[str(age) for age in range(14, 31)[i:i+5]] for i in range(0, 17, 5)]
        await update.message.reply_text(
            "Pilih umur barunya nih~ 🎂",
            reply_markup=ReplyKeyboardMarkup(age_buttons, one_time_keyboard=True, resize_keyboard=True)
        )
        return EDIT_AGE
    elif "gender" in choice:
        gender_buttons = [["♂️ Cowok", "♀️ Cewek"]]
        await update.message.reply_text(
            "Pilih gender kamu ya~ 💁‍♂️💁‍♀️",
            reply_markup=ReplyKeyboardMarkup(gender_buttons, one_time_keyboard=True, resize_keyboard=True)
        )
        return EDIT_GENDER
    elif "kota" in choice:
        await update.message.reply_text("Tulis kota barunya ya~ 🌆", reply_markup=ReplyKeyboardRemove())
        return EDIT_CITY
    elif "bio" in choice:
        await update.message.reply_text(
            "Tulis bio barunya ya~ (max 250 huruf)",
            reply_markup=ReplyKeyboardRemove()
        )
        return EDIT_DESCRIPTION
    elif "lokasi" in choice:
        location_button = KeyboardButton("📍 Share Lokasi Baru", request_location=True)
        await update.message.reply_text(
            "Share lokasi barunya ya~ 🌍",
            reply_markup=ReplyKeyboardMarkup([[location_button]], one_time_keyboard=True, resize_keyboard=True)
        )
        return EDIT_LOCATION
    elif "foto" in choice:
        await update.message.reply_text("Kirim foto profil barunya ya~ 📸", reply_markup=ReplyKeyboardRemove())
        return EDIT_PHOTO
    elif "menu" in choice:
        await update.message.reply_text("Kembali ke menu utama~", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    else:
        await update.message.reply_text("Waduh pilih yang bener dong~", reply_markup=main_menu_keyboard())
        return EDIT_CHOICE

async def edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) > 50:
        await update.message.reply_text("Nama kepanjangan! Max 50 huruf ya~")
        return EDIT_NAME
    
    user = update.effective_user
    users_collection.update_one(
        {"telegram_id": user.id},
        {"$set": {"name": name, "last_updated": datetime.utcnow()}}
    )
    await update.message.reply_text(
        f"✨ *Nama berhasil diupdate!* ✨\n\nSekarang kamu bisa dipanggil *{name}* ya~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
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
    users_collection.update_one(
        {"telegram_id": user.id},
        {"$set": {
            "age": age,
            "age_group": get_age_group(age),
            "last_updated": datetime.utcnow()
        }}
    )
    await update.message.reply_text(
        f"🎂 *Umur berhasil diupdate!* 🎂\n\nSekarang umur kamu *{age} tahun* ya~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
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
    users_collection.update_one(
        {"telegram_id": user.id},
        {"$set": {"gender": gender, "last_updated": datetime.utcnow()}}
    )
    await update.message.reply_text(
        f"🚻 *Gender berhasil diupdate!* 🚻\n\nSekarang gender kamu *{gender}* ya~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def edit_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = normalize_city_name(update.message.text)
    if len(city) > 50:
        await update.message.reply_text("Nama kota kepanjangan! Max 50 huruf ya~")
        return EDIT_CITY
    
    user = update.effective_user
    users_collection.update_one(
        {"telegram_id": user.id},
        {"$set": {"city": city, "last_updated": datetime.utcnow()}}
    )
    await update.message.reply_text(
        f"🏙 *Kota berhasil diupdate!* 🏙\n\nSekarang lokasi kamu di *{city}* ya~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text.strip()
    if len(description) > 250:
        await update.message.reply_text("Bio kepanjangan! Max 250 huruf ya~")
        return EDIT_DESCRIPTION
    
    user = update.effective_user
    users_collection.update_one(
        {"telegram_id": user.id},
        {"$set": {"description": description, "last_updated": datetime.utcnow()}}
    )
    await update.message.reply_text(
        "📝 *Bio berhasil diupdate!* 📝\n\nDeskripsi profil kamu sudah diperbarui~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def edit_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    updates = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "last_updated": datetime.utcnow()
    }
    users_collection.update_one(
        {"telegram_id": update.effective_user.id},
        {"$set": updates}
    )
    await update.message.reply_text(
        "📍 *Lokasi berhasil diupdate!* 📍\n\nSekarang kita bisa cari teman lebih akurat~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def edit_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    users_collection.update_one(
        {"telegram_id": update.effective_user.id},
        {"$set": {
            "photo_file_id": photo.file_id,
            "last_updated": datetime.utcnow()
        }}
    )
    await update.message.reply_text(
        "📸 *Foto profil berhasil diupdate!* 📸\n\nSekarang foto profil kamu lebih fresh~",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ======================
# ADMIN FEATURES
# ======================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ Akses ditolak!")
        return
    
    await update.message.reply_text(
        "✨ *Admin Panel* ✨\n\nPilih menu dibawah ini:",
        reply_markup=admin_menu_keyboard(),
        parse_mode="Markdown"
    )
    return ADMIN_ACTION

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ Akses ditolak!")
        return
    
    users = list(users_collection.find().sort("created_at", -1).limit(50))
    
    if not users:
        await update.message.reply_text("Tidak ada pengguna terdaftar.")
        return
    
    message = "📋 *Daftar Pengguna* (50 terbaru):\n\n"
    for user in users:
        status = "🟢" if user.get("is_active", True) else "🔴"
        message += (
            f"{status} *{user['name']}*, {user['age']}\n"
            f"ID: `{user['_id']}`\n"
            f"Username: @{user.get('username', 'tidak ada')}\n"
            f"Lokasi: {user.get('city', 'tidak diketahui')}\n"
            f"Terdaftar: {user['created_at'].strftime('%d/%m/%Y')}\n\n"
        )
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard()
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ Akses ditolak!")
        return
    
    total_users = users_collection.count_documents({})
    active_users = users_collection.count_documents({"is_active": True})
    
    # Top cities
    pipeline = [
        {"$group": {"_id": "$city", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    top_cities = list(users_collection.aggregate(pipeline))
    
    # Gender distribution
    gender_pipeline = [
        {"$group": {"_id": "$gender", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    gender_stats = list(users_collection.aggregate(gender_pipeline))
    
    message = (
        "📊 *Statistik Pengguna*\n\n"
        f"👥 Total Pengguna: *{total_users}*\n"
        f"🟢 Aktif: *{active_users}* | 🔴 Nonaktif: *{total_users - active_users}*\n\n"
        "🏙 *Kota Terbanyak*:\n"
    )
    
    for city in top_cities:
        message += f"- {city['_id']}: {city['count']} pengguna\n"
    
    message += "\n🚻 *Gender*:\n"
    for gender in gender_stats:
        message += f"- {gender['_id']}: {gender['count']}\n"
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard()
    )

async def find_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ Akses ditolak!")
        return
    
    await update.message.reply_text(
        "🔍 Masukkan ID atau username pengguna (tanpa @):",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADMIN_VIEW_USER

async def view_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    
    try:
        # Try as ObjectId first
        user = users_collection.find_one({"_id": ObjectId(query)})
    except:
        # Search by username
        user = users_collection.find_one({"username": query})
    
    if not user:
        await update.message.reply_text(
            "Pengguna tidak ditemukan!",
            reply_markup=admin_menu_keyboard()
        )
        return ADMIN_ACTION
    
    status = "🟢 Aktif" if user.get("is_active", True) else "🔴 Nonaktif"
    message = (
        f"📋 *Detail Pengguna*\n\n"
        f"🆔 ID: `{user['_id']}`\n"
        f"👤 Nama: *{user['name']}*, {user['age']}\n"
        f"🚻 Gender: {user['gender']}\n"
        f"📱 Username: @{user.get('username', 'tidak ada')}\n"
        f"🏙 Kota: {user.get('city', 'tidak diketahui')}\n"
        f"📍 Lokasi: {user.get('latitude', '?')}, {user.get('longitude', '?')}\n"
        f"📅 Terdaftar: {user['created_at'].strftime('%d/%m/%Y %H:%M')}\n"
        f"🔄 Terakhir update: {user.get('last_updated', user['created_at']).strftime('%d/%m/%Y %H:%M')}\n"
        f"🔘 Status: {status}\n\n"
        f"📝 Bio:\n_{user.get('description', 'tidak ada')}_"
    )
    
    # Send photo if available
    if user.get("photo_file_id"):
        await update.message.reply_photo(
            photo=user["photo_file_id"],
            caption=message,
            parse_mode="Markdown",
            reply_markup=admin_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=admin_menu_keyboard()
        )
    
    return ADMIN_ACTION

async def delete_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ Akses ditolak!")
        return
    
    await update.message.reply_text(
        "❌ Masukkan ID pengguna yang akan dihapus:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADMIN_DELETE_CONFIRM

async def delete_user_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()
    
    try:
        result = users_collection.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count > 0:
            await update.message.reply_text(
                f"✅ Pengguna dengan ID `{user_id}` berhasil dihapus!",
                parse_mode="Markdown",
                reply_markup=admin_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Pengguna tidak ditemukan!",
                reply_markup=admin_menu_keyboard()
            )
    except:
        await update.message.reply_text(
            "❌ Format ID tidak valid!",
            reply_markup=admin_menu_keyboard()
        )
    
    return ADMIN_ACTION

# ======================
# MAIN FUNCTIONS
# ======================

async def exit_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_collection.update_one(
        {"telegram_id": update.effective_user.id},
        {"$set": {"is_active": False}}
    )
    await update.message.reply_text(
        "😢 *Profile kamu sekarang disembunyikan...*\n\n"
        "Klik /start kapan aja kalo mau balik lagi ya~",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Oke dibatalin ya~",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Mau ngapain nih? Pilih menu dibawah ya~ 👇",
        reply_markup=main_menu_keyboard()
    )

def main() -> None:
    keep_alive()
    # Create the Application
    TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # User conversation handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            LOCATION: [MessageHandler(filters.LOCATION, get_location)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    edit_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✏️ Edit Profile$"), edit_profile)],
        states={
            EDIT_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_choice)],
            EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_name)],
            EDIT_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_age)],
            EDIT_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_gender)],
            EDIT_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_city)],
            EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_description)],
            EDIT_LOCATION: [MessageHandler(filters.LOCATION, edit_location)],
            EDIT_PHOTO: [MessageHandler(filters.PHOTO, edit_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_panel)],
        states={
            ADMIN_ACTION: [
                MessageHandler(filters.Regex("^👥 List Users$"), list_users),
                MessageHandler(filters.Regex("^📊 Stats$"), show_stats),
                MessageHandler(filters.Regex("^🔍 Find User$"), find_user),
                MessageHandler(filters.Regex("^❌ Delete User$"), delete_user_prompt),
                MessageHandler(filters.Regex("^🏠 Main Menu$"), main_menu),
            ],
            ADMIN_VIEW_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_user)],
            ADMIN_DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_user_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add all handlers
    application.add_handler(conv_handler)
    application.add_handler(edit_handler)
    application.add_handler(admin_handler)
    
    # Add other handlers
    application.add_handler(MessageHandler(filters.Regex("^🔍 Cari Teman$"), find_nearby_friends))
    application.add_handler(MessageHandler(filters.Regex("^👀 Profile Saya$"), view_my_profile))
    application.add_handler(MessageHandler(filters.Regex("^🚪 Keluar$"), exit_bot))
    application.add_handler(MessageHandler(filters.Regex("^➡️ Lanjut$"), next_match))
    application.add_handler(MessageHandler(filters.Regex("^🏠 Menu Utama$"), main_menu))
    
    # Start the bot
    while True:
        try:
            print("Bot starting...")
            application.run_polling()
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    keep_alive()
    main()