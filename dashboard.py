import streamlit as st
import pandas as pd
from google.cloud import firestore as gcp_firestore
from google.auth.credentials import AnonymousCredentials

GCP_PROJECT_ID = "project-ef09c9bb-3689-4f27-8cf"

@st.cache_resource
def get_db():
    return gcp_firestore.Client(project=GCP_PROJECT_ID, credentials=AnonymousCredentials())

st.set_page_config(page_title="UCF Shinkansen Live", layout="wide")
st.title("🚄 Shinkansen Live LED Feed")

db = get_db()
doc = db.collection("live_train_data").document("current_status").get()

if doc.exists:
    data = doc.to_dict()
    st.write(f"**Last Sync:** `{data.get('timestamp')}`")
    
    rows = []
    for route, trains in data.get("routes", {}).items():
        for t in trains:
            pos = f"Between {t['station_a']} & {t['station_b']}" if t['is_between'] else f"At {t['station_a']}"
            rows.append({
                "Line": route,
                "Train": t['name'],
                "Direction": t['direction'],
                "Live Position": pos,
                "Status": t.get('status', 'Normal')
            })
    
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("No trains currently running.")
