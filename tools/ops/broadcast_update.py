"""
Script broadcast satu kali: memberitahu semua user bahwa bot telah diperbarui.
Jalankan: python tools/ops/broadcast_update.py
"""

import asyncio
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from dotenv import load_dotenv

load_dotenv()

from telegram import Bot  # noqa: E402
from telegram.error import BadRequest, Forbidden  # noqa: E402

from bot.repositories.users import user_repository  # noqa: E402
from bot.utils import telegram_call_with_retry  # noqa: E402

BROADCAST_MESSAGE = (
    "🎉 <b>Bot LoveMatch ID Telah Diperbarui!</b>\n\n"
    "Halo! Kami ingin memberitahu bahwa bot ini baru saja mendapatkan pembaruan.\n\n"
    "✅ Bot kini sudah aktif kembali dan siap digunakan.\n"
    "Silakan lanjutkan menggunakan bot seperti biasa.\n\n"
    "Terima kasih atas kesabaranmu! 💖\n"
    "— Tim LoveMatch ID"
)


async def run_broadcast():
    token = os.environ["TELEGRAM_TOKEN"]
    bot = Bot(token=token)

    target_ids = user_repository.list_unique_telegram_ids()
    if not target_ids:
        print("Tidak ada user yang ditemukan di database.")
        return

    print(f"Memulai broadcast ke {len(target_ids)} user...")

    sent = 0
    forbidden = 0
    bad_request = 0
    other_error = 0

    for chat_id in target_ids:
        try:
            await telegram_call_with_retry(
                lambda cid=chat_id: bot.send_message(
                    chat_id=cid,
                    text=BROADCAST_MESSAGE,
                    parse_mode="HTML",
                )
            )
            sent += 1
            print(f"  ✅ Terkirim ke {chat_id}")
        except Forbidden:
            forbidden += 1
            print(f"  ⛔ Forbidden (user blokir bot): {chat_id}")
        except BadRequest as e:
            bad_request += 1
            print(f"  ❌ BadRequest {chat_id}: {e}")
        except Exception as e:
            other_error += 1
            print(f"  ⚠️  Error {chat_id}: {e}")

        await asyncio.sleep(0.05)  # rate limit aman

    print("\n========== HASIL BROADCAST ==========")
    print(f"Total target : {len(target_ids)}")
    print(f"Terkirim     : {sent}")
    print(f"Forbidden    : {forbidden}")
    print(f"Bad Request  : {bad_request}")
    print(f"Error lain   : {other_error}")
    print("=====================================")


if __name__ == "__main__":
    asyncio.run(run_broadcast())
