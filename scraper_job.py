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

def parse_location(text):
    """
    Extracts station names from strings like 'Nozomi 12 (at Nagoya)' 
    or 'Hayabusa 5 (between Sendai and Furukawa)'
    """
    if not text:
        return {"a": "Unknown", "b": None, "is": False}
    
    # Clean whitespace and handle Japanese full-width parentheses
    text = " ".join(text.split())
    
    # 1. Match "(between Station A and Station B)"
    between_match = re.search(r"[\(（]between\s+(.*?)\s+and\s+(.*?)[\)）]", text, re.IGNORECASE)
    if between_match:
        return {
            "a": between_match.group(1).strip(), 
            "b": between_match.group(2).strip(), 
            "is": True
        }
    
    # 2. Match "(at Station A)"
    at_match = re.search(r"[\(（]at\s+(.*?)[\)）]", text, re.IGNORECASE)
    if at_match:
        return {
            "a": at_match.group(1).strip(), 
            "b": None, 
            "is": False
        }
    
    return {"a": "Unknown", "b": None, "is": False}

async def scrape_shinkansen():
    print(f"🚀 Initializing Scraper for Project: {GCP_PROJECT_ID}")
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
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        # Create a context with a standard User Agent to avoid bot detection
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        for route_name, url in urls.items():
            try:
                print(f"📡 Scraping {route_name}...")
                await page.goto(url, timeout=60000)
                
                # Wait for the specific train name elements to load
                try:
                    await page.wait_for_selector(".train_name", timeout=15000)
                except:
                    print(f"⚠️ No trains found currently on {route_name} (likely late night/no service)")
                    final_data["routes"][route_name] = []
                    continue

                train_elements = await page.query_selector_all(".train_name")
                route_trains = []
                
                for el in train_elements:
                    raw_name = await el.inner_text()
                    if not raw_name or "at " not in raw_name.lower() and "between " not in raw_name.lower():
                        continue
                    
                    loc = parse_location(raw_name)
                    
                    # We default to 'Up' direction for this simple version. 
                    # In a full version, we'd check which table/column the train is in.
                    route_trains.append({
                        "name": raw_name,
                        "station_a": loc["a"],
                        "station_b": loc["b"],
                        "is_between": loc["is"],
                        "direction": "Up", 
                        "event_time": datetime.now().strftime("%H:%M")
                    })
                
                final_data["routes"][route_name] = route_trains
                print(f"✅ Extracted {len(route_trains)} trains from {route_name}")

            except Exception as e:
                print(f"⚠️ Error processing {route_name}: {e}")
                continue 
        
        await browser.close()
    
    # Save the consolidated data to Firestore
    try:
        await db.collection(COLLECTION_NAME).document(DOCUMENT_NAME).set(final_data)
        print("🏁 Successfully synced all routes to Firestore.")
    except Exception as e:
        print(f"❌ Firestore Sync Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(scrape_shinkansen())
    except Exception as e:
        print(f"❌ Fatal execution error: {e}")
        sys.exit(1)
