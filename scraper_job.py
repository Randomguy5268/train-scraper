import asyncio
from playwright.async_api import async_playwright
from google.cloud import firestore
from datetime import datetime, timezone
import re

# --- CONFIGURATION ---
GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"

def parse_location(text):
    """Extracts station names from strings like 'Nozomi 12 (at Nagoya)'"""
    text = " ".join(text.split()) # Clean whitespace
    
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
    db = firestore.AsyncClient(project=GCP_PROJECT_ID)
    routes = {
        "Tokaido-Sanyo": "https://www.shinkansen.co.jp/pc/en/Tokaido-Sanyo/",
        "Tohoku-Hokkaido": "https://www.shinkansen.co.jp/pc/en/Tohoku-Hokkaido/",
        "Hokuriku": "https://www.shinkansen.co.jp/pc/en/Hokuriku/",
        "Joetsu": "https://www.shinkansen.co.jp/pc/en/Joetsu/"
    }
    
    final_data = {"timestamp": datetime.now(timezone.utc).isoformat(), "routes": {}}

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_row()
        
        for route_name, url in routes.items():
            await page.goto(url)
            # This selector looks for the train name cells in the JR status table
            train_elements = await page.query_selector_all(".train_name") 
            
            route_trains = []
            for el in train_elements:
                raw_name = await el.inner_text()
                loc = parse_location(raw_name)
                
                # Basic direction logic (usually based on odd/even train numbers or table side)
                # For this example, we assume "Up" but your scraper logic should verify
                direction = "Up" 
                
                route_trains.append({
                    "name": raw_name,
                    "station_a": loc["a"],
                    "station_b": loc["b"],
                    "is_between": loc["is"],
                    "direction": direction,
                    "event_time": datetime.now().strftime("%H:%M")
                })
            final_data["routes"][route_name] = route_trains
        
        await browser.close()
    
    # Save to Firestore
    await db.collection("live_train_data").document("current_status").set(final_data)
    print("✅ Scrape and Parse Complete")

if __name__ == "__main__":
    asyncio.run(scrape_shinkansen())
