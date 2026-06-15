import os
from datetime import date, timedelta
from pathlib import Path

import requests
import streamlit as st

from ui_status import install_swimming_fish_status


DEFAULT_API_BASE_URL = "https://pelagicseer-api-542566523617.us-central1.run.app"
API_BASE_URL = os.getenv("PELAGICSEER_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
API_TIMEOUT_SECONDS = int(os.getenv("PELAGICSEER_API_TIMEOUT_SECONDS", "90"))
ICON_PATH = Path(__file__).parent / "assets" / "BluefinTuna.png"

_MODE_HELP = {
    "live": "Window includes today — using the freshest live observations.",
    "historical": "Past window — conditions reflect archived observations near the window end.",
    "forecast": "Future window — conditions are a latest-observation proxy; confidence is capped.",
}

st.set_page_config(page_title="PelagicSeer", page_icon=str(ICON_PATH))
install_swimming_fish_status(ICON_PATH)

_, logo_column, _ = st.columns([1, 1, 1])
with logo_column:
    st.image(str(ICON_PATH), width=160)
st.title("PelagicSeer")
st.page_link("pages/1_Multi_Source_Data_Mapper.py", label="Open Multi-Source Data Mapper")

with st.form("advice-form"):
    city = st.text_input("City", value="San Diego")
    state = st.text_input("State", value="CA")
    species = st.text_input("Species", value="tuna")
    target_depth_ft = st.number_input("Target depth (ft)", min_value=0, value=250)
    date_columns = st.columns(2)
    with date_columns[0]:
        start_date = st.date_input("Start date", value=date.today())
    with date_columns[1]:
        end_date = st.date_input("End date", value=date.today() + timedelta(days=2))
    submitted = st.form_submit_button("Get advice")

if submitted:
    if start_date > end_date:
        st.error("Start date cannot be after end date.")
        st.stop()

    payload = {
        "city": city,
        "state": state,
        "species": species,
        "target_depth_ft": target_depth_ft,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }

    try:
        with st.spinner("Getting live ocean advice..."):
            response = requests.post(
                f"{API_BASE_URL}/advice",
                json=payload,
                timeout=API_TIMEOUT_SECONDS,
            )
        response.raise_for_status()
    except requests.RequestException as exc:
        st.error(f"Could not reach PelagicSeer API: {exc}")
        st.caption(f"API endpoint: {API_BASE_URL}")
    except ValueError as exc:
        st.error(f"PelagicSeer API returned an unreadable response: {exc}")
        st.caption(f"API endpoint: {API_BASE_URL}")
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

        date_range = body.get("date_range", {})
        mode = date_range.get("mode")
        if mode:
            st.caption(
                f"{date_range.get('start_date')} -> {date_range.get('end_date')} "
                f"({mode}). {_MODE_HELP.get(mode, '')}"
            )

        score_column, confidence_column = st.columns(2)
        score_column.metric("Recommendation score", recommendation["score"])
        confidence_column.metric("Confidence", recommendation.get("confidence", "n/a").title())
        st.subheader(recommendation["summary"])

        st.write("Conditions")
        st.json(body["conditions"])

        area_species = body.get("area_species", {})
        if area_species.get("available") and area_species.get("species"):
            st.write(f"Species recorded in this area ({area_species.get('total_species', 0)} total)")
            for entry in area_species["species"]:
                label = entry.get("common_name") or entry.get("scientific_name")
                detail = f" — {entry['scientific_name']}" if entry.get("common_name") else ""
                st.write(f"- {label}{detail}  ·  {entry.get('records', 0)} records")
        else:
            st.caption("No area species list was available for this window.")

        st.write("Reasons")
        for reason in recommendation["reasons"]:
            st.write(f"- {reason}")
