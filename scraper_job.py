import asyncio
import re
import sys
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError
from google.cloud import firestore

# --- CONFIGURATION ---
GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"
WEBSITE_URL = "https://www.jr.cyberstation.ne.jp/index_en.html"

def parse_location(text):
    """Parses station names from text like '(at Nagoya)' or '(between X and Y)'"""
    text = " ".join(text.split())
    between_match = re.search(r"[\(（]between\s+(.*?)\s+and\s+(.*?)[\)）]", text, re.IGNORECASE)
    if between_match:
        return {"a": between_match.group(1).strip(), "b": between_match.group(2).strip(), "is": True}
    at_match = re.search(r"[\(（]at\s+(.*?)[\)）]", text, re.IGNORECASE)
    if at_match:
        return {"a": at_match.group(1).strip(), "b": None, "is": False}
    return {"a": "Unknown", "b": None, "is": False}

async def scrape_shinkansen():
    print(f"🚀 Starting Cyberstation Scraper...")
    db = firestore.AsyncClient(project=GCP_PROJECT_ID)
    final_data = {"timestamp": datetime.now(timezone.utc).isoformat(), "routes": {}}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        try:
            # 1. Navigate and open Shinkansen Status
            await page.goto(WEBSITE_URL)
            await page.click('a:has-text("Shinkansen Status")', timeout=15000)
            await page.wait_for_selector("#input-select-route", timeout=15000)

            # 2. Get Route List
            await page.click("#input-select-route")
            await page.wait_for_selector("#modal-select-route-shinkansen.uk-open")
            route_btns = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
            
            route_names = []
            for btn in route_btns:
                span = await btn.query_selector("span.route_name")
                name = await span.inner_text() if span else "Unknown"
                route_names.append(name)
            
            await page.keyboard.press("Escape")

            # 3. Iterate Routes and Directions
            for i, route_name in enumerate(route_names):
                route_trains = []
                for direction in ["Up", "Down"]:
                    try:
                        # Re-open modal and select route
                        await page.click("#input-select-route")
                        await page.wait_for_selector("#modal-select-route-shinkansen.uk-open")
                        btns = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
                        await btns[i].click()

                        # Select Direction and Request
                        await page.click("#up_button" if direction == "Up" else "#down_button")
                        await page.click("#train_info_request")
                        
                        # Wait for table
                        await page.wait_for_selector("#table_info_status_detail tbody tr", timeout=5000)
                        rows = await page.query_selector_all("#table_info_status_detail tbody tr")

                        for row in rows:
                            cols = await row.query_selector_all("td")
                            if len(cols) >= 2:
                                train_name_raw = await cols[0].inner_text()
                                status_raw = await cols[1].inner_text()
                                
                                if "service ended" in status_raw.lower(): continue

                                loc = parse_location(train_name_raw)
                                route_trains.append({
                                    "name": train_name_raw.strip(),
                                    "station_a": loc["a"],
                                    "station_b": loc["b"],
                                    "is_between": loc["is"],
                                    "direction": direction,
                                    "status": status_raw.strip()
                                })
                    except Exception:
                        continue # Skip failed directions gracefully

                final_data["routes"][route_name] = route_trains
                print(f"✅ {route_name}: {len(route_trains)} trains found.")

            # 4. Save to Firestore
            await db.collection("live_train_data").document("current_status").set(final_data)
            print("🏁 Firestore Update Successful.")

        except Exception as e:
            print(f"❌ Scraper Failed: {e}")
            sys.exit(1)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_shinkansen())
