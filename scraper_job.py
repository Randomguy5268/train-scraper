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
        # Launch with a real-looking user agent to bypass anti-bot checks
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

            # Open the modal to find all route names
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

            # Loop through each Shinkansen route
            for i, route_name in enumerate(route_names):
                print(f"\n🔍 Scanning route: {route_name}...")
                
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

                # Check both Up and Down directions
                for direction in ["Up", "Down"]:
                    if direction == "Up":
                        await page.click("#up_button")
                    else:
                        await page.click("#down_button")

                    await page.click("#train_info_request")

                    try:
                        # Wait for the table, keeping the timeout generous for GitHub runners
                        await page.wait_for_selector("#table_info_status_detail tbody tr", timeout=15000)
                        await page.wait_for_timeout(1000) 
                        
                        rows = await page.query_selector_all("#table_info_status_detail tbody tr")
                        print(f"   -> Found {len(rows)} rows for {direction} direction")

                        for row in rows:
                            cols = await row.query_selector_all("td")
                            if len(cols) >= 2:
                                train_name_raw = await cols[0].inner_text()
                                status_raw = await cols[1].inner_text()
                                
                                train_name = ' '.join(train_name_raw.split())
                                status = ' '.join(status_raw.split())

                                # Skip trains that are done for the day
                                if "service ended" not in status.lower() and status.strip() != "":
                                    
                                    # --- THE NEW TEXT PARSER ---
                                    # Remove the "| On time" or "| Delay" part
                                    status_text = status.split('|')[0].strip()
                                    
                                    station_a = ""
                                    station_b = ""
                                    is_between = False
                                    
                                    # Case 1: Train is moving between two stations
                                    if "Running between" in status_text:
                                        match = re.search(r'Running between\s+(.+?)\s+and\s+(.+)', status_text, re.IGNORECASE)
                                        if match:
                                            station_a = match.group(1).strip()
                                            station_b = match.group(2).strip()
                                            is_between = True
                                            
                                    # Case 2: Train is stopped at a station
                                    elif "Stopped at" in status_text:
                                        match = re.search(r'Stopped at\s+(.+)', status_text, re.IGNORECASE)
                                        if match:
                                            station_a = match.group(1).strip()
                                            is_between = False

                                    # Save the clean data
                                    if station_a:
                                        train_data = {
                                            "n": train_name,
                                            "s": station_a,
                                            "b": is_between,
                                            "d": direction
                                        }
                                        # Include the destination station so the ESP32 can light up the LED between them
                                        if is_between:
                                            train_data["s_b"] = station_b  
                                            
                                        all_trains.append(train_data)
                                    else:
                                        print(f"      ⚠️ Parser missed! Raw status: {status}")

                    except Exception as e:
                        print(f"   -> ❌ No trains found or Timeout for {direction}: {e}")

        except Exception as e:
            print(f"❌ Critical Error during scraping: {e}")
        finally:
            await browser.close()

    return all_trains

async def main():
    trains_list = await scrape_all()
    print(f"\n📦 Generating JSON with {len(trains_list)} active trains...")
    
    with open('live_trains.json', 'w') as f:
        json.dump(trains_list, f)
    
    print("✅ Success! live_trains.json saved.")

if __name__ == "__main__":
    asyncio.run(main())
