import os
import sys
import time
import json
import ssl
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# Force UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen_jobs.json")

# Bulletproof token handling (environment variable or fallback)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "9258009174:AAFByQvFIrZeshenTPmEizIGp9Wrk_MCGpA"
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or "6196853483"
MERCURY_KEY = os.getenv("MERCURY_KEY") or "sk_50f1cfaa0c554c08601a0870deeb767fa887bc7c9edb24774fbc5739ec55184e"

# Only direct-chat freelance subreddits (No corporate ATS or resume-required portals)
FEEDS = [
    ("r/forhire", "https://www.reddit.com/r/forhire/new/.rss"),
    ("r/slavelabour", "https://www.reddit.com/r/slavelabour/new/.rss")
]

KEYWORDS = [
    "python", "scrape", "scraper", "scraping", "bot", "crawler", "automation",
    "script", "excel", "csv", "bug", "fix", "debug", "data", "web",
    "website", "landing", "html", "css", "video", "editor", "shorts", "reel"
]

EXCLUDE = ["[for hire]", "[offer]", "exam", "homework", "essay"]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen)[-500:], f, indent=2)


def send_telegram(title, link, source, proposal):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    clean_title = html.escape(title)
    clean_proposal = html.escape(proposal)

    text = (
        f"🚨 <b>NEW DIRECT FREELANCE GIG!</b>\n"
        f"📍 <b>Platform:</b> {source} (Direct Chat)\n\n"
        f"💼 <b>Client Post:</b> {clean_title}\n\n"
        f"🔗 <a href=\"{link}\">👉 Tap here to open post & Chat with Client</a>\n\n"
        f"📋 <b>Copy & Send this Proposal:</b>\n"
        f"<code>{clean_proposal}</code>\n\n"
        f"⚡ <i>Pehle client se payment & details confirm karo, fir laptop pe code banayenge!</i>"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15, context=ctx):
            pass
        print(f"[Telegram] Alert sent: {title[:40]}...")
    except Exception as e:
        print(f"[Telegram Error] {e}")


def generate_proposal_mercury(job_title):
    prompt = (
        f"You are a professional freelance developer writing a response to a potential client on Reddit. "
        f"Write a concise, persuasive 2-sentence proposal. "
        f"1) State you can handle this cleanly in Python/Automation/Media, "
        f"2) Ask them to share specific details so we can confirm timeline and budget before starting.\n\n"
        f"Client Job: {job_title}"
    )

    payload = json.dumps({
        "model": "mercury-3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 100
    }).encode('utf-8')

    req = urllib.request.Request(
        "https://api.inceptionlabs.ai/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {MERCURY_KEY}", "Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            reply = res['choices'][0]['message'].get('content')
            if reply and reply.strip():
                return reply.strip()
    except Exception:
        pass

    return (
        "Hi! I can handle this task efficiently with clean results. "
        "Please share the specific details so we can align on requirements and budget. Ready to start immediately!"
    )


def scan_reddit(seen):
    new_found = 0
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnandDirectBot/3.0"}

    for source_name, feed_url in FEEDS:
        try:
            req = urllib.request.Request(feed_url, headers=headers)
            with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            for e in root.findall('atom:entry', ns):
                title_elem = e.find('atom:title', ns)
                link_elem = e.find('atom:link', ns)
                if title_elem is None or link_elem is None:
                    continue

                title = title_elem.text or ""
                link = link_elem.attrib.get('href', "")
                lower = title.lower()

                if link in seen:
                    continue
                if not any(tag in lower for tag in ["[hiring]", "hiring", "[task]", "task"]):
                    continue
                if any(ex in lower for ex in EXCLUDE):
                    continue

                if any(kw in lower for kw in KEYWORDS):
                    print(f"[{source_name}] Match: {title}")
                    proposal = generate_proposal_mercury(title)
                    send_telegram(title, link, source_name, proposal)
                    seen.add(link)
                    new_found += 1
                    time.sleep(2)
        except Exception as e:
            print(f"[{source_name} Error] {e}")

    return new_found


def run_scan():
    seen = load_seen()
    total = scan_reddit(seen)
    save_seen(seen)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Direct Gigs Scan Complete. Sent {total} alerts.")


if __name__ == "__main__":
    run_scan()
