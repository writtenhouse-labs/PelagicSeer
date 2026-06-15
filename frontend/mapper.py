import math
import os
from datetime import date, timedelta

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st


DEFAULT_API_BASE_URL = "https://pelagicseer-api-542566523617.us-central1.run.app"
API_BASE_URL = os.getenv("PELAGICSEER_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
API_TIMEOUT_SECONDS = int(os.getenv("PELAGICSEER_API_TIMEOUT_SECONDS", "300"))
FAO_TIMEOUT_SECONDS = int(os.getenv("PELAGICSEER_FAO_TIMEOUT_SECONDS", "120"))
WORLD_VIEW_STATE = {"latitude": 12.0, "longitude": -20.0, "zoom": 0.75}


def render_mapper() -> None:
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
        sample_size = st.number_input(
            "Record sample", min_value=100, max_value=5000, value=1000, step=100
        )

    submitted = st.button("Search data banks", type="primary")
    if submitted:
        if startdate > enddate:
            st.error("Start date cannot be after end date.")
        else:
            _run_source_bank_search(search_rank, species, sample_size, startdate, enddate)

    body = st.session_state.get("source_bank_map_result")
    if body:
        _render_combined_map(
            body,
            st.session_state.get("source_bank_fao_result"),
            st.session_state.get("source_bank_fao_error"),
        )


def _run_source_bank_search(search_rank, species, sample_size, startdate, enddate) -> None:
    map_body = None
    fao_body = None
    fao_error = None
    try:
        with st.spinner("Searching live data banks..."):
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
        map_body = response.json()
    except requests.RequestException as exc:
        st.error(f"Could not search the data banks: {exc}")
        st.caption(f"API endpoint: {API_BASE_URL}")

    if map_body is not None:
        try:
            with st.spinner("Checking FAO FishStat context..."):
                fao_response = requests.get(
                    f"{API_BASE_URL}/fao/fishstat/species-summary",
                    params={
                        "species": species,
                        "scientific_name": map_body.get("scientificname"),
                        "dataset": "global_production",
                        "limit": 10,
                    },
                    timeout=FAO_TIMEOUT_SECONDS,
                )
            fao_response.raise_for_status()
            fao_body = fao_response.json()
        except requests.RequestException as exc:
            fao_error = str(exc)

    if map_body is not None:
        st.session_state["source_bank_map_result"] = map_body
        st.session_state["source_bank_fao_result"] = fao_body
        st.session_state["source_bank_fao_error"] = fao_error


def _render_combined_map(body, fao_result, fao_error) -> None:
    points = body.get("points", [])
    display_name = body.get("common_name") or body.get("scientificname")
    if body.get("search_rank") in {"Genus", "Family"}:
        display_name = f"{display_name} ({body['search_rank']})"
    st.subheader(f"Showing {body.get('search_area')} results for {display_name}")

    fao_points = (fao_result or {}).get("map_points", [])
    metrics = st.columns(6)
    metrics[0].metric("Source records", body.get("total", 0))
    metrics[1].metric("Mapped cells", body.get("point_count", 0))
    metrics[2].metric("Sampled records", body.get("returned", 0))
    year_range = body.get("year_range")
    metrics[3].metric(
        "Years",
        f"{year_range['min']}-{year_range['max']}" if year_range else "Unavailable",
    )
    metrics[4].metric("FAO areas", len(fao_points))
    metrics[5].metric("FishStat rows", (fao_result or {}).get("record_count", 0))
    date_range = body.get("date_range")
    if date_range:
        st.caption(f"Data banks date filter: {date_range['start']} through {date_range['end']}")

    layers = _obis_layers(points) + _fao_layers(fao_points)
    if layers:
        st.pydeck_chart(
            pdk.Deck(
                layers=layers,
                initial_view_state=pdk.ViewState(**WORLD_VIEW_STATE, pitch=0, bearing=0),
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                tooltip={
                    "html": (
                        "<b>{source_label}</b><br/>"
                        "{tooltip_title}<br/>"
                        "{tooltip_detail}<br/>"
                        "{tooltip_extra}"
                    ),
                    "style": {"fontFamily": "Arial", "fontSize": "12px"},
                },
            ),
            use_container_width=True,
        )
        st.caption(
            "Blue points are OBIS occurrence records aggregated to 0.1-degree cells. "
            "Orange circles are FAO FishStat production/capture totals by FAO major fishing area."
        )
    else:
        st.info("No OBIS or FAO map records were returned for that query.")

    if not points:
        st.info("No mapped OBIS source records were returned for that date range and species.")
    if fao_error:
        st.info(f"FAO FishStat context was unavailable: {fao_error}")
    elif fao_result and not fao_result.get("available"):
        detail = fao_result.get("detail")
        st.info(detail or "No FAO FishStat production/capture rows were returned for this query.")

    records = (fao_result or {}).get("records", [])
    if records:
        with st.expander("FAO FishStat rows"):
            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)


def _obis_layers(points):
    if not points:
        return []
    obis_df = pd.DataFrame(points)
    obis_df["source_label"] = "OBIS occurrence"
    obis_df["tooltip_title"] = obis_df["scientific_name"]
    obis_df["tooltip_detail"] = obis_df["occurrences"].apply(
        lambda value: f"{value} occurrence records"
    )
    obis_df["tooltip_extra"] = obis_df.apply(
        lambda row: f"Lat/Lon: {row['latitude']}, {row['longitude']}", axis=1
    )
    obis_df["log_occurrences"] = obis_df["occurrences"].apply(lambda value: math.log10(value + 1))
    return [
        pdk.Layer(
            "ScatterplotLayer",
            data=obis_df,
            get_position="[longitude, latitude]",
            get_radius="radius_m",
            get_fill_color="[9, 96, 143, 130]",
            get_line_color="[3, 37, 65, 220]",
            line_width_min_pixels=1,
            pickable=True,
            stroked=True,
            filled=True,
        )
    ]


def _fao_layers(fao_points):
    if not fao_points:
        return []
    fao_df = pd.DataFrame(fao_points)
    fao_df["source_label"] = "FAO FishStat area"
    fao_df["tooltip_title"] = fao_df["area_name"]
    fao_df["tooltip_detail"] = fao_df.apply(
        lambda row: f"{row['total_value']:g} {row.get('measure') or ''}".strip(), axis=1
    )
    fao_df["tooltip_extra"] = fao_df.apply(
        lambda row: (
            f"Area {row['area']} - {row['records']} rows - "
            f"latest {row.get('latest_year') or 'n/a'}"
        ),
        axis=1,
    )
    return [
        pdk.Layer(
            "ScatterplotLayer",
            data=fao_df,
            get_position="[longitude, latitude]",
            get_radius="radius_m",
            get_fill_color="[232, 132, 35, 95]",
            get_line_color="[126, 67, 19, 210]",
            line_width_min_pixels=2,
            pickable=True,
            stroked=True,
            filled=True,
        )
    ]
