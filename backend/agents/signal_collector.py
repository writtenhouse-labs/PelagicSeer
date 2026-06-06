"""Gathers biological and fishing-activity signals for a location.

This is the deterministic SpeciesContextAgent from docs/noaa_data_sources.md
plus a fishing-activity signal. Given a target species and a lat/lon it asks:

- OBIS: has this species actually been observed near here, and at what depths?
- GFW: how much commercial fishing effort is here, and is this month in season?

Like the environment collector, each source is fetched independently and any
failure (including a missing GFW token) is swallowed per-source, so /advice can
fold in whatever signals are available and flag the rest as unavailable.
"""

from datetime import date
from typing import Any

import httpx

from connectors.gfw import get_fishing_effort
from connectors.obis import get_species_occurrences

# Curated common-name -> scientific-name map for popular targets. Falls back to
# the raw input when unmatched (the user may already type a scientific name).
# Genus-level entries (e.g. "Thunnus") intentionally match a broad group.
COMMON_TO_SCIENTIFIC = {
    "tuna": "Thunnus",
    "yellowfin": "Thunnus albacares",
    "yellowfin tuna": "Thunnus albacares",
    "bluefin": "Thunnus thynnus",
    "bluefin tuna": "Thunnus thynnus",
    "albacore": "Thunnus alalunga",
    "bigeye tuna": "Thunnus obesus",
    "yellowtail": "Seriola lalandi",
    "mahi": "Coryphaena hippurus",
    "mahi-mahi": "Coryphaena hippurus",
    "dorado": "Coryphaena hippurus",
    "wahoo": "Acanthocybium solandri",
    "marlin": "Makaira nigricans",
    "striped marlin": "Kajikia audax",
    "swordfish": "Xiphias gladius",
    "halibut": "Hippoglossus stenolepis",
    "california halibut": "Paralichthys californicus",
    "rockfish": "Sebastes",
    "lingcod": "Ophiodon elongatus",
    "salmon": "Oncorhynchus",
    "chinook": "Oncorhynchus tshawytscha",
    "coho": "Oncorhynchus kisutch",
    "mackerel": "Scomber",
    "bonito": "Sarda",
    "barracuda": "Sphyraena",
    "white seabass": "Atractoscion nobilis",
    "calico bass": "Paralabrax clathratus",
    "kelp bass": "Paralabrax clathratus",
    "cod": "Gadus morhua",
}

# Total apparent fishing hours (over the year window) at or above which we treat
# the area as notably active.
EFFORT_NOTABLE_HOURS = 50.0


def resolve_scientific_name(species: str) -> tuple[str, bool]:
    """Map a common name to a scientific name. Returns (name, resolved)."""
    key = species.strip().lower()
    if key in COMMON_TO_SCIENTIFIC:
        return COMMON_TO_SCIENTIFIC[key], True
    return species.strip(), False


def collect_signals(
    species: str,
    latitude: float,
    longitude: float,
    today: date | None = None,
) -> dict[str, Any]:
    """Gather species-presence (OBIS) and fishing-activity (GFW) signals."""
    scientific_name, name_resolved = resolve_scientific_name(species)
    sources: list[dict[str, Any]] = []

    species_presence: dict[str, Any] = {"available": False}
    try:
        occ = get_species_occurrences(scientific_name, latitude, longitude, buffer_deg=2.0)
        species_presence = {
            "available": True,
            "scientific_name": scientific_name,
            "total": occ.get("total", 0),
            "returned": occ.get("returned", 0),
            "depth_range_m": occ.get("depth_range_m"),
            "year_range": occ.get("year_range"),
        }
        sources.append({"id": "obis", "status": "ok", "total": occ.get("total", 0)})
    except (httpx.HTTPError, ValueError) as exc:
        sources.append({"id": "obis", "status": "error", "detail": str(exc)})

    fishing_activity: dict[str, Any] = {"available": False}
    try:
        # A full year gives a seasonality curve for the in-season check.
        effort = get_fishing_effort(latitude, longitude, days=365, today=today)
        by_month = effort.get("by_month", {})
        now = today or date.today()
        current_key = now.strftime("%Y-%m")

        # The current calendar month is incomplete, so exclude it from the
        # seasonality baseline (otherwise early in a month it always looks dead).
        baseline = {k: v for k, v in by_month.items() if k != current_key}
        peak_month = max(baseline, key=baseline.get) if baseline else None
        peak_hours = baseline.get(peak_month, 0.0) if peak_month else 0.0
        # Historical effort for THIS month-of-year (e.g. last year's same month).
        moy_suffix = now.strftime("-%m")
        same_moy = [v for k, v in baseline.items() if k.endswith(moy_suffix)]
        historical_month_hours = max(same_moy) if same_moy else 0.0

        fishing_activity = {
            "available": True,
            "total_hours": effort.get("total_apparent_fishing_hours", 0.0),
            "peak_month": peak_month,
            "current_month": current_key,
            "current_month_hours": round(by_month.get(current_key, 0.0), 1),
            "historical_month_hours": round(historical_month_hours, 1),
            # "in season" = this month-of-year is historically at least half the
            # busiest month's effort.
            "in_season": peak_hours > 0 and historical_month_hours >= 0.5 * peak_hours,
        }
        sources.append({"id": "global-fishing-watch", "status": "ok"})
    except (httpx.HTTPError, ValueError) as exc:
        # ValueError also covers a missing GFW_API_TOKEN.
        sources.append({"id": "global-fishing-watch", "status": "error", "detail": str(exc)})

    return {
        "species_input": species,
        "scientific_name": scientific_name,
        "name_resolved": name_resolved,
        "species_presence": species_presence,
        "fishing_activity": fishing_activity,
        "sources": sources,
    }
