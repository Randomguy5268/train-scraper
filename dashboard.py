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
        # Keyless connection for Streamlit Community Cloud
        return gcp_firestore.Client(project=GCP_PROJECT_ID, credentials=AnonymousCredentials())
    except Exception as e:
        st.error(f"Firestore Connection Error: {e}")
        return None

@st.cache_data(ttl=60)
def get_shinkansen_data(_db):
    if _db is None: return pd.DataFrame(), "Never"
    
    doc = _db.collection("live_train_data").document("current_status").get()
    if not doc.exists: return pd.DataFrame(), "Document Missing"
    
    raw_data = doc.to_dict()
    routes = raw_data.get("routes", {})
    rows = []
    
    for route_name, trains in routes.items():
        for t in trains:
            # Clean up line names for coloring
            display_line = route_name
            for key in LINE_COLORS.keys():
                if key.lower() in route_name.lower():
                    display_line = key
                    break
            
            rows.append({
                "Line": display_line,
                "Train": t.get("name", "Unknown"),
                "Direction": t.get("direction", "Unknown"),
                "station_a": t.get("station_a", "Unknown"),
                "station_b": t.get("station_b", None),
                "is_between": t.get("is_between", False),
                "Destination": t.get("destination", "Unknown"),
                "Time": t.get("event_time", "")
            })
    return pd.DataFrame(rows), raw_data.get("timestamp", "Unknown")

def main():
    st.set_page_config(page_title="Shinkansen Live Tracker", layout="wide")
    
    db = initialize_firestore_client()
    df, last_upd = get_shinkansen_data(db)

    st.title("🚄 Shinkansen Live Position Tracker")
    st.write(f"**Data Updated (UTC):** `{last_upd}`")

    if not df.empty:
        # --- NEW LOCATION LOGIC ---
        def format_live_position(row):
            if row['is_between'] and row['station_b']:
                return f"Between {row['station_a']} and {row['station_b']}"
            return f"At {row['station_a']}"

        df['Live Position'] = df.apply(format_live_position, axis=1)

        # Reorder and filter columns for display
        display_cols = ['Line', 'Train', 'Direction', 'Live Position', 'Destination', 'Time']
        
        # Style the 'Line' column with colors
        def color_line_text(val):
            color = LINE_COLORS.get(val, "#ffffff")
            return f"color: {color}; font-weight: bold;"

        styled_df = df[display_cols].style.map(color_line_text, subset=['Line'])
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # --- LED STRIP PREVIEW (For your 288-LED strips) ---
        st.divider()
        st.subheader("Physical LED Map Status")
        c1, c2 = st.columns(2)
        with c1:
            st.info("Strip 1: Main Corridor (Kagoshima ↔ Hakodate)")
            st.caption("0-143: Upbound | 144-287: Downbound")
        with c2:
            st.info("Strip 2: Branch Lines (72 LEDs per line)")
            st.caption("Hokuriku | Joetsu | Akita | Yamagata")

    else:
        st.warning("No data found in Firestore. Make sure the scraper has finished a run.")

if __name__ == "__main__":
    main()
