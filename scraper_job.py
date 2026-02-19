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
    """
    Extracts station names and positional state from the train name string.
    Example: "Nozomi 12 (at Nagoya)" -> station_a: Nagoya, is_between: False
    Example: "Hayabusa 5 (between Sendai and Furukawa)" -> station_a: Sendai, station_b: Furukawa, is_between: True
    """
    # Regex for "at" pattern
    at_match = re.search(r"\(at (.*?)\)", train_name_string)
    # Regex for "between" pattern
    between_match = re.search(r"\(between (.*?) and (.*?)\)", train_name_string)
    
    if at_match:
        return {
            "station_a": at_match.group(1).strip(),
            "station_b": None,
            "is_between": False
        }
    elif between_match:
        return {
            "station_a": between_match.group(1).strip(),
            "station_b": between_match.group(2).strip(),
            "is_between": True
        }
    
    return {"station_a": "Unknown", "station_b": None, "is_between": False}

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
