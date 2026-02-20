import streamlit as st
import pandas as pd
from google.cloud import firestore as gcp_firestore
from google.auth.credentials import AnonymousCredentials

# --- CONFIG ---
GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"

@st.cache_resource
def get_db():
    return gcp_firestore.Client(project=GCP_PROJECT_ID, credentials=AnonymousCredentials())

def main():
    st.set_page_config(page_title="UCF Shinkansen Map", layout="wide")
    st.title("🚄 Shinkansen Live LED Feed")
    
    db = get_db()
    doc = db.collection("live_train_data").document("current_status").get()
    
    if doc.exists:
        data = doc.to_dict()
        st.write(f"**Last Sync:** `{data.get('timestamp')}`")
        
        rows = []
        for route, trains in data.get("routes", {}).items():
            for t in trains:
                # Combine a+b for the dashboard view
                pos = f"Between {t['station_a']} & {t['station_b']}" if t['is_between'] else f"At {t['station_a']}"
                rows.append({
                    "Line": route,
                    "Train": t['name'],
                    "Position": pos,
                    "Station A": t['station_a'],
                    "Station B": t['station_b']
                })
        
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Add a visual reminder for your hardware build
        st.success("📡 Data ready for ESP32-C5 (288 LED Mapping)")
    else:
        st.error("No data found. Trigger the GitHub Scraper Action.")

if __name__ == "__main__":
    main()
