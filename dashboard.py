import streamlit as st
import pandas as pd
from google.cloud import firestore as gcp_firestore
from google.auth.credentials import AnonymousCredentials
import datetime

# --- CONFIGURATION ---
GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"
FIRESTORE_COLLECTION_NAME = "live_train_data"
FIRESTORE_DOCUMENT_NAME = "current_status"
SCRAPE_INTERVAL_SECONDS = 60

# --- HARDWARE & DISPLAY CONFIGURATION ---
STRIP_1_LINES = ["Kyushu", "Sanyo", "Tokaido", "Tohoku", "Hokkaido"]
STRIP_2_LINES = ["Hokuriku"]

# Distinct colors for each line
LINE_COLORS = {
    "Kyushu": "#ff4b4b",   # Red
    "Sanyo": "#0068c9",    # Blue
    "Tokaido": "#f68b1e",  # Orange
    "Tohoku": "#29b09d",   # Teal/Green
    "Hokkaido": "#90ee90", # Light Green
    "Hokuriku": "#83c9ff", # Light Blue/Purple
}

# --- INITIALIZE FIRESTORE ---
@st.cache_resource
def initialize_firestore_client():
    try:
        # Keyless anonymous connection for public-read database
        creds = AnonymousCredentials()
        return gcp_firestore.Client(project=GCP_PROJECT_ID, credentials=creds)
    except Exception as e:
        st.error(f"Could not connect to Cloud Firestore. Error: {e}")
        return None

# --- CORE DATA RETRIEVAL FUNCTION ---
@st.cache_data(ttl=SCRAPE_INTERVAL_SECONDS)
def get_shinkansen_data(_db):
    if _db is None:
        return pd.DataFrame(), "Never"

    try:
        doc_ref = _db.collection(FIRESTORE_COLLECTION_NAME).document(FIRESTORE_DOCUMENT_NAME)
        doc = doc_ref.get()

        if not doc.exists:
            st.sidebar.error("Document 'current_status' NOT FOUND.")
            return pd.DataFrame(), "Not Found"

        doc_data = doc.to_dict()
        routes_data = doc_data.get("routes", {})
        last_updated = doc_data.get("timestamp", "Unknown")
        
        all_trains_list = []
        for route_name, trains in routes_data.items():
            # Clean up route names to map them cleanly to our colors
            mapped_route = route_name
            for known_line in LINE_COLORS.keys():
                if known_line.lower() in route_name.lower():
                    mapped_route = known_line
                    break

            for train in trains:
                all_trains_list.append({
                    "Line": mapped_route,
                    "Train": train.get("name", "Unknown"),
                    "Current Station": train.get("current_station", "Unknown"),
                    "Destination": train.get("destination", "Unknown"),
                    "Direction": train.get("direction", "Unknown"),
                    "Action": train.get("action", "Unknown"),
                    "Time": train.get("event_time", "Unknown"),
                })
        
        df = pd.DataFrame(all_trains_list)
        return df, last_updated

    except Exception as e:
        st.sidebar.error(f"Firestore Read Failed: {e}")
        return pd.DataFrame(), "Error"

# --- STREAMLIT DASHBOARD LAYOUT ---
def main():
    st.set_page_config(page_title="Shinkansen Tracking API", page_icon="🚄", layout="wide")
    st.title("🚄 Shinkansen Distance & Position Tracker")

    db = initialize_firestore_client()
    data, last_updated_iso = get_shinkansen_data(db) 

    with st.container():
        st.markdown(f"**Last Scraper Sync (UTC):** `{last_updated_iso}`")
        st.caption("Keyless connection active. Database is set to public-read.")
        st.divider()

    if not data.empty:
        # 1. Sidebar Filter mapped to strips
        st.sidebar.header("Filter by Hardware Strip")
        show_strip_1 = st.sidebar.checkbox("Strip 1 Lines", value=True)
        show_strip_2 = st.sidebar.checkbox("Strip 2 Lines", value=True)
        
        selected_lines = []
        if show_strip_1:
            selected_lines.extend(STRIP_1_LINES)
        if show_strip_2:
            selected_lines.extend(STRIP_2_LINES)
            
        filtered_data = data[data['Line'].isin(selected_lines)]

        # 2. Main Tracking Table
        st.subheader("Live Train Positions")

        # Function to color the 'Line' column text
        def color_line(val):
            color = LINE_COLORS.get(val, 'inherit')
            return f'color: {color}; font-weight: bold;'

        display_cols = ['Line', 'Train', 'Direction', 'Current Station', 'Destination', 'Action', 'Time']
        
        # Apply styling and display
        styled_df = filtered_data[display_cols].style.map(color_line, subset=['Line'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.divider()

        # 3. Hardware Mapping Preview
        st.subheader("Hardware Strip Mapping Preview")
        st.caption("Current configuration mapped for the dual 60-LED arrays.")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Strip 1")
            for line in STRIP_1_LINES:
                color = LINE_COLORS.get(line, "#fff")
                st.markdown(f"- <span style='color:{color}; font-weight:bold;'>{line}</span>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("### Strip 2")
            for line in STRIP_2_LINES:
                color = LINE_COLORS.get(line, "#fff")
                st.markdown(f"- <span style='color:{color}; font-weight:bold;'>{line}</span>", unsafe_allow_html=True)

    else:
        st.warning("No live train data available. Please check the scraper job execution.")

if __name__ == "__main__":
    main()
