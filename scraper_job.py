import asyncio
from playwright.async_api import async_playwright
from google.cloud import firestore
from datetime import datetime, timezone
import sys
import re

# --- CONFIGURATION ---
COLLECTION_NAME = "live_train_data"
DOCUMENT_NAME = "current_status"


def parse_location(train_name_string):
    """Parses JR Cyberstation text to find station names."""
    # Look for "between X and Y"
    between_match = re.search(r"\(between (.*?) and (.*?)\)", train_name_string)
    # Look for "at X"
    at_match = re.search(r"\(at (.*?)\)", train_name_string)
    
    if between_match:
        return {
            "station_a": between_match.group(1).strip(),
            "station_b": between_match.group(2).strip(),
            "is_between": True
        }
    elif at_match:
        return {
            "station_a": at_match.group(1).strip(),
            "station_b": None,
            "is_between": False
        }
    return {"station_a": "Unknown", "station_b": None, "is_between": False}

# IMPORTANT: In your scrape loop, you must call this:
# loc_data = parse_location(raw_train_name_from_web)
# train_entry = {
#    "name": raw_train_name_from_web,
#    "station_a": loc_data["station_a"],
#    "station_b": loc_data["station_b"],
#    "is_between": loc_data["is_between"],
#    ...
# }
async def init_firestore():
    return firestore.AsyncClient()

async def scrape_once():
    # ... (Your existing Playwright scraping logic here) ...
    # Inside your loop where you process the 'all_trains' list:
    
    # Example of how to integrate the parser inside your loop:
    # loc = parse_location(raw_name_from_site)
    # train_entry = {
    #     "name": raw_name_from_site,
    #     "station_a": loc["station_a"],
    #     "station_b": loc["station_b"],
    #     "is_between": loc["is_between"],
    #     "direction": direction,
    #     "event_time": event_time,
    #     "destination": get_destination(route, direction)
    # }
    pass

# Update the main execution to use the new fields
