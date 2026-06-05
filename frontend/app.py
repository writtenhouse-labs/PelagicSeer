import os

import requests
import streamlit as st


API_BASE_URL = os.getenv("PELAGICSEER_API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="PelagicSeer", page_icon="PS")
st.title("PelagicSeer")

with st.form("advice-form"):
    latitude = st.number_input("Latitude", value=32.7157, format="%.4f")
    longitude = st.number_input("Longitude", value=-117.1611, format="%.4f")
    species = st.text_input("Species", value="tuna")
    target_depth_ft = st.number_input("Target depth (ft)", min_value=0, value=250)
    submitted = st.form_submit_button("Get advice")

if submitted:
    payload = {
        "latitude": latitude,
        "longitude": longitude,
        "species": species,
        "target_depth_ft": target_depth_ft,
    }

    try:
        response = requests.post(f"{API_BASE_URL}/advice", json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        st.error(f"Could not reach PelagicSeer API: {exc}")
    else:
        body = response.json()
        recommendation = body["recommendation"]
        st.metric("Recommendation score", recommendation["score"])
        st.subheader(recommendation["summary"])
        st.write("Conditions")
        st.json(body["conditions"])
        st.write("Reasons")
        for reason in recommendation["reasons"]:
            st.write(f"- {reason}")
