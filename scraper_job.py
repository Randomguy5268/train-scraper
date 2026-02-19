import asyncio
from playwright.async_api import async_playwright, TimeoutError
from google.cloud import firestore
from datetime import datetime, timezone
import pandas as pd
import sys
import os
import re  # Added for parsing text

# --- CONFIGURATION ---
WEBSITE_URL = "https://www.jr.cyberstation.ne.jp/index_en.html"
COLLECTION_NAME = "live_train_data"
DOCUMENT_NAME = "current_status"
MAX_RETRIES = 3
RETRY_DELAY = 5

# --- DATA MAPPING ---
DESTINATION_MAP = {
    ("Tokaido/Sanyo", "Up"): "TOKYO",
    ("Tokaido/Sanyo", "Down"): "HAKATA",
    ("Tohoku/Hokkaido", "Up"): "TOKYO",
    ("Tohoku/Hokkaido", "Down"): "HAKODATE-HOKUTO",
    ("Joetsu", "Up"): "TOKYO",
    ("Joetsu", "Down"): "NIIGATA",
    ("Hokuriku", "Up"): "TOKYO",
    ("Hokuriku", "Down"): "TSURUGU",
    ("Yamagata", "Up"): "TOKYO",
    ("Yamagata", "Down"): "SHINJO",
    ("Akita", "Up"): "TOKYO",
    ("Akita", "Down"): "AKITA",
    ("Kyushu", "Up"): "HAKATA",
    ("Kyushu", "Down"): "KAGOSHIMA-CHUO",
}

def get_destination(route, direction):
    return DESTINATION_MAP.get((route, direction), f"To {direction}bound {route}")

# --- FIRESTORE ---
async def init_firestore():
    print("[INFO] Initializing Firestore client...")
    return firestore.Client()

# --- NEW SCRAPER LOGIC ---
async def scrape_once():
    print("[INFO] Starting new scrape logic...")
    for attempt in range(1, MAX_RETRIES + 1):
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
                )
                page = await browser.new_page()

                # --- NAVIGATION ---
                print(f"[INFO] Navigating to {WEBSITE_URL}")
                await page.goto(WEBSITE_URL, timeout=45000)
                await page.click('a:has-text("Shinkansen Status")', timeout=10000)
                await page.wait_for_selector("#input-select-route", timeout=15000)

                # Get route names
                await page.click("#input-select-route")
                await page.wait_for_selector("#modal-select-route-shinkansen.uk-open", timeout=5000)
                route_buttons_initial = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
                
                route_names = []
                for btn in route_buttons_initial:
                    span = await btn.query_selector("span.route_name")
                    if span:
                        route_names.append(await span.inner_text())
                    else:
                        route_names.append("Unknown")

                await page.keyboard.press("Escape")
                await page.wait_for_selector("#modal-select-route-shinkansen", state="hidden")

                all_trains = {}

                for i, route_name in enumerate(route_names):
                    print(f"[INFO] Scraping route: {route_name}")
                    await page.click("#input-select-route")
                    await page.wait_for_selector("#modal-select-route-shinkansen.uk-open", timeout=5000)

                    all_buttons_fresh = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
                    if i < len(all_buttons_fresh):
                        await all_buttons_fresh[i].click()
                    else:
                        await page.keyboard.press("Escape")
                        continue

                    await page.wait_for_selector("#modal-select-route-shinkansen", state="hidden", timeout=5000)
                    await page.wait_for_timeout(500)

                    for direction in ["Up", "Down"]:
                        if direction == "Up":
                            await page.click("#up_button")
                        else:
                            await page.click("#down_button")

                        await page.click("#train_info_request")

                        try:
                            await page.wait_for_selector("#table_info_status_detail tbody tr", timeout=7000)
                            rows = await page.query_selector_all("#table_info_status_detail tbody tr")
                            destination_station = get_destination(route_name, direction)

                            for row in rows:
                                cols = await row.query_selector_all("td")
                                if len(cols) >= 2:
                                    train_name = ' '.join((await cols[0].inner_text()).split())
                                    status_raw = ' '.join((await cols[1].inner_text()).split())

                                    if "service ended" not in status_raw.lower():
                                        # --- PARSING LOGIC START ---
                                        # Examples: "Departed Tokyo at 14:00" or "Arrived at Shin-Osaka at 14:05"
                                        
                                        current_station = "Unknown"
                                        action = "Unknown"
                                        event_time = "00:00"

                                        # Regex to find time (HH:MM)
                                        time_match = re.search(r"(\d{1,2}:\d{2})", status_raw)
                                        if time_match:
                                            event_time = time_match.group(1)

                                        # Regex to find station and action
                                        if "Departed" in status_raw:
                                            action = "Departed"
                                            # Extract text between "Departed" and "at"
                                            station_match = re.search(r"Departed\s+(.*?)\s+at", status_raw)
                                            if station_match:
                                                current_station = station_match.group(1).strip()
                                        elif "Arrived" in status_raw:
                                            action = "Arrived"
                                            # Extract text between "Arrived at" and "at"
                                            station_match = re.search(r"Arrived at\s+(.*?)\s+at", status_raw)
                                            if station_match:
                                                current_station = station_match.group(1).strip()
                                        
                                        # --- PARSING LOGIC END ---

                                        train_info = {
                                            "name": train_name,
                                            "direction": direction,
                                            "destination": destination_station,
                                            "status_raw": status_raw,  # Keep original just in case
                                            "current_station": current_station,
                                            "action": action,
                                            "event_time": event_time
                                        }
                                        all_trains.setdefault(route_name, []).append(train_info)
                        except TimeoutError:
                            # It is normal for some lines (especially late at night) to have no trains
                            pass
                
                await browser.close()
                if not all_trains:
                    print("[WARN] Scrape finished but no data was parsed.")
                    return {}
                
                print(f"[INFO] Scrape successful. Found data for {len(all_trains)} routes.")
                return all_trains

        except Exception as e:
            print(f"[WARN] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if browser:
                await browser.close()
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
            else:
                print("[ERROR] All retries failed.")
                return {}

# --- MAIN JOB EXECUTION ---
async def main():
    print(f"[START] JR Cyberstation scrape at {datetime.now(timezone.utc).isoformat()}")

    db = await init_firestore()
    routes_data = await scrape_once()

    if not routes_data:
        print("[WARN] No data scraped. Skipping Firestore write.")
        sys.exit(0)

    doc_ref = db.collection(COLLECTION_NAME).document(DOCUMENT_NAME)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "routes": routes_data,
    }

    try:
        doc_ref.set(payload)
        print(f"[INFO] Firestore updated successfully with {sum(len(v) for v in routes_data.values())} trains.")
    except Exception as e:
        print(f"[ERROR] Firestore write failed: {e}")

    print("[END] Scraper finished cleanly.")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())