import asyncio, aiofiles, time, uuid, os, random
from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from collections import defaultdict, deque

BOT_TOKEN = "8646480993:AAHy3RSUzm6bcPmbzh9c4bqsuAIXLZtcniY"
ADMIN_ID = 8646480993

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== SYSTEM =====
task_queue = asyncio.Queue()
retry_queue = asyncio.Queue()
user_stats = defaultdict(lambda: {
    "checked": 0,
    "valid": 0,
    "invalid": 0,
    "retry": 0
})

WORKERS = 20
PROXIES = []

# ===== LOAD PROXIES =====
def load_proxies():
    global PROXIES
    if os.path.exists("proxies.txt"):
        with open("proxies.txt") as f:
            PROXIES = [x.strip() for x in f if x.strip()]

def get_proxy():
    if not PROXIES:
        return None
    return random.choice(PROXIES)

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
    await msg.answer("🔥 ULTRA Checker Online", reply_markup=kb())

# ===== SERVICE DETECTION =====
services = {
    "Netflix": "netflix.txt",
    "Spotify": "spotify.txt",
    "Amazon": "amazon.txt",
    "Facebook": "facebook.txt"
}

async def save_service(service, combo):
    if not os.path.exists("Accounts"):
        os.makedirs("Accounts")

    async with aiofiles.open(f"Accounts/{services[service]}", "a") as f:
        await f.write(combo + "\n")

def detect_services(email):
    result = []
    if "netflix" in email: result.append("Netflix")
    if "spotify" in email: result.append("Spotify")
    if "amazon" in email: result.append("Amazon")
    if "fb" in email: result.append("Facebook")
    return result

# ===== CORE CHECK (SIMULATED ENGINE) =====
async def check_combo(combo):
    await asyncio.sleep(0.01)  # simulate delay

    if ":" not in combo:
        return "invalid"

    email, password = combo.split(":", 1)

    if len(password) < 6:
        return "retry"

    if "@" not in email:
        return "invalid"

    return "valid"

# ===== PROCESS =====
async def process(task):
    user_id = task["user_id"]
    combos = task["combos"]
    msg = task["msg"]
    task_id = task["task_id"]

    start = time.time()

    for i, combo in enumerate(combos):
        proxy = get_proxy()

        try:
            result = await check_combo(combo)

            if result == "valid":
                user_stats[user_id]["valid"] += 1

                for s in detect_services(combo):
                    await save_service(s, combo)

            elif result == "retry":
                user_stats[user_id]["retry"] += 1
                await retry_queue.put(combo)

            else:
                user_stats[user_id]["invalid"] += 1

            user_stats[user_id]["checked"] += 1

        except:
            await retry_queue.put(combo)

        # CPM
        elapsed = time.time() - start
        cpm = int((i / elapsed) * 60) if elapsed > 0 else 0

        if i % 50 == 0:
            await msg.answer(f"⚡ {task_id}\n{i}/{len(combos)}\nCPM: {cpm}")

    await msg.answer("✅ Task Done")

# ===== WORKER =====
async def worker():
    while True:
        task = await task_queue.get()
        await process(task)
        task_queue.task_done()

# ===== RETRY WORKER =====
async def retry_worker():
    while True:
        combo = await retry_queue.get()
        await asyncio.sleep(1)
        await task_queue.put({
            "user_id": 0,
            "combos": [combo],
            "msg": None,
            "task_id": "retry"
        })
        retry_queue.task_done()

# ===== FILE HANDLER =====
@dp.message(lambda m: m.document)
async def file_handler(msg: Message):
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
Retry: {s['retry']}
""")

# ===== QUEUE =====
@dp.message(lambda m: m.text == "⚡ Queue")
async def queue(msg: Message):
    await msg.answer(f"Queue: {task_queue.qsize()} | Retry: {retry_queue.qsize()}")

# ===== ADMIN =====
@dp.message(Command("admin"))
async def admin(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer(f"👑 Workers: {WORKERS}")

# ===== MAIN =====
async def main():
    load_proxies()

    for _ in range(WORKERS):
        asyncio.create_task(worker())

    asyncio.create_task(retry_worker())

    print("🚀 ULTRA RUNNING")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())