import asyncio
from playwright.async_api import async_playwright
from google.cloud import firestore
from datetime import datetime, timezone
import re
import sys

# --- CONFIGURATION ---
GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"

def parse_location(text):
    """Robust parser for JR Cyberstation location strings."""
    if not text:
        return {"a": "Unknown", "b": None, "is": False}
    
    text = " ".join(text.split())
    # Match "(between Station A and Station B)"
    between_match = re.search(r"[\(（]between\s+(.*?)\s+and\s+(.*?)[\)）]", text, re.IGNORECASE)
    if between_match:
        return {"a": between_match.group(1).strip(), "b": between_match.group(2).strip(), "is": True}
    
    # Match "(at Station A)"
    at_match = re.search(r"[\(（]at\s+(.*?)[\)）]", text, re.IGNORECASE)
    if at_match:
        return {"a": at_match.group(1).strip(), "b": None, "is": False}
    
    return {"a": "Unknown", "b": None, "is": False}

async def scrape_shinkansen():
    print("🚀 Starting Shinkansen Scraper...")
    db = firestore.AsyncClient(project=GCP_PROJECT_ID)
    
    urls = {
        "Tokaido-Sanyo": "https://www.shinkansen.co.jp/pc/en/Tokaido-Sanyo/",
        "Tohoku-Hokkaido": "https://www.shinkansen.co.jp/pc/en/Tohoku-Hokkaido/",
        "Hokuriku": "https://www.shinkansen.co.jp/pc/en/Hokuriku/",
        "Joetsu": "https://www.shinkansen.co.jp/pc/en/Joetsu/"
    }
    
    final_data = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "routes": {}
    }

    async with async_playwright() as p:
        # Launch browser with slightly slower movement to avoid being blocked
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x464)")
        page = await context.new_page()
        
        for route_name, url in urls.items():
            try:
                print(f"📡 Scraping {route_name}...")
                await page.goto(url, timeout=60000)
                # Wait for the table to actually appear
                await page.wait_for_selector(".train_name", timeout=10000)
                
                train_elements = await page.query_selector_all(".train_name")
                route_trains = []
                
                for el in train_elements:
                    raw_name = await el.inner_text()
                    if not raw_name: continue
                    
                    loc = parse_location(raw_name)
                    # We'll default to 'Up' unless the table logic suggests otherwise
                    # Most Shinkansen sites split tables by direction
                    route_trains.append({
                        "name": raw_name,
                        "station_a": loc["a"],
                        "station_b": loc["b"],
                        "is_between": loc["is"],
                        "direction": "Up", 
                        "event_time": datetime.now().strftime("%H:%M")
                    })
                
                final_data["routes"][route_name] = route_trains
                print(f"✅ Found {len(route_trains)} trains for {route_name}")

            except Exception as e:
                print(f"⚠️ Error scraping {route_name}: {e}")
                continue # Keep going even if one route fails
        
        await browser.close()
    
    # Save to Firestore
    await db.collection("live_train_data").document("current_status").set(final_data)
    print("🏁 Data synced to Firestore.")

if __name__ == "__main__":
    try:
        asyncio.run(scrape_shinkansen())
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        sys.exit(1)
