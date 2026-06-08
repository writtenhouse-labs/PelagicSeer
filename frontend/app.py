import os
from pathlib import Path

import requests
import streamlit as st


API_BASE_URL = os.getenv("PELAGICSEER_API_BASE_URL", "http://127.0.0.1:8000")
API_TIMEOUT_SECONDS = int(os.getenv("PELAGICSEER_API_TIMEOUT_SECONDS", "300"))
ICON_PATH = Path(__file__).parent / "assets" / "BlueFinTuna.png"

st.set_page_config(page_title="PelagicSeer", page_icon=str(ICON_PATH))

_, logo_column, _ = st.columns([1, 1, 1])
with logo_column:
    st.image(str(ICON_PATH), width=160)
st.title("PelagicSeer")

with st.form("advice-form"):
    city = st.text_input("City", value="San Diego")
    state = st.text_input("State", value="CA")
    species = st.text_input("Species", value="tuna")
    target_depth_ft = st.number_input("Target depth (ft)", min_value=0, value=250)
    submitted = st.form_submit_button("Get advice")

if submitted:
    payload = {
        "city": city,
        "state": state,
        "species": species,
        "target_depth_ft": target_depth_ft,
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/advice",
            json=payload,
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        st.error(f"Could not reach PelagicSeer API: {exc}")
    else:
        body = response.json()
        recommendation = body["recommendation"]
        location = body["location"]
        st.caption(
            f"{location['city']}, {location['state']} -> "
            f"{location['latitude']:.4f}, {location['longitude']:.4f}"
        )
        if recommendation["label"] == "too_far":
            st.warning(recommendation["summary"])
            for reason in recommendation["reasons"]:
                st.write(f"- {reason}")
            st.stop()

        st.metric("Recommendation score", recommendation["score"])
        st.subheader(recommendation["summary"])
        st.write("Conditions")
        st.json(body["conditions"])
        st.write("Reasons")
        for reason in recommendation["reasons"]:
            st.write(f"- {reason}")
