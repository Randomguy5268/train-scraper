import json
import asyncio
import re
from datetime import datetime
import pytz
from playwright.async_api import async_playwright

WEBSITE_URL = "https://www.jr.cyberstation.ne.jp/index_en.html"

def inject_ghost_trains(live_trains):
    """
    Reads the static timetable.json and injects mountain branch Shinkansens 
    (Akita/Yamagata lines) based on the current time in Japan.
    """
    try:
        with open('timetable.json', 'r') as f:
            timetable = json.load(f)
    except FileNotFoundError:
        print("⚠️ timetable.json not found. Run the timetable ripper first. Skipping mountain lines.")
        return live_trains

    # Get current time in Japan
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst)
    current_minutes = now.hour * 60 + now.minute

    ghosts_added = 0

    def to_mins(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m

    for train_id, data in timetable.items():
        stops = data.get("stops", [])
        if len(stops) < 2:
            continue

        direction = data.get("direction", "Down")
        train_name = train_id.split('_')[0]  # Extracts "Komachi" or "Tsubasa"

        # Find where the train is right now based on the clock
        for i in range(len(stops) - 1):
            stop_a = stops[i]
            stop_b = stops[i+1]

            time_a = to_mins(stop_a['time'])
            time_b = to_mins(stop_b['time'])

            # Handle midnight rollover just in case
            if time_b < time_a:
                time_b += 24 * 60

            # If the current time falls between these two stops
            if time_a <= current_minutes <= time_b:
                is_between = current_minutes > time_a and current_minutes < time_b

                ghost_train = {
                    "n": train_name,
                    "s": stop_a['station'],
                    "b": is_between,
                    "d": direction
                }
                
                if is_between:
                    ghost_train["s_b"] = stop_b['station']

                live_trains.append(ghost_train)
                ghosts_added += 1
                break # Found its current location, move to the next train in the schedule

    print(f"👻 Automatically injected {ghosts_added} scheduled mountain trains!")
    return live_trains

async def scrape_live_trains():
    """
    Scrapes the live JR Cyberstation website for main line Shinkansen data.
    """
    print("🚀 Starting Cyberstation Live Scraper...")
    all_trains = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print("📡 Navigating to JR Cyberstation...")
            await page.goto(WEBSITE_URL, timeout=60000)
            await page.click('a:has-text("Shinkansen Status")', timeout=10000)
            await page.wait_for_selector("#input-select-route", timeout=15000)

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

            print(f"✅ Found {len(route_names)} main routes to scan.")

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

                for direction in ["Up", "Down"]:
                    if direction == "Up":
                        await page.click("#up_button")
                    else:
                        await page.click("#down_button")

                    await page.click("#train_info_request")

                    try:
                        await page.wait_for_selector("#table_info_status_detail tbody tr", timeout=15000)
                        await page.wait_for_timeout(1000) 
                        
                        rows = await page.query_selector_all("#table_info_status_detail tbody tr")

                        for row in rows:
                            cols = await row.query_selector_all("td")
                            
                            if len(cols) >= 2:
                                delay_info = await cols[1].inner_text()
                                delay_info = delay_info.strip()

                                if "service ended" not in delay_info.lower() and delay_info != "":
                                    small_tag = await cols[0].query_selector("small")
                                    
                                    if small_tag:
                                        location_text = await small_tag.inner_text()
                                        location_text = location_text.strip()
                                        
                                        full_text = await cols[0].inner_text()
                                        train_name = full_text.replace(location_text, "").strip()
                                        
                                        station_a = ""
                                        station_b = ""
                                        is_between = False
                                        
                                        if "Running between" in location_text:
                                            match = re.search(r'Running between\s+(.+?)\s+and\s+(.+)', location_text, re.IGNORECASE)
                                            if match:
                                                station_a = match.group(1).strip()
                                                station_b = match.group(2).strip()
                                                is_between = True
                                                
                                        elif "Stopped at" in location_text:
                                            match = re.search(r'Stopped at\s+(.+)', location_text, re.IGNORECASE)
                                            if match:
                                                station_a = match.group(1).strip()
                                                is_between = False

                                        if station_a:
                                            train_data = {
                                                "n": train_name,
                                                "s": station_a,
                                                "b": is_between,
                                                "d": direction
                                            }
                                            if is_between:
                                                train_data["s_b"] = station_b  
                                                
                                            all_trains.append(train_data)

                    except Exception:
                        pass 

        except Exception as e:
            print(f"❌ Critical Error during scraping: {e}")
        finally:
            await browser.close()

    return all_trains

async def main():
    # 1. Scrape the live data for the main lines
    live_trains = await scrape_live_trains()
    
    # 2. Inject the scheduled ghost trains for the mountain lines
    complete_train_list = inject_ghost_trains(live_trains)

    print(f"\n📦 Generating final JSON payload with {len(complete_train_list)} active trains...")
    
    with open('live_trains.json', 'w') as f:
        json.dump(complete_train_list, f, indent=4)
    
    print("✅ Success! live_trains.json saved and ready for the ESP32.")

if __name__ == "__main__":
    asyncio.run(main())
