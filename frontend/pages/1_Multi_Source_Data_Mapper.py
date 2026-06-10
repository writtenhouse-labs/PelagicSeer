import math
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st


API_BASE_URL = os.getenv("PELAGICSEER_API_BASE_URL", "http://127.0.0.1:8000")
API_TIMEOUT_SECONDS = int(os.getenv("PELAGICSEER_API_TIMEOUT_SECONDS", "300"))
ASSET_PATH = Path(__file__).resolve().parents[1] / "assets" / "YellowfinTuna.png"

WORLD_VIEW_STATE = {"latitude": 12.0, "longitude": -20.0, "zoom": 0.75}


st.set_page_config(page_title="Multi-Source Data Mapper", page_icon=str(ASSET_PATH), layout="wide")

_, logo_column, _ = st.columns([1, 1, 1])
with logo_column:
    st.image(str(ASSET_PATH), width=160)

st.title("Multi-Source Data Mapper")

default_end_date = date.today()
default_start_date = default_end_date - timedelta(days=365)

controls = st.columns([1, 2, 1, 1, 1])
with controls[0]:
    search_rank = st.selectbox("Search by", ["Species", "Genus", "Family"])
with controls[1]:
    species = st.text_input("Name", value="yellowfin tuna")
with controls[2]:
    startdate = st.date_input("Start date", value=default_start_date)
with controls[3]:
    enddate = st.date_input("End date", value=default_end_date)
with controls[4]:
    sample_size = st.number_input("Record sample", min_value=100, max_value=5000, value=1000, step=100)

submitted = st.button("Search data banks", type="primary")

if submitted:
    if startdate > enddate:
        st.error("Start date cannot be after end date.")
    else:
        try:
            response = requests.get(
                f"{API_BASE_URL}/obis/ocean-map",
                params={
                    "species": species,
                    "search_rank": search_rank,
                    "size": sample_size,
                    "startdate": startdate.isoformat(),
                    "enddate": enddate.isoformat(),
                },
                timeout=API_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            st.error(f"Could not search the data banks: {exc}")
        else:
            st.session_state["source_bank_map_result"] = response.json()
            st.session_state["source_bank_map_query"] = {
                "search_rank": search_rank,
                "species": species,
                "sample_size": sample_size,
                "startdate": startdate,
                "enddate": enddate,
            }

body = st.session_state.get("source_bank_map_result")
query = st.session_state.get("source_bank_map_query")
current_query = {
    "search_rank": search_rank,
    "species": species,
    "sample_size": sample_size,
    "startdate": startdate,
    "enddate": enddate,
}

if body and query == current_query:
    points = body.get("points", [])
    display_name = body.get("common_name") or body.get("scientificname")
    if body.get("search_rank") in {"Genus", "Family"}:
        display_name = f"{display_name} ({body['search_rank']})"
    st.subheader(f"Showing {body.get('search_area')} results for {display_name}")

    metrics = st.columns(4)
    metrics[0].metric("Source records", body.get("total", 0))
    metrics[1].metric("Mapped cells", body.get("point_count", 0))
    metrics[2].metric("Sampled records", body.get("returned", 0))
    year_range = body.get("year_range")
    metrics[3].metric(
        "Years",
        f"{year_range['min']}-{year_range['max']}" if year_range else "Unavailable",
    )
    date_range = body.get("date_range")
    if date_range:
        st.caption(f"Data banks date filter: {date_range['start']} through {date_range['end']}")

    if not points:
        st.info("No mapped source records were returned for that date range and species.")
    else:
        df = pd.DataFrame(points)
        df["log_occurrences"] = df["occurrences"].apply(lambda value: math.log10(value + 1))

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[longitude, latitude]",
            get_radius="radius_m",
            get_fill_color="[9, 96, 143, 130]",
            get_line_color="[3, 37, 65, 220]",
            line_width_min_pixels=1,
            pickable=True,
            stroked=True,
            filled=True,
        )
        view_state = pdk.ViewState(**WORLD_VIEW_STATE, pitch=0, bearing=0)
        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            tooltip={
                "html": (
                    "<b>{scientific_name}</b><br/>"
                    "Occurrences: {occurrences}<br/>"
                    "Lat/Lon: {latitude}, {longitude}"
                ),
                "style": {"fontFamily": "Arial", "fontSize": "12px"},
            },
        )
        st.pydeck_chart(deck, use_container_width=True)
        st.caption(
            "Point size represents occurrence count aggregated to 0.1-degree cells. "
            "Source records show reported occurrences, not fishing catch."
        )
elif body:
    st.info("Search the source banks again to refresh the map for the selected species, dates, or sample size.")
