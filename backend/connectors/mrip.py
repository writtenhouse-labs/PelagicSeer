"""NOAA MRIP recreational catch prior connector.

MRIP public-use data is distributed through query/download products rather
than a small point API. This connector exposes a conservative seasonal prior
and coverage metadata for advice scoring; it does not claim live catch data.
"""

from datetime import date
from typing import Any


MRIP_DOWNLOADS_URL = "https://www.fisheries.noaa.gov/recreational-fishing-data/recreational-fishing-data-downloads"
MRIP_ESTIMATE_DATA_URL = "https://apps-st.fisheries.noaa.gov/st1/recreational/MRIP_Estimate_Data/"
LPS_DATA_URL = "https://apps-st.fisheries.noaa.gov/st1/recreational/LPS_Data/"

MRIP_REGIONS = {
    "atlantic": {
        "label": "Atlantic coast",
        "bounds": {"lat_min": 24.0, "lat_max": 46.0, "lon_min": -82.0, "lon_max": -66.0},
    },
    "gulf": {
        "label": "Gulf coast",
        "bounds": {"lat_min": 24.0, "lat_max": 31.5, "lon_min": -98.5, "lon_max": -81.0},
    },
    "hawaii": {
        "label": "Hawaii",
        "bounds": {"lat_min": 18.0, "lat_max": 23.0, "lon_min": -161.0, "lon_max": -154.0},
    },
    "puerto_rico": {
        "label": "Puerto Rico",
        "bounds": {"lat_min": 17.5, "lat_max": 18.8, "lon_min": -67.5, "lon_max": -65.0},
    },
}

SPECIES_SEASONAL_PRIORS = {
    "tuna": {"months": {6, 7, 8, 9, 10}, "group": "large pelagic"},
    "yellowfin": {"months": {6, 7, 8, 9, 10}, "group": "large pelagic"},
    "yellowfin tuna": {"months": {6, 7, 8, 9, 10}, "group": "large pelagic"},
    "bluefin tuna": {"months": {6, 7, 8, 9, 10, 11}, "group": "large pelagic"},
    "bigeye tuna": {"months": {6, 7, 8, 9, 10}, "group": "large pelagic"},
    "mahi": {"months": {5, 6, 7, 8, 9, 10}, "group": "pelagic"},
    "mahi-mahi": {"months": {5, 6, 7, 8, 9, 10}, "group": "pelagic"},
    "dorado": {"months": {5, 6, 7, 8, 9, 10}, "group": "pelagic"},
    "wahoo": {"months": {5, 6, 7, 8, 9, 10, 11}, "group": "pelagic"},
    "marlin": {"months": {6, 7, 8, 9, 10}, "group": "large pelagic"},
    "striped marlin": {"months": {6, 7, 8, 9, 10}, "group": "large pelagic"},
    "swordfish": {"months": {6, 7, 8, 9, 10, 11}, "group": "large pelagic"},
    "halibut": {"months": {4, 5, 6, 7, 8, 9}, "group": "demersal"},
    "rockfish": {"months": {3, 4, 5, 6, 7, 8, 9, 10}, "group": "demersal"},
    "salmon": {"months": {5, 6, 7, 8, 9}, "group": "anadromous"},
    "mackerel": {"months": {4, 5, 6, 7, 8, 9, 10}, "group": "coastal pelagic"},
}


def _region_for_point(latitude: float, longitude: float) -> dict[str, Any] | None:
    for region_id, region in MRIP_REGIONS.items():
        bounds = region["bounds"]
        if (
            bounds["lat_min"] <= latitude <= bounds["lat_max"]
            and bounds["lon_min"] <= longitude <= bounds["lon_max"]
        ):
            return {"id": region_id, "label": region["label"]}
    return None


def _species_prior(species: str) -> dict[str, Any]:
    key = species.strip().lower()
    if key in SPECIES_SEASONAL_PRIORS:
        return SPECIES_SEASONAL_PRIORS[key]
    for known, prior in SPECIES_SEASONAL_PRIORS.items():
        if known in key or key in known:
            return prior
    return {"months": set(), "group": "unknown"}


def get_mrip_recreational_prior(
    species: str,
    latitude: float,
    longitude: float,
    target_date: date | None = None,
) -> dict[str, Any]:
    """Return an MRIP coverage/seasonality prior for recreational catch."""
    region = _region_for_point(latitude, longitude)
    when = target_date or date.today()
    prior = _species_prior(species)
    seasonal_months = sorted(prior["months"])
    in_season = when.month in prior["months"] if seasonal_months else None

    if region is None:
        return {
            "source": "noaa-mrip",
            "available": False,
            "species": species,
            "latitude": latitude,
            "longitude": longitude,
            "target_month": when.month,
            "detail": "Point is outside the conservative MRIP region coverage used by this connector.",
            "downloads_url": MRIP_DOWNLOADS_URL,
            "estimate_data_url": MRIP_ESTIMATE_DATA_URL,
            "notes": "MRIP is a delayed recreational catch/effort prior, not a live fish-location signal.",
        }

    return {
        "source": "noaa-mrip",
        "available": True,
        "species": species,
        "latitude": latitude,
        "longitude": longitude,
        "region": region,
        "species_group": prior["group"],
        "target_month": when.month,
        "seasonal_months": seasonal_months,
        "in_season": in_season,
        "seasonality_score": 1.0 if in_season else 0.25 if seasonal_months else 0.5,
        "downloads_url": MRIP_DOWNLOADS_URL,
        "estimate_data_url": MRIP_ESTIMATE_DATA_URL,
        "large_pelagics_data_url": LPS_DATA_URL if prior["group"] == "large pelagic" else None,
        "notes": "MRIP estimates are delayed recreational catch/effort context and should be treated as a seasonal prior.",
    }
