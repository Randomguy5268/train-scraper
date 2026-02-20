import streamlit as st
import pandas as pd
from google.cloud import firestore as gcp_firestore
from google.auth.credentials import AnonymousCredentials

GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"

@st.cache_resource
def get_db():
    return gcp_firestore.Client(project=GCP_PROJECT_ID, credentials=AnonymousCredentials())

st.set_page_config(page_title="UCF Shinkansen Debug", layout="wide")
st.title("🚄 Shinkansen Live Feed Debugger")

db = get_db()
doc = db.collection("live_train_data").document("current_status").get()

if doc.exists:
    data = doc.to_dict()
    st.write(f"**Last Scraper Update:** `{data.get('timestamp')}`")
    
    # Check if 'routes' exists
    if "routes" in data:
        routes_data = data["routes"]
        all_trains = []
        
        for route_name, trains in routes_data.items():
            for t in trains:
                t['Route'] = route_name # Add route name to the row
                all_trains.append(t)
        
        if all_trains:
            st.success(f"Found {len(all_trains)} trains in Firestore!")
            df = pd.DataFrame(all_trains)
            st.dataframe(df) # Show everything
        else:
            st.warning("The 'routes' field exists, but it contains 0 trains.")
            st.json(data)
    else:
        st.error("The 'routes' field is missing from the Firestore document.")
        st.json(data)
else:
    st.error("The document 'live_train_data/current_status' does not exist in Firestore.")
