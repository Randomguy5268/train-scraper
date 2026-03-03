import json
import asyncio
import re
from datetime import datetime
import pytz
from playwright.async_api import async_playwright

WEBSITE_URL = "https://www.jr.cyberstation.ne.jp/index_en.html"

def inject_ghost_trains(live_trains):
    """
    Injects mountain Shinkansens.
    Ensures lights stay lit until the next station is reached.
    """
    try:
        with open('timetable.json', 'r') as f:
            timetable = json.load(f)
    except FileNotFoundError:
        print("⚠️ timetable.json not found!")
        return live_trains

    rename_map = {
        "SAKURAMBOHIGASHINE": "SAKURANBO-HIGASHINE",
        "NASUSHIOBARA": "NASU-SHIOBARA",
        "HIGASHIHIROSHIMA": "HIGASHI-HIROSHIMA",
        "KAMINOYAMA-ONSEN": "KAMINOYAMA ONSEN",
        "SHIZUKUISHI": "SHIZUKUSHI", 
        "SHIROISHIZAO": "SHIROISHI-ZAO"
    }

    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst)
    current_minutes = now.hour * 60 + now.minute

    def to_mins(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m

    ghosts_added = 0
    for train_id, data in timetable.items():
        stops = data.get("stops", [])
        if len(stops) < 2: continue

        direction = data.get("direction", "Down")
        train_name = train_id.split('_')[0] 

        # We look at the total window of the train's mountain journey
        first_stop_time = to_mins(stops[0]['time'])
        last_stop_time = to_mins(stops[-1]['time'])

        # If the train is currently active in the mountains
        if first_stop_time <= current_minutes <= last_stop_time:
            for i in range(len(stops) - 1):
                time_a = to_mins(stops[i]['time'])
                time_b = to_mins(stops[i+1]['time'])

                # The train "belongs" to this segment until it hits time_b
                if time_a <= current_minutes < time_b:
                    sA = rename_map.get(stops[i]['station'], stops[i]['station'])
                    sB = rename_map.get(stops[i+1]['station'], stops[i+1]['station'])
                    
                    # If it's exactly at the minute of departure, b=False (Solid LED)
                    # If it's anytime after that but before the next stop, b=True (Moving/Between)
                    is_between = current_minutes > time_a

                    live_trains.append({
                        "n": train_name,
                        "s": sA,
                        "s_b": sB,
                        "b": is_between,
                        "d": direction
                    })
                    ghosts_added += 1
                    break 

    print(f"👻 Injected {ghosts_added} Ghost Trains with persistence logic.")
    return live_trains

async def scrape_live_data():
    print("🚀 Starting Cyberstation Scraper...")
    all_trains = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(WEBSITE_URL, timeout=60000)
            await page.click('a:has-text("Shinkansen Status")')
            
            # --- OPERATING HOURS CHECK ---
            try:
                # If this button isn't visible in 10s, the site is likely closed for the night
                await page.wait_for_selector("#input-select-route", timeout=10000)
            except Exception:
                print("🌙 JR Cyberstation is currently closed. Skipping live scrape.")
                await browser.close()
                return [] 
            # -----------------------------

            await page.click("#input-select-route")
            
            route_buttons = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
            route_names = [await (await b.query_selector("span.route_name")).inner_text() for b in route_buttons if await b.query_selector("span.route_name")]
            await page.keyboard.press("Escape")

            for i, route_name in enumerate(route_names):
                await page.click("#input-select-route")
                btn = (await page.query_selector_all("#modal-select-route-shinkansen button.uk-button"))[i]
                await btn.click()
                
                for direction in ["Up", "Down"]:
                    await page.click("#up_button" if direction == "Up" else "#down_button")
                    await page.click("#train_info_request")
                    try:
                        await page.wait_for_selector("#table_info_status_detail tbody tr", timeout=5000)
                        rows = await page.query_selector_all("#table_info_status_detail tbody tr")
                        for row in rows:
                            cols = await row.query_selector_all("td")
                            if len(cols) >= 2:
                                status = (await cols[1].inner_text()).lower()
                                if "service ended" not in status and status != "":
                                    loc_el = await cols[0].query_selector("small")
                                    if loc_el:
                                        loc_txt = (await loc_el.inner_text()).strip()
                                        full_txt = await cols[0].inner_text()
                                        t_name = full_txt.replace(loc_txt, "").strip().split('(')[0].strip()
                                        
                                        if "Running between" in loc_txt:
                                            m = re.search(r'between\s+(.+?)\s+and\s+(.+)', loc_txt, re.IGNORECASE)
                                            if m:
                                                all_trains.append({
                                                    "n": t_name, "d": direction, "b": True,
                                                    "s": m.group(1).strip().split('(')[0].strip(),
                                                    "s_b": m.group(2).strip().split('(')[0].strip()
                                                })
                                        elif "Stopped at" in loc_txt:
                                            m = re.search(r'at\s+(.+)', loc_txt, re.IGNORECASE)
                                            if m:
                                                all_trains.append({
                                                    "n": t_name, "d": direction, "b": False,
                                                    "s": m.group(1).strip().split('(')[0].strip()
                                                })
                    except: pass
        finally:
            await browser.close()
    return all_trains

async def main():
    live = await scrape_live_data()
    final = inject_ghost_trains(live)
    
    with open('live_trains.json', 'w') as f:
        json.dump(final, f, indent=4)
    print(f"✅ live_trains.json updated with {len(final)} total trains.")

if __name__ == "__main__":
    asyncio.run(main())
