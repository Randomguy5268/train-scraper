import json
import asyncio
import os
from playwright.async_api import async_playwright
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. SETUP FIREBASE (With safety check) ---
try:
    # Look for the secret you (hopefully) added to GitHub
    if os.environ.get('FIREBASE_SERVICE_ACCOUNT'):
        cert_dict = json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT'))
        cred = credentials.Certificate(cert_dict)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase Initialized")
    else:
        print("⚠️ No Firebase secret found. Skipping cloud sync, focusing on JSON only.")
except Exception as e:
    print(f"⚠️ Firebase Setup Failed: {e}")

async def scrape_all():
    print("🚀 Starting Cyberstation Scraper...")
    all_results = {} # This is now safely inside the function

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        
        # --- YOUR SCRAPING LOGIC HERE ---
        # Make sure your scraper fills 'all_results' 
        # Example: all_results['Tokaido'] = [{'name': 'Nozomi 1', ...}]
        
        # [SCRAPER CODE GOES HERE]
        
        await browser.close()
    
    return all_results

async def main():
    # Run the scraper and get the data back
    all_results = await scrape_all()
    
    # --- 2. TRY FIRESTORE SYNC ---
    try:
        db = firestore.client()
        db.collection('live_train_data').document('current_status').set({
            "routes": all_results,
            "last_updated": firestore.SERVER_TIMESTAMP
        })
        print("🏁 Firestore Sync Complete.")
    except Exception:
        print("⏭️ Skipping Firestore (using local JSON only).")

    # --- 3. GENERATE LITE JSON FOR ESP32 ---
    # --- 3. GENERATE LITE JSON FOR ESP32 ---
    print(f"📦 Found {len(all_results)} routes. Generating JSON...")
    lite_data = []
    
    # Debug: Print the keys to see what the scraper found
    print(f"Debug: Routes found: {list(all_results.keys())}")

    for route_name, trains in all_results.items():
        print(f"Processing {route_name}: found {len(trains)} trains")
        for t in trains:
            lite_data.append({
                "n": t.get('name', '??'),
                "s": t.get('station_a', ''),
                "b": t.get('is_between', False),
                "d": t.get('direction', 'Down')
            })

    if not lite_data:
        print("⚠️ WARNING: No trains were found in any route!")

    with open('live_trains.json', 'w') as f:
        json.dump(lite_data, f)
    
    print(f"✅ Created JSON with {len(lite_data)} trains.")

if __name__ == "__main__":
    asyncio.run(main())
