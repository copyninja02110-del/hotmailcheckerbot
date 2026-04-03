import asyncio
import aiofiles
import time
import uuid
import os
import random
from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from collections import defaultdict

# ===== CONFIG =====
BOT_TOKEN = os.getenv("8646480993:AAHy3RSUzm6bcPmbzh9c4bqsuAIXLZtcniY")
ADMIN_ID = 8646480993

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== GLOBAL =====
task_queue = asyncio.Queue()
user_stats = defaultdict(lambda: {"checked": 0, "valid": 0, "invalid": 0, "retry": 0})

WORKERS = 10

# ===== SERVICES =====
services = {
    "Netflix": "netflix.txt",
    "Spotify": "spotify.txt",
    "Amazon": "amazon.txt",
    "Facebook": "facebook.txt",
    "Instagram": "instagram.txt",
    "PayPal": "paypal.txt",
    "Steam": "steam.txt",
    "Discord": "discord.txt"
}

# ===== KEYBOARD =====
def kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📂 Upload Combo")],
            [KeyboardButton(text="📊 Stats"), KeyboardButton(text="⚡ Queue")]
        ],
        resize_keyboard=True
    )

# ===== START =====
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer("🔥 ULTRA CHECKER READY", reply_markup=kb())

# ===== LOADING ANIMATION =====
async def loading_animation(msg):
    steps = [
        "🔄 Sistem başlatılıyor...",
        "⚡ Proxy bağlanıyor...",
        "📡 Sunucuya bağlanıyor...",
        "🔍 Combo analiz ediliyor...",
        "🚀 Başlatılıyor..."
    ]

    m = await msg.answer("⚡ Starting...")

    for step in steps:
        await asyncio.sleep(1)
        await m.edit_text(step)

    await asyncio.sleep(1)
    await m.delete()

# ===== PROGRESS BAR =====
def progress_bar(current, total, length=20):
    percent = current / total if total else 0
    filled = int(length * percent)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {int(percent*100)}%"

# ===== LIVE STATUS =====
async def live_status(msg, task_id, stats, total):
    m = await msg.answer("⚡ Starting panel...")

    start_time = time.time()

    while stats["running"]:
        elapsed = time.time() - start_time
        checked = stats["checked"]

        cpm = int((checked / elapsed) * 60) if elapsed > 0 else 0
        bar = progress_bar(checked, total)

        text = f"""
⚡ TASK ID: {task_id}

📊 Progress:
{bar}

📈 Checked: {checked}/{total}
🔥 CPM: {cpm}

✅ Hits: {stats['valid']}
❌ Bad: {stats['invalid']}
🔁 Retry: {stats['retry']}
"""
        try:
            await m.edit_text(text)
        except:
            pass

        await asyncio.sleep(2)

# ===== SAVE SERVICE =====
async def save_account(service, combo):
    if not os.path.exists("Accounts"):
        os.makedirs("Accounts")

    async with aiofiles.open(f"Accounts/{services[service]}", "a") as f:
        await f.write(combo + "\n")

# ===== DETECT SERVICES =====
def detect_services(email):
    found = []
    for s in services:
        if s.lower() in email.lower():
            found.append(s)
    return found

# ===== HIT FORMAT =====
async def send_hit(msg, email, password, services_found, total_hits):
    services_text = "\n".join([f"✔ {s}" for s in services_found]) if services_found else "✖ None"

    text = f"""
🔱 HOTMAİL HİT BULUNDU 🔱
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
📧 Email: {email}
🔑 Password: {password}
👤 Name: User
🌍 Country: 🇩🇪 DE
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
🔗 EMAIL IN INBOX:
{services_text}

📊 Toplam Hit: {total_hits}
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
𝑷𝑹𝑶𝑮𝑹𝑨𝑴 : @YourBot
"""
    await msg.answer(text)

# ===== PROCESS =====
async def process(task):
    user_id = task["user_id"]
    combos = task["combos"]
    msg = task["msg"]
    task_id = task["task_id"]

    stats = {"checked": 0, "valid": 0, "invalid": 0, "retry": 0, "running": True}
    total = len(combos)

    asyncio.create_task(live_status(msg, task_id, stats, total))
    await loading_animation(msg)

    for combo in combos:
        if ":" not in combo:
            stats["invalid"] += 1
            stats["checked"] += 1
            continue

        email, password = combo.split(":", 1)

        detected = detect_services(email)

        for s in detected:
            await save_account(s, combo)

        if len(password) >= 6:
            stats["valid"] += 1

            await send_hit(
                msg,
                email,
                password,
                detected,
                stats["valid"]
            )
        else:
            stats["retry"] += 1

        stats["checked"] += 1

    stats["running"] = False
    await msg.answer("✅ TASK COMPLETED")

# ===== WORKER =====
async def worker():
    while True:
        task = await task_queue.get()
        await process(task)
        task_queue.task_done()

# ===== FILE HANDLER =====
@dp.message(lambda m: m.document)
async def handle_file(msg: Message):
    file = await bot.get_file(msg.document.file_id)
    path = file.file_path
    data = await bot.download_file(path)

    content = data.read().decode("utf-8", errors="ignore")
    combos = [x.strip() for x in content.splitlines() if x.strip()]

    task_id = str(uuid.uuid4())[:6]

    await msg.answer(f"📥 Task {task_id} | {len(combos)} combos")

    await task_queue.put({
        "user_id": msg.from_user.id,
        "combos": combos,
        "msg": msg,
        "task_id": task_id
    })

# ===== STATS =====
@dp.message(lambda m: m.text == "📊 Stats")
async def stats(msg: Message):
    s = user_stats[msg.from_user.id]
    await msg.answer(f"""
📊 Stats
Checked: {s['checked']}
Valid: {s['valid']}
""")

# ===== QUEUE =====
@dp.message(lambda m: m.text == "⚡ Queue")
async def queue(msg: Message):
    await msg.answer(f"Queue: {task_queue.qsize()}")

# ===== ADMIN =====
@dp.message(Command("admin"))
async def admin(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer(f"👑 Workers: {WORKERS}")

# ===== MAIN =====
async def main():
    for _ in range(WORKERS):
        asyncio.create_task(worker())

    print("🚀 ULTRA BOT RUNNING")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())