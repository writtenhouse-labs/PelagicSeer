import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests
import streamlit as st

from mapper import render_mapper
from ui_status import install_swimming_fish_status


DEFAULT_API_BASE_URL = "https://pelagicseer-api-542566523617.us-central1.run.app"
API_BASE_URL = os.getenv("PELAGICSEER_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
ADVICE_TIMEOUT_SECONDS = int(
    os.getenv(
        "PELAGICSEER_ADVICE_TIMEOUT_SECONDS",
        os.getenv("PELAGICSEER_API_TIMEOUT_SECONDS", "110"),
    )
)
ICON_PATH = Path(__file__).parent / "assets" / "BlueFinTuna.png"

_MODE_HELP = {
    "live": "Window includes today - using the freshest live observations.",
    "historical": "Past window - conditions reflect archived observations near the window end.",
    "forecast": "Future window - conditions are a latest-observation proxy; confidence is capped.",
}

FIELD_LABELS = {
    "sea_surface_temp_f": "Sea surface temperature",
    "wind_speed_kts": "Wind speed",
    "wave_height_ft": "Wave height",
    "barometric_pressure_mb": "Barometric pressure",
    "current_speed_kts": "Current speed",
    "water_level_ft": "Water level",
    "chlorophyll_mg_m3": "Chlorophyll",
    "salinity_psu": "Salinity",
}

FIELD_UNITS = {
    "sea_surface_temp_f": "deg F",
    "wind_speed_kts": "kt",
    "wave_height_ft": "ft",
    "barometric_pressure_mb": "mb",
    "current_speed_kts": "kt",
    "water_level_ft": "ft",
    "chlorophyll_mg_m3": "mg/m3",
    "salinity_psu": "psu",
}

SOURCE_LABELS = {
    "noaa-erddap": "NOAA ERDDAP satellite SST",
    "noaa-erddap-chla": "NOAA ERDDAP chlorophyll",
    "noaa-ndbc": "NOAA NDBC buoy station",
    "noaa-coops:currents": "NOAA CO-OPS currents",
    "noaa-coops:water_level": "NOAA CO-OPS water level",
    "noaa-coops:salinity": "NOAA CO-OPS salinity",
    "obis": "OBIS species occurrence",
    "global-fishing-watch": "Global Fishing Watch",
    "fao-fishstat": "FAO FishStat",
    "noaa-ncei-etopo": "NOAA NCEI bathymetry",
    "noaa-mrip": "NOAA MRIP recreational prior",
    "noaa-dismap": "NOAA DisMAP survey distribution",
}


def install_advice_styles() -> None:
    st.markdown(
        """
<style>
.data-report-shell {
    border: 1px solid #d6e5dc;
    border-radius: 8px;
    background: #fbfdfb;
    padding: 1rem 1.1rem;
    margin-bottom: 0.8rem;
}
.data-report-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1f5134;
    margin-bottom: 0.15rem;
}
.data-report-caption {
    color: #66736b;
    font-size: 0.9rem;
    margin-bottom: 0.75rem;
}
div[data-testid="stMetric"] {
    background: #f7faf8;
    border: 1px solid #e2ebe5;
    border-radius: 8px;
    padding: 0.65rem 0.75rem;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _format_value(value: Any, field: str | None = None) -> str:
    if value is None:
        return "not returned"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        text = f"{value:.2f}".rstrip("0").rstrip(".")
    else:
        text = str(value)
    unit = FIELD_UNITS.get(field or "")
    return f"{text} {unit}" if unit else text


def _source_by_id(sources: list[dict[str, Any]], source_id: str) -> dict[str, Any]:
    return next((source for source in sources if source.get("id") == source_id), {})


def _latest_date(*values: Any) -> str | None:
    for value in values:
        if value:
            return str(value)
    return None


def _field_list(fields: dict[str, Any]) -> str:
    lines = [f"- **{label}:** {value}" for label, value in fields.items() if value is not None]
    return "\n".join(lines) if lines else "- No data fields were returned."


def _render_interface_card(
    name: str,
    status: str,
    returned: dict[str, Any] | None = None,
    missing: list[str] | None = None,
    last_date: str | None = None,
    detail: str | None = None,
) -> None:
    returned = returned or {}
    missing = missing or []
    if status == "ok":
        heading = f"{name} data interface returned:"
    elif status in {"partial", "skipped", "unavailable"}:
        heading = f"{name} data interface returned partial information:"
    else:
        heading = f"{name} data interface did not return information:"

    st.markdown(f"**{heading}**")
    st.markdown(_field_list(returned))
    if missing:
        date_text = last_date or "no last capture date was returned by this interface"
        st.caption(f"Missing: {', '.join(missing)}. Last known capture: {date_text}.")
    elif last_date:
        st.caption(f"Latest data timestamp: {last_date}.")
    if detail:
        st.caption(detail)
    st.divider()


def _render_placeholder_report() -> None:
    st.markdown(
        """
<div class="data-report-shell">
  <div class="data-report-title">Data interface report</div>
  <div class="data-report-caption">Run advice to see each data source, returned fields, missing elements, and latest observation dates.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    for label in (
        "NOAA live conditions",
        "Species and fishing signals",
        "Bathymetry and survey context",
        "Recommendation build",
    ):
        st.caption(f"Waiting for {label.lower()}...")


def render_interface_report(body: dict[str, Any]) -> None:
    conditions = body.get("conditions", {})
    condition_sources = conditions.get("sources", [])
    provenance = conditions.get("provenance", {})
    signals = body.get("signals", {})
    signal_sources = signals.get("sources", [])
    area_species = body.get("area_species", {})
    survey = body.get("survey_distribution", {})

    st.markdown(
        """
<div class="data-report-shell">
  <div class="data-report-title">Data interface report</div>
  <div class="data-report-caption">Readable source-by-source output for this fishing spot.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    erddap_sst = _source_by_id(condition_sources, "noaa-erddap")
    erddap_chla = _source_by_id(condition_sources, "noaa-erddap-chla")
    _render_interface_card(
        SOURCE_LABELS["noaa-erddap"],
        "ok" if erddap_sst.get("status") == "ok" else "error",
        {
            "Sea surface temperature": _format_value(conditions.get("sea_surface_temp_f"), "sea_surface_temp_f")
            if provenance.get("sea_surface_temp_f") == "noaa-erddap"
            else None,
            "Dataset": erddap_sst.get("dataset"),
        },
        [] if erddap_sst.get("status") == "ok" else ["sea surface temperature"],
        erddap_sst.get("observed_time") or conditions.get("target_date"),
        erddap_sst.get("detail"),
    )
    _render_interface_card(
        SOURCE_LABELS["noaa-erddap-chla"],
        "ok" if erddap_chla.get("status") == "ok" else "error",
        {
            "Chlorophyll": _format_value(conditions.get("chlorophyll_mg_m3"), "chlorophyll_mg_m3")
            if provenance.get("chlorophyll_mg_m3") == "noaa-erddap"
            else None,
            "Dataset": erddap_chla.get("dataset"),
        },
        [] if erddap_chla.get("status") == "ok" else ["chlorophyll"],
        erddap_chla.get("observed_time") or conditions.get("target_date"),
        erddap_chla.get("detail"),
    )

    ndbc = _source_by_id(condition_sources, "noaa-ndbc")
    ndbc_fields = {
        FIELD_LABELS[field]: _format_value(conditions.get(field), field)
        for field in ("sea_surface_temp_f", "wind_speed_kts", "wave_height_ft", "barometric_pressure_mb")
        if provenance.get(field) == "noaa-ndbc"
    }
    ndbc_missing = [
        FIELD_LABELS[field]
        for field in ("sea_surface_temp_f", "wind_speed_kts", "wave_height_ft", "barometric_pressure_mb")
        if provenance.get(field) != "noaa-ndbc"
    ]
    _render_interface_card(
        SOURCE_LABELS["noaa-ndbc"],
        "partial" if ndbc.get("status") == "ok" and ndbc_missing else ndbc.get("status", "error"),
        {
            **ndbc_fields,
            "Station": ndbc.get("station_name") or ndbc.get("station"),
            "Distance": f"{ndbc.get('distance_nm')} nm" if ndbc.get("distance_nm") is not None else None,
        },
        ndbc_missing,
        ndbc.get("observed_time"),
        ndbc.get("detail"),
    )

    for source_id, field in (
        ("noaa-coops:currents", "current_speed_kts"),
        ("noaa-coops:water_level", "water_level_ft"),
        ("noaa-coops:salinity", "salinity_psu"),
    ):
        source = _source_by_id(condition_sources, source_id)
        returned = {"Station": source.get("station_name") or source.get("station")}
        if provenance.get(field) == "noaa-coops":
            returned[FIELD_LABELS[field]] = _format_value(conditions.get(field), field)
        _render_interface_card(
            SOURCE_LABELS[source_id],
            "ok" if source.get("status") == "ok" else "error",
            returned,
            [] if source.get("status") == "ok" else [FIELD_LABELS[field]],
            source.get("observed_time") or conditions.get("target_date"),
            source.get("detail"),
        )

    presence = signals.get("species_presence", {})
    obis_source = _source_by_id(signal_sources, "obis")
    date_range = presence.get("date_range") or area_species.get("date_range") or {}
    _render_interface_card(
        SOURCE_LABELS["obis"],
        "ok" if presence.get("available") else "error",
        {
            "Scientific name": presence.get("scientific_name"),
            "Records near spot": presence.get("total"),
            "Returned rows": presence.get("returned"),
            "Search window": f"{date_range.get('start')} to {date_range.get('end')}" if date_range else None,
        },
        [] if presence.get("available") else ["species occurrence records"],
        _latest_date(date_range.get("end"), conditions.get("target_date")),
        obis_source.get("detail"),
    )

    fishing = signals.get("fishing_activity", {})
    gfw_source = _source_by_id(signal_sources, "global-fishing-watch")
    _render_interface_card(
        SOURCE_LABELS["global-fishing-watch"],
        "ok" if fishing.get("available") else "error",
        {
            "Recent fishing effort": _format_value(fishing.get("recent_hours")),
            "One-year fishing effort": _format_value(fishing.get("total_hours")),
            "Peak month": fishing.get("peak_month"),
            "In season": _format_value(fishing.get("in_season")),
        },
        [] if fishing.get("available") else ["commercial fishing effort"],
        fishing.get("current_month") or conditions.get("target_date"),
        gfw_source.get("detail"),
    )

    fao = signals.get("fao_fishstat_context", {})
    fao_source = _source_by_id(signal_sources, "fao-fishstat")
    fao_year_range = fao.get("year_range") or {}
    _render_interface_card(
        SOURCE_LABELS["fao-fishstat"],
        "ok" if fao.get("available") else fao_source.get("status", "error"),
        {
            "Record count": fao.get("record_count"),
            "Returned rows": fao.get("returned"),
            "Year range": f"{fao_year_range.get('min')} to {fao_year_range.get('max')}"
            if fao_year_range
            else None,
        },
        [] if fao.get("available") else ["global production/capture context"],
        fao_year_range.get("max"),
        fao.get("detail") or fao_source.get("detail"),
    )

    bathy = signals.get("bathymetry_context", {})
    _render_interface_card(
        SOURCE_LABELS["noaa-ncei-etopo"],
        "ok" if bathy.get("available") else "error",
        {
            "Depth": f"{bathy.get('depth_ft')} ft" if bathy.get("depth_ft") is not None else None,
            "Nearby relief": f"{bathy.get('nearby_relief_ft')} ft" if bathy.get("nearby_relief_ft") is not None else None,
            "Structure": bathy.get("structure"),
            "Dataset": bathy.get("dataset"),
        },
        [] if bathy.get("available") else ["bathymetry"],
        "ETOPO 2022 model",
        bathy.get("detail") or bathy.get("notes"),
    )

    mrip = signals.get("mrip_recreational_prior", {})
    mrip_source = _source_by_id(signal_sources, "noaa-mrip")
    region = mrip.get("region") if isinstance(mrip.get("region"), dict) else {}
    _render_interface_card(
        SOURCE_LABELS["noaa-mrip"],
        "ok" if mrip.get("available") else mrip_source.get("status", "error"),
        {
            "Target month": mrip.get("target_month"),
            "In season": _format_value(mrip.get("in_season")) if mrip.get("in_season") is not None else None,
            "Region": region.get("label"),
        },
        [] if mrip.get("available") else ["recreational prior"],
        None,
        mrip.get("detail") or mrip_source.get("detail"),
    )

    survey_year_range = survey.get("year_range") or {}
    _render_interface_card(
        SOURCE_LABELS["noaa-dismap"],
        "ok" if survey.get("available") else "error",
        {
            "Survey region": survey.get("region_name") or survey.get("region"),
            "Returned samples": survey.get("returned"),
            "Present samples": survey.get("present_samples"),
            "WTCPUE": survey.get("wtcpue"),
            "Year range": f"{survey_year_range.get('min')} to {survey_year_range.get('max')}"
            if survey_year_range
            else None,
        },
        [] if survey.get("available") and survey.get("returned") else ["survey distribution samples"],
        survey_year_range.get("max") or conditions.get("target_date"),
        survey.get("detail"),
    )


st.set_page_config(page_title="PelagicSeer", page_icon=str(ICON_PATH))
install_swimming_fish_status(ICON_PATH)
install_advice_styles()

_, logo_column, _ = st.columns([1, 1, 1])
with logo_column:
    st.image(str(ICON_PATH), width=160)
st.title("PelagicSeer")

view = st.radio(
    "View",
    ["Fishing advice", "Multi-Source Data Mapper"],
    horizontal=True,
    label_visibility="collapsed",
)

if view == "Multi-Source Data Mapper":
    render_mapper()
    st.stop()

input_column, report_column = st.columns([0.82, 1.18], gap="large")

with input_column:
    with st.form("advice-form"):
        city = st.text_input("City", value="San Diego")
        state = st.text_input("State", value="CA")
        species = st.text_input("Species", value="tuna")
        target_depth_ft = st.number_input("Target depth (ft)", min_value=0, value=20)
        date_columns = st.columns(2)
        with date_columns[0]:
            start_date = st.date_input("Start date", value=date.today())
        with date_columns[1]:
            end_date = st.date_input("End date", value=date.today() + timedelta(days=2))
        submitted = st.form_submit_button("Get advice")

with report_column:
    report_placeholder = st.empty()
    if not submitted:
        with report_placeholder.container():
            _render_placeholder_report()

if submitted:
    if start_date > end_date:
        with report_column:
            report_placeholder.error("Start date cannot be after end date.")
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
        with report_column:
            with report_placeholder.container():
                status = st.status("Gathering data interfaces...", expanded=True)
                status.write("Resolving the fishing spot and nearest working marine station.")
                status.write("Collecting NOAA live conditions.")
                status.write("Collecting species, fishing activity, and seafloor context.")
                status.write("Building the recommendation and formatting the interface report.")
        response = requests.post(
            f"{API_BASE_URL}/advice",
            json=payload,
            timeout=ADVICE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        with report_column:
            report_placeholder.error(f"Could not reach PelagicSeer API: {exc}")
            st.caption(f"API endpoint: {API_BASE_URL}")
    except ValueError as exc:
        with report_column:
            report_placeholder.error(f"PelagicSeer API returned an unreadable response: {exc}")
            st.caption(f"API endpoint: {API_BASE_URL}")
    else:
        body = response.json()
        recommendation = body["recommendation"]
        location = body["location"]

        with report_column:
            with report_placeholder.container():
                render_interface_report(body)

        with input_column:
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

            area_species = body.get("area_species", {})
            if area_species.get("available") and area_species.get("species"):
                st.write(f"Species recorded in this area ({area_species.get('total_species', 0)} total)")
                for entry in area_species["species"]:
                    label = entry.get("common_name") or entry.get("scientific_name")
                    detail = f" - {entry['scientific_name']}" if entry.get("common_name") else ""
                    st.write(f"- {label}{detail} - {entry.get('records', 0)} records")
            else:
                st.caption("No area species list was available for this window.")

            st.write("Reasons")
            for reason in recommendation["reasons"]:
                st.write(f"- {reason}")
