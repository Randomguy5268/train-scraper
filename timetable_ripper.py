import json
import asyncio
import urllib.parse
import re
from playwright.async_api import async_playwright

START_URL = "https://timetables.jreast.co.jp/en/"
TARGET_STATIONS = {
    "Yamagata": ["Fukushima", "Yonezawa", "Takahata", "Akayu", "Kaminoyama-Onsen", "Yamagata", "Tendo", "Sakurambohigashine", "Murayama", "Oishida", "Shinjo"],
    "Akita": ["Morioka", "Shizukuishi", "Tazawako", "Kakunodate", "Omagari", "Akita"]
}

async def scrape_timetables():
    print("🚂 Starting JR East Timetable Ripper (NO-CLICK BLAZING SPEED MODE)...")
    master_schedule = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        for line_name, stations in TARGET_STATIONS.items():
            train_prefix = "Tsubasa" if line_name == "Yamagata" else "Komachi"
            print(f"\n🏔️ --- Scraping the {line_name} Line ---")
            
            for station in stations:
                print(f"📍 Reading grid for {station}...")
                await page.goto(START_URL, timeout=60000)
                
                try:
                    await page.click(f'a:has-text("{station}")', timeout=5000)
                    await page.wait_for_load_state("networkidle")
                except Exception:
                    continue

                urls_to_visit = []
                try:
                    rows = await page.query_selector_all(f'tr:has-text("{line_name}")')
                    for row in rows:
                        direction_el = await row.query_selector('td:nth-child(2)')
                        if not direction_el: continue
                        
                        direction_text = await direction_el.inner_text()
                        direction = "Up" if "Inbound" in direction_text or "Tokyo" in direction_text else "Down"
                        
                        weekdays_link = await row.query_selector('a:has-text("Weekdays")')
                        if weekdays_link:
                            href = await weekdays_link.get_attribute("href")
                            absolute_url = urllib.parse.urljoin(page.url, href)
                            urls_to_visit.append({"url": absolute_url, "dir": direction})
                except Exception:
                    continue

                for target in urls_to_visit:
                    await page.goto(target["url"])
                    await page.wait_for_load_state("networkidle")
                    
                    # Find EVERY train link on the grid in one sweep
                    links = await page.locator('a[href*="/train/"]').element_handles()
                    
                    for link in links:
                        href = await link.get_attribute("href")
                        
                        # Extract the minute (e.g., "58")
                        minute_text = await link.inner_text()
                        minute_match = re.search(r'\d+', minute_text)
                        if not minute_match: continue
                        minute = minute_match.group(0).zfill(2)

                        # Extract the hour from the row the link is sitting in
                        row = await link.evaluate_handle('el => el.closest("tr")')
                        hour_text = await row.evaluate('el => { const cell = el.querySelector("th, td"); return cell ? cell.innerText : ""; }')
                        hour_match = re.search(r'\d+', hour_text)
                        if not hour_match: continue
                        hour = hour_match.group(0).zfill(2)

                        time_str = f"{hour}:{minute}"
                        
                        # Create a unique Train ID from the URL (e.g. Komachi_12345)
                        train_id = f"{train_prefix}_{href.split('/')[-1].replace('.html', '')}"
                        
                        if train_id not in master_schedule:
                            master_schedule[train_id] = {"direction": target["dir"], "stops": []}
                        
                        # Add the stop to this train's journey
                        existing_stops = [s["station"] for s in master_schedule[train_id]["stops"]]
                        if station.upper() not in existing_stops:
                            master_schedule[train_id]["stops"].append({
                                "station": station.upper(),
                                "time": time_str
                            })

        await browser.close()
        return master_schedule

async def main():
    schedule = await scrape_timetables()
    
    # Sort the stops by time so the ghost trains move in order
    for train in schedule:
        schedule[train]["stops"] = sorted(schedule[train]["stops"], key=lambda x: x["time"])

    print(f"\n📦 Saving master schedule with {len(schedule)} trains...")
    with open('timetable.json', 'w') as f:
        json.dump(schedule, f, indent=4)
    print("✅ Success! timetable.json saved.")

if __name__ == "__main__":
    asyncio.run(main())
