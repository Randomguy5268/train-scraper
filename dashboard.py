import streamlit as st
import pandas as pd
from google.cloud import firestore as gcp_firestore
from google.auth.credentials import AnonymousCredentials

# --- CONFIGURATION ---
GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"
LINE_COLORS = {
    "Kyushu": "#ff4b4b", "Sanyo": "#0068c9", "Tokaido": "#f68b1e",
    "Tohoku": "#29b09d", "Hokkaido": "#90ee90", "Hokuriku": "#83c9ff",
    "Joetsu": "#f0f2f6", "Akita": "#ff00ff", "Yamagata": "#00ff00"
}

@st.cache_resource
def initialize_firestore_client():
    try:
        return gcp_firestore.Client(project=GCP_PROJECT_ID, credentials=AnonymousCredentials())
    except Exception as e:
        st.error(f"Firestore Error: {e}")
        return None

@st.cache_data(ttl=60)
def get_shinkansen_data(_db):
    if _db is None: return pd.DataFrame(), "Never"
    doc = _db.collection("live_train_data").document("current_status").get()
    if not doc.exists: return pd.DataFrame(), "Not Found"
    
    data = doc.to_dict()
    routes = data.get("routes", {})
    rows = []
    
    for route, trains in routes.items():
        for t in trains:
            # Map the route name to our color keys
            display_line = route
            for key in LINE_COLORS.keys():
                if key.lower() in route.lower():
                    display_line = key
                    break
            
            rows.append({
                "Line": display_line,
                "Train": t.get("name", "Unknown"),
                "Direction": t.get("direction", "Unknown"),
                "station_a": t.get("station_a", ""),
                "station_b": t.get("station_b", ""),
                "is_between": t.get("is_between", False),
                "Destination": t.get("destination", "Unknown"),
                "Time": t.get("event_time", "")
            })
    return pd.DataFrame(rows), data.get("timestamp", "Unknown")

def main():
    st.set_page_config(page_title="Shinkansen Tracker", layout="wide")
    db = initialize_firestore_client()
    df, last_upd = get_shinkansen_data(db)

    st.title("🚄 Shinkansen Live Position Tracker")
    st.write(f"Last Updated: `{last_upd}`")

    if not df.empty:
        # Create the human-readable position string
        def format_pos(row):
            if row['is_between'] and row['station_b']:
                return f"Between {row['station_a']} and {row['station_b']}"
            return f"At {row['station_a']}"

        df['Live Position'] = df.apply(format_pos, axis=1)

        # Style and Display
        cols = ['Line', 'Train', 'Direction', 'Live Position', 'Destination', 'Time']
        styled = df[cols].style.map(lambda x: f"color: {LINE_COLORS.get(x, 'inherit')}; font-weight: bold;", subset=['Line'])
        
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.warning("Waiting for scraper data...")

if __name__ == "__main__":
    main()
