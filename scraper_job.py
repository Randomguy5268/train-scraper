import json
import asyncio
import re
from playwright.async_api import async_playwright

WEBSITE_URL = "https://www.jr.cyberstation.ne.jp/index_en.html"

async def scrape_all():
    print("🚀 Starting Cyberstation Scraper (Using HTML <small> tag parsing)...")
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
                if span:
                    route_names.append(await span.inner_text())
                else:
                    route_names.append("Unknown")

            await page.keyboard.press("Escape")
            await page.wait_for_selector("#modal-select-route-shinkansen", state="hidden")

            print(f"✅ Found {len(route_names)} routes to scan.")

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
                            
                            # Ensure we have at least 2 columns like the HTML image shows
                            if len(cols) >= 2:
                                delay_info = await cols[1].inner_text()
                                delay_info = delay_info.strip()

                                # Check if train is still running
                                if "service ended" not in delay_info.lower() and delay_info != "":
                                    
                                    # --- THE HTML SCALPEL ---
                                    # Find the <small> tag inside the first column
                                    small_tag = await cols[0].query_selector("small")
                                    
                                    if small_tag:
                                        location_text = await small_tag.inner_text()
                                        location_text = location_text.strip()
                                        
                                        # To get the train name, we get the full text of the column and remove the <small> text
                                        full_text = await cols[0].inner_text()
                                        train_name = full_text.replace(location_text, "").strip()
                                        
                                        station_a = ""
                                        station_b = ""
                                        is_between = False
                                        
                                        # Parse the extracted <small> tag text
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
                                        else:
                                            print(f"      ⚠️ Parser missed location: {location_text}")
                                    else:
                                        print("      ⚠️ No <small> tag found in this row.")

                    except Exception as e:
                        pass 

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
