import asyncio
import re
import sys
from datetime import datetime, timezone
from playwright.async_api import async_playwright
from google.cloud import firestore

# --- CONFIGURATION ---
GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"
COLLECTION_NAME = "live_train_data"
DOCUMENT_NAME = "current_status"

def parse_location(train_name_string):
    """ Extracts station names from (at ...) or (between ... and ...) """
    at_match = re.search(r"\(at (.*?)\)", train_name_string)
    between_match = re.search(r"\(between (.*?) and (.*?)\)", train_name_string)
    
    if at_match:
        return {"a": at_match.group(1).strip(), "b": None, "is": False}
    elif between_match:
        return {"a": between_match.group(1).strip(), "b": between_match.group(2).strip(), "is": True}
    return {"a": "Unknown", "b": None, "is": False}

async def scrape_shinkansen():
    db = firestore.AsyncClient(project=GCP_PROJECT_ID)
    urls = {
        "Tokaido-Sanyo": "https://www.shinkansen.co.jp/pc/en/Tokaido-Sanyo/",
        "Tohoku-Hokkaido": "https://www.shinkansen.co.jp/pc/en/Tohoku-Hokkaido/",
        "Hokuriku": "https://www.shinkansen.co.jp/pc/en/Hokuriku/",
        "Joetsu": "https://www.shinkansen.co.jp/pc/en/Joetsu/"
    }
    
    final_data = {"timestamp": datetime.now(timezone.utc).isoformat(), "routes": {}}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # --- THE FIXES ARE HERE ---
        context = await browser.new_context(ignore_https_errors=True) # Ignores SSL Errors
        page = await context.new_page() # Corrected from new_row()
        
        for route_name, url in urls.items():
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_selector(".train_name", timeout=10000)
                
                train_elements = await page.query_selector_all(".train_name")
                route_trains = []
                
                for el in train_elements:
                    raw_name = await el.inner_text()
                    loc = parse_location(raw_name)
                    
                    route_trains.append({
                        "name": raw_name,
                        "station_a": loc["a"],
                        "station_b": loc["b"],
                        "is_between": loc["is"],
                        "direction": "Up", # Simplified for now
                        "event_time": datetime.now().strftime("%H:%M")
                    })
                final_data["routes"][route_name] = route_trains
                print(f"✅ {route_name}: Found {len(route_trains)} trains")

            except Exception as e:
                print(f"⚠️ {route_name} skipped: {e}")
        
        await browser.close()
    
    await db.collection(COLLECTION_NAME).document(DOCUMENT_NAME).set(final_data)
    print("🏁 Firestore Update Complete")

if __name__ == "__main__":
    asyncio.run(scrape_shinkansen())
