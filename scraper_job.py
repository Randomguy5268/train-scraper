import json
import asyncio
import re
from datetime import datetime
import pytz # Run 'pip install pytz' if you don't have it
from playwright.async_api import async_playwright

WEBSITE_URL = "https://www.jr.cyberstation.ne.jp/index_en.html"

def inject_ghost_trains(live_trains):
    """
    Reads your new timetable.json and injects the Akita/Yamagata trains
    based on the current time in Japan.
    """
    try:
        with open('timetable.json', 'r') as f:
            timetable = json.load(f)
    except FileNotFoundError:
        print("⚠️ timetable.json not found! Mountain lines will be empty.")
        return live_trains
    # Add this inside inject_ghost_trains
rename_map = {
    "SAKURAMBOHIGASHINE": "SAKURANBO-HIGASHINE",
    "NASUSHIOBARA": "NASU-SHIOBARA",
    "HIGASHIHIROSHIMA": "HIGASHI-HIROSHIMA",
    "KAMINOYAMA-ONSEN": "KAMINOYAMA ONSEN",
    "SHIZUOKUISHI": "SHIZUKUSHI" 
}

# Then, where you set the station name:
s_name = stop_a['station']
ghost_train["s"] = rename_map.get(s_name, s_name)
    # Get current time in Japan
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst)
    current_minutes = now.hour * 60 + now.minute

    def to_mins(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m

    ghosts_added = 0

    for train_id, data in timetable.items():
        stops = data.get("stops", [])
        if len(stops) < 2:
            continue

        direction = data.get("direction", "Down")
        # Extract name (e.g., "Komachi") from the ID we generated
        train_name = train_id.split('_')[0] 

        for i in range(len(stops) - 1):
            stop_a = stops[i]
            stop_b = stops[i+1]
            time_a = to_mins(stop_a['time'])
            time_b = to_mins(stop_b['time'])

            # Check if train is currently between or at these stations
            if time_a <= current_minutes <= time_b:
                is_between = current_minutes > time_a
                
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
                break 

    print(f"👻 Injected {ghosts_added} Ghost Trains for mountain lines.")
    return live_trains

async def scrape_all():
    print("🚀 Starting Cyberstation Scraper...")
    all_trains = []

    async with async_playwright() as p:
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

            await page.click("#input-select-route")
            await page.wait_for_selector("#modal-select-route-shinkansen.uk-open", timeout=5000)

            route_buttons = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
            route_names = []
            for btn in route_buttons:
                span = await btn.query_selector("span.route_name")
                route_names.append(await span.inner_text() if span else "Unknown")

            await page.keyboard.press("Escape")
            await page.wait_for_selector("#modal-select-route-shinkansen", state="hidden")

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
                
                for direction in ["Up", "Down"]:
                    if direction == "Up": await page.click("#up_button")
                    else: await page.click("#down_button")

                    await page.click("#train_info_request")

                    try:
                        await page.wait_for_selector("#table_info_status_detail tbody tr", timeout=5000)
                        rows = await page.query_selector_all("#table_info_status_detail tbody tr")

                        for row in rows:
                            cols = await row.query_selector_all("td")
                            if len(cols) >= 2:
                                delay_info = (await cols[1].inner_text()).strip()
                                if "service ended" not in delay_info.lower() and delay_info != "":
                                    small_tag = await cols[0].query_selector("small")
                                    if small_tag:
                                        location_text = (await small_tag.inner_text()).strip()
                                        full_text = await cols[0].inner_text()
                                        train_name = full_text.replace(location_text, "").strip()
                                        
                                        # Clean name (remove "(Tohoku Line)" etc)
                                        train_name = train_name.split('(')[0].strip()
                                        
                                        station_a = ""
                                        station_b = ""
                                        is_between = False
                                        
                                        if "Running between" in location_text:
                                            match = re.search(r'Running between\s+(.+?)\s+and\s+(.+)', location_text, re.IGNORECASE)
                                            if match:
                                                station_a = match.group(1).strip().split('(')[0].strip()
                                                station_b = match.group(2).strip().split('(')[0].strip()
                                                is_between = True
                                        elif "Stopped at" in location_text:
                                            match = re.search(r'Stopped at\s+(.+)', location_text, re.IGNORECASE)
                                            if match:
                                                station_a = match.group(1).strip().split('(')[0].strip()

                                        if station_a:
                                            train_data = {"n": train_name, "s": station_a, "b": is_between, "d": direction}
                                            if is_between: train_data["s_b"] = station_b
                                            all_trains.append(train_data)
                    except:
                        pass

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await browser.close()

    return all_trains

async def main():
    # 1. Get live data from Cyberstation
    trains_list = await scrape_all()
    
    # 2. Inject Ghost data from timetable.json
    final_list = inject_ghost_trains(trains_list)
    
    print(f"\n📦 Saving {len(final_list)} trains to live_trains.json...")
    with open('live_trains.json', 'w') as f:
        json.dump(final_list, f, indent=4)
    print("✅ Success!")

if __name__ == "__main__":
    asyncio.run(main())
