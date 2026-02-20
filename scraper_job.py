import json
import asyncio
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
WEBSITE_URL = "https://www.jr.cyberstation.ne.jp/index_en.html"

# --- DIRECTION MAPPING ---
DESTINATION_MAP = {
    ("Tokaido/Sanyo", "Up"): "TOKYO",
    ("Tokaido/Sanyo", "Down"): "HAKATA",
    ("Tohoku/Hokkaido", "Up"): "TOKYO",
    ("Tohoku/Hokkaido", "Down"): "HAKODATE-HOKUTO",
    ("Joetsu", "Up"): "TOKYO",
    ("Joetsu", "Down"): "NIIGATA",
    ("Hokuriku", "Up"): "TOKYO",
    ("Hokuriku", "Down"): "TSURUGU",
    ("Yamagata", "Up"): "TOKYO",
    ("Yamagata", "Down"): "SHINJO",
    ("Akita", "Up"): "TOKYO",
    ("Akita", "Down"): "AKITA",
    ("Kyushu", "Up"): "HAKATA",
    ("Kyushu", "Down"): "KAGOSHIMA-CHUO",
}

def get_destination(route, direction):
    return DESTINATION_MAP.get((route, direction), f"To {direction}bound {route}")

async def scrape_all():
    print("🚀 Starting Cyberstation Scraper (English Site)...")
    all_trains = []

    async with async_playwright() as p:
        # Use a real user agent to prevent blocks
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

            # Get route names
            await page.click("#input-select-route")
            await page.wait_for_selector("#modal-select-route-shinkansen.uk-open", timeout=5000)

            route_buttons_initial = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
            route_names = []
            for btn in route_buttons_initial:
                span = await btn.query_selector("span.route_name")
                if span:
                    route_names.append(await span.inner_text())
                else:
                    route_names.append("Unknown")

            await page.keyboard.press("Escape")
            await page.wait_for_selector("#modal-select-route-shinkansen", state="hidden")

            print(f"✅ Found {len(route_names)} routes to scan.")

            # Iterate through each route
            for i, route_name in enumerate(route_names):
                print(f"🔍 Scanning route: {route_name}...")
                await page.click("#input-select-route")
                await page.wait_for_selector("#modal-select-route-shinkansen.uk-open", timeout=5000)

                all_buttons_fresh = await page.query_selector_all("#modal-select-route-shinkansen button.uk-button")
                if i < len(all_buttons_fresh):
                    await all_buttons_fresh[i].click()
                else:
                    await page.keyboard.press("Escape")
                    await page.wait_for_selector("#modal-select-route-shinkansen", state="hidden")
                    continue

                await page.wait_for_selector("#modal-select-route-shinkansen", state="hidden", timeout=5000)
                await page.wait_for_timeout(500) # Replaced time.sleep with Playwright's async sleep

                # Scrape Up and Down
                for direction in ["Up", "Down"]:
                    if direction == "Up":
                        await page.click("#up_button")
                    else:
                        await page.click("#down_button")

                    await page.click("#train_info_request")

                    try:
                        await page.wait_for_selector("#table_info_status_detail tbody tr", timeout=7000)
                        rows = await page.query_selector_all("#table_info_status_detail tbody tr")

                        destination_station = get_destination(route_name, direction)

                        for row in rows:
                            cols = await row.query_selector_all("td")
                            if len(cols) >= 2:
                                train_name_raw = await cols[0].inner_text()
                                status_raw = await cols[1].inner_text()
                                
                                train_name = ' '.join(train_name_raw.split())
                                status = ' '.join(status_raw.split())

                                # Filter out ended service
                                if "service ended" not in status.lower():
                                    all_trains.append({
                                        "n": train_name,
                                        "s": status, # Saving status for now, we'll need to extract station
                                        "b": False,  # Simplified for now
                                        "d": direction
                                    })
                    except Exception as e:
                        # Timeout just means no trains currently listed for that direction
                        pass 

        except Exception as e:
            print(f"❌ Critical Error during scraping: {e}")
        finally:
            await browser.close()

    return all_trains

async def main():
    trains_list = await scrape_all()
    
    # --- GENERATE LITE JSON FOR ESP32 ---
    print(f"📦 Generating JSON with {len(trains_list)} active trains...")
    
    with open('live_trains.json', 'w') as f:
        json.dump(trains_list, f)
    
    print("✅ Success! live_trains.json saved.")

if __name__ == "__main__":
    asyncio.run(main())
