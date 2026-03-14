from pymongo import MongoClient

from .config import DB_NAME, MONGODB_URI


client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

users_collection = db.users
seen_profiles_collection = db.seen_profiles
blocked_profiles_collection = db.blocked_profiles
reports_collection = db.reports
