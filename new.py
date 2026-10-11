from playwright.sync_api import sync_playwright
import pandas as pd
import re
import time
import random
import os
import logging
from datetime import datetime

# ---------------- CONFIG ----------------
LINKS_FILE = "links.txt"
MAX_RETRIES = 3
FILE_NAME = "instagram_data.xlsx"

logging.basicConfig(level=logging.INFO)

# ---------------- LOAD LINKS ----------------

def load_links():
    with open(LINKS_FILE) as f:
        return [line.strip() for line in f if line.strip()]

def extract_username_from_url(url):
    return url.rstrip("/").split("/")[-1]

# ---------------- HELPERS ----------------

def extract_followers(meta):
    match = re.search(r"([\d,.]+[MK]?)\sFollowers", meta)
    return match.group(1) if match else None

def extract_name(meta):
    try:
        return meta.split("-")[1].split("(")[0].strip()
    except:
        return None

def human_delay():
    time.sleep(random.uniform(4, 8))

def is_login_page(page):
    return (
        "login" in page.url or
        page.locator("input[name='username']").count() > 0
    )

def handle_login(context, page):
    print("⚠️ Login required. Please login manually...")

    page.goto("https://www.instagram.com/accounts/login/")
    page.wait_for_timeout(60000)

    context.storage_state(path="session.json")
    print("✅ Session saved. Continuing...")

# ---------------- SCRAPER ----------------

def scrape_user(context, url):
    username = extract_username_from_url(url)

    for attempt in range(MAX_RETRIES):
        page = context.new_page()

        try:
            page.goto(url, timeout=60000, wait_until="networkidle")

            # Handle login redirect
            if is_login_page(page):
                handle_login(context, page)
                page.goto(url, timeout=60000, wait_until="networkidle")

            meta = page.locator("meta[name='description']").get_attribute("content")

            if not meta:
                raise Exception("Meta not found")

            page.close()

            return {
                "username": username,
                "profile_url": url,
                "name": extract_name(meta),
                "followers": extract_followers(meta),
                "timestamp": datetime.now()
            }

        except Exception as e:
            logging.warning(f"[Retry {attempt+1}] {username}: {e}")
            page.close()
            time.sleep(3)

    return {
        "username": username,
        "profile_url": url,
        "name": None,
        "followers": None,
        "timestamp": datetime.now()
    }

# ---------------- MAIN ----------------

results = []
run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

links = load_links()

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,  # first run login
        args=["--disable-blink-features=AutomationControlled"]
    )

    if os.path.exists("session.json"):
        context = browser.new_context(storage_state="session.json")
    else:
        context = browser.new_context()

    for link in links:
        logging.info(f"🔍 Scraping: {link}")
        data = scrape_user(context, link)
        data["run_id"] = run_id
        results.append(data)
        human_delay()

    context.storage_state(path="session.json")
    browser.close()

# ---------------- SAVE ----------------

new_df = pd.DataFrame(results)

if os.path.exists(FILE_NAME):
    existing_df = pd.read_excel(FILE_NAME)
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
else:
    combined_df = new_df

combined_df.to_excel(FILE_NAME, index=False)

logging.info("✅ Data appended to instagram_data.xlsx")