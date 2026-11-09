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

# Config from environment variables or defaults
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "9258009174:AAFByQvFIrZeshenTPmEizIGp9Wrk_MCGpA")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6196853483")
MERCURY_KEY = os.getenv("MERCURY_KEY", "sk_50f1cfaa0c554c08601a0870deeb767fa887bc7c9edb24774fbc5739ec55184e")

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
        f"🚨 <b>NEW FREELANCE JOB ALERT!</b>\n"
        f"📍 <b>Source:</b> {source}\n\n"
        f"💼 <b>Title:</b> {clean_title}\n\n"
        f"🔗 <a href=\"{link}\">👉 Click Here to Open Client Post</a>\n\n"
        f"📋 <b>Proposal Pitch (Copy & Send):</b>\n"
        f"<code>{clean_proposal}</code>\n\n"
        f"💡 <i>Tip: Pehle client se budget confirm karo, fir kaam shuru karenge!</i>"
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
        f"You are a professional freelance developer writing a response to a potential client. "
        f"Write a concise, persuasive 3-sentence proposal. "
        f"1) State you understand their requirements, 2) Mention you can build it cleanly in Python/Web, "
        f"3) Ask them to share details/link to confirm timeline and budget before starting.\n\n"
        f"Client Job: {job_title}"
    )

    payload = json.dumps({
        "model": "mercury-3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 120
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
        "Hi! I saw your requirement and can deliver this efficiently with clean, tested Python code. "
        "Please share the specific link and details so we can align on requirements and budget. "
        "I am ready to get started immediately!"
    )


def scan_reddit(seen):
    new_found = 0
    feeds = [
        ("Reddit r/forhire", "https://www.reddit.com/r/forhire/new/.rss"),
        ("Reddit r/slavelabour", "https://www.reddit.com/r/slavelabour/new/.rss")
    ]
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnandHunter/2.0"}

    for source_name, feed_url in feeds:
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


def scan_remotive(seen):
    new_found = 0
    url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=15"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        jobs = data.get("jobs", [])
        for j in jobs:
            title = j.get("title", "")
            link = j.get("url", "")
            lower = title.lower()

            if link in seen:
                continue

            if any(kw in lower for kw in KEYWORDS):
                source = f"Remotive ({j.get('company_name', 'Global')})"
                print(f"[Remotive] Match: {title}")
                proposal = generate_proposal_mercury(title)
                send_telegram(title, link, source, proposal)
                seen.add(link)
                new_found += 1
                time.sleep(2)
    except Exception as e:
        print(f"[Remotive Error] {e}")

    return new_found


def scan_weworkremotely(seen):
    new_found = 0
    url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            link_elem = item.find('link')
            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            link = link_elem.text or ""
            lower = title.lower()

            if link in seen:
                continue

            if any(kw in lower for kw in KEYWORDS):
                print(f"[WeWorkRemotely] Match: {title}")
                proposal = generate_proposal_mercury(title)
                send_telegram(title, link, "WeWorkRemotely", proposal)
                seen.add(link)
                new_found += 1
                time.sleep(2)
    except Exception as e:
        print(f"[WeWorkRemotely Error] {e}")

    return new_found


def run_scan():
    seen = load_seen()
    total = 0
    total += scan_reddit(seen)
    total += scan_remotive(seen)
    total += scan_weworkremotely(seen)
    save_seen(seen)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Full Multi-Channel Scan Complete. Sent {total} alerts.")


if __name__ == "__main__":
    run_scan()
