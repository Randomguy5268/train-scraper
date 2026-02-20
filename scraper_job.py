import json
import asyncio
import re
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
WEBSITE_URL = "https://www.jr.cyberstation.ne.jp/index_en.html"

async def scrape_all():
    print("🚀 Starting Cyberstation Scraper (English Site)...")
    all_trains = []

    async with async_playwright() as p:
        # Launch with a real-looking user agent so JR Cyberstation doesn't block us
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print("📡 Navigating to main site...")
            await page.goto(WEBSITE_URL, timeout=60000)
            await page.click('a:has-text("Shinkansen Status")', timeout=10000)
            await page.wait_for_selector("#input-select-route", timeout=15000)

            # Get the names of all the train routes from the popup menu
            await page.click("#input-select-route")
            await page.wait_for_selector("#modal-select-route-shinkansen.uk-open", timeout=5000)

            route_buttons = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
            route_names = []
            
            for btn in route_buttons:
                span = await btn.query_selector("span.route_name")
                if span:
                    route_names.append(await span.inner_text())
                else:
                    route_names.append("Unknown")

            await page.keyboard.press("Escape")
            await page.wait_for_selector("#modal-select-route-shinkansen", state="hidden")

            print(f"✅ Found {len(route_names)} routes to scan.")

            # Loop through each route one by one
            for i, route_name in enumerate(route_names):
                print(f"🔍 Scanning route: {route_name}...")
                
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

                # Check both directions (Up and Down)
                for direction in ["Up", "Down"]:
                    if direction == "Up":
                        await page.click("#up_button")
                    else:
                        await page.click("#down_button")

                    await page.click("#train_info_request")

                    try:
                        # Wait for the table to appear
                        await page.wait_for_selector("#table_info_status_detail tbody tr", timeout=7000)
                        rows = await page.query_selector_all("#table_info_status_detail tbody tr")

                        for row in rows:
                            cols = await row.query_selector_all("td")
                            if len(cols) >= 2:
                                train_name_raw = await cols[0].inner_text()
                                status_raw = await cols[1].inner_text()
                                
                                train_name = ' '.join(train_name_raw.split())
                                status = ' '.join(status_raw.split())

                                # Skip trains that have finished for the day
                                if "service ended" not in status.lower():
                                    
                                    # --- THE REGEX CHOPPER ---
                                    # Extracts exactly the station name from the status sentence
                                    match = re.search(r'(?:Departed|Arrived at)\s+(.+?)\s+at', status, re.IGNORECASE)
                                    
                                    station_name = ""
                                    is_between = False
                                    
                                    if match:
                                        station_name = match.group(1).strip()
                                        # If it says 'Departed', the train is currently moving between stations
                                        is_between = "Departed" in status 

                                    # Save it if we successfully found a station
                                    if station_name:
                                        all_trains.append({
                                            "n": train_name,
                                            "s": station_name,
                                            "b": is_between,
                                            "d": direction
                                        })
                    except Exception:
                        # A timeout here just means no trains are running in this direction right now
                        pass 

        except Exception as e:
            print(f"❌ Critical Error during scraping: {e}")
        finally:
            await browser.close()

    return all_trains

async def main():
    # 1. Scrape the data
    trains_list = await scrape_all()
    
    # 2. Save it straight to JSON for the ESP32
    print(f"📦 Generating JSON with {len(trains_list)} active trains...")
    
    with open('live_trains.json', 'w') as f:
        json.dump(trains_list, f)
    
    print("✅ Success! live_trains.json saved.")

if __name__ == "__main__":
    asyncio.run(main())
