import asyncio
import re
import sys
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError
from google.cloud import firestore
from google.auth.credentials import AnonymousCredentials # <-- Added Anonymous Bypass

# --- CONFIGURATION ---
GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"
WEBSITE_URL = "https://www.jr.cyberstation.ne.jp/index_en.html"

def parse_location(full_text):
    """
    Parses the 'Running between/at' format.
    """
    text = " ".join(full_text.split()).replace('\xa0', ' ')
    
    between_match = re.search(r"between\s+(.*?)\s+and\s+(.*?)(?=\s|$|\)|\])", text, re.IGNORECASE)
    if between_match:
        return {
            "a": between_match.group(1).strip().upper(),
            "b": between_match.group(2).strip().upper(),
            "is": True
        }
    
    at_match = re.search(r"at\s+(.*?)(?=\s|$|\)|\])", text, re.IGNORECASE)
    if at_match:
        return {
            "a": at_match.group(1).strip().upper(),
            "b": None,
            "is": False
        }
    
    return {"a": "Unknown", "b": None, "is": False}

async def scrape_shinkansen():
    print("🚀 Starting Cyberstation Scraper...")
    
    # --- FIREBASE CONNECTION BYPASS ---
    # This tells Google Cloud to stop asking for a password
    db = firestore.AsyncClient(project=GCP_PROJECT_ID, credentials=AnonymousCredentials())
    final_data = {"timestamp": datetime.now(timezone.utc).isoformat(), "routes": {}}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            ignore_https_errors=True 
        )
        page = await context.new_page()

        try:
            # 1. Navigation
            await page.goto(WEBSITE_URL)
            await page.click('a:has-text("Shinkansen Status")', timeout=15000)
            await page.wait_for_selector("#input-select-route", timeout=15000)

            # 2. Extract Route Names
            await page.click("#input-select-route")
            await page.wait_for_selector("#modal-select-route-shinkansen.uk-open")
            route_btns = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
            
            route_names = []
            for btn in route_btns:
                span = await btn.query_selector("span.route_name")
                name = await span.inner_text() if span else "Unknown"
                route_names.append(name)
            
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)

            # 3. Iterate through Routes
            for i, route_name in enumerate(route_names):
                route_trains = []
                for direction in ["Up", "Down"]:
                    try:
                        await page.click("#input-select-route")
                        await page.wait_for_selector("#modal-select-route-shinkansen.uk-open")
                        btns = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
                        await btns[i].click()

                        await page.click("#up_button" if direction == "Up" else "#down_button")
                        await page.click("#train_info_request")
                        
                        await page.wait_for_selector("#table_info_status_detail tbody tr", timeout=8000)
                        rows = await page.query_selector_all("#table_info_status_detail tbody tr")

                        for row in rows:
                            cols = await row.query_selector_all("td")
                            if len(cols) >= 2:
                                raw_cell_text = await cols[0].inner_text()
                                status_text = await cols[1].inner_text()
                                
                                if "service ended" in status_text.lower():
                                    continue

                                loc = parse_location(raw_cell_text)
                                train_name = raw_cell_text.split("Running")[0].strip()

                                route_trains.append({
                                    "name": train_name,
                                    "station_a": loc["a"],
                                    "station_b": loc["b"],
                                    "is_between": loc["is"],
                                    "direction": direction,
                                    "status": status_text.strip(),
                                    "event_time": datetime.now().strftime("%H:%M")
                                })
                    except Exception:
                        continue

                final_data["routes"][route_name] = route_trains
                print(f"✅ {route_name}: {len(route_trains)} trains.")

            # 4. Upload to Firestore
            await db.collection("live_train_data").document("current_status").set(final_data)
            print("🏁 Successfully synced to Firestore.")

        except Exception as e:
            print(f"❌ Scraper Failed: {e}")
            sys.exit(1)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_shinkansen())
import json

# ... (after you finish your Firestore update) ...

# Save a simplified version for the ESP32 to download directly
lite_data = {
    "trains": [] # Loop through your data and add only name, sA, sB, isBetween, isUp
}

# (Add your logic to populate lite_data)

with open('live_trains.json', 'w') as f:
    json.dump(lite_data, f)
