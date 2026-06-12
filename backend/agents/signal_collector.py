"""Gathers biological and fishing-activity signals for a location.

This is the deterministic SpeciesContextAgent from docs/noaa_data_sources.md
plus a fishing-activity signal. Given a target species and a lat/lon it asks:

- OBIS: has this species actually been observed near here, and at what depths?
- GFW: how much commercial fishing effort is here, and is this month in season?
- FAO FishStat: does this species appear in global production/capture records?
- Bathymetry: is the point near depth/structure that can concentrate fish?
- MRIP: is this species/region/month historically plausible for recreational catch?

Like the environment collector, each source is fetched independently and any
failure (including a missing GFW token) is swallowed per-source, so /advice can
fold in whatever signals are available and flag the rest as unavailable.
"""

from datetime import date
from typing import Any

import httpx

from agents.temporal_router import TemporalPlan
from connectors.bathymetry import get_bathymetry_context
from connectors.fao import get_fishstat_species_summary
from connectors.gfw import get_fishing_effort
from connectors.mrip import get_mrip_recreational_prior
from connectors.obis import get_area_species, get_species_occurrences

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
    "atlantic herring": "Clupea harengus",
}

# Apparent fishing hours at or above which we treat the area as notably active.
EFFORT_NOTABLE_HOURS = 50.0
RECENT_EFFORT_NOTABLE_HOURS = 10.0


def resolve_scientific_name(species: str) -> tuple[str, bool]:
    """Map a common name to a scientific name. Returns (name, resolved)."""
    key = species.strip().lower()
    if key in COMMON_TO_SCIENTIFIC:
        return COMMON_TO_SCIENTIFIC[key], True
    return species.strip(), False


def resolve_common_name(scientific_name: str) -> str | None:
    """Map a scientific name back to a display-friendly common name."""
    normalized_name = scientific_name.strip().lower()
    matches = [
        common_name
        for common_name, mapped_scientific_name in COMMON_TO_SCIENTIFIC.items()
        if mapped_scientific_name.lower() == normalized_name and common_name != "tuna"
    ]
    return max(matches, key=len).title() if matches else None


def collect_signals(
    species: str,
    latitude: float,
    longitude: float,
    today: date | None = None,
    plan: TemporalPlan | None = None,
) -> dict[str, Any]:
    """Gather species-presence (OBIS) and fishing-activity (GFW) signals.

    When ``plan`` is given, OBIS presence is restricted to the plan's date
    window and the GFW "recent" window matches the plan span anchored at its
    end; otherwise the original today / 30-day behavior is used.
    """
    scientific_name, name_resolved = resolve_scientific_name(species)
    sources: list[dict[str, Any]] = []

    if plan is not None:
        today = plan.end_date
        startdate, enddate = plan.start_date.isoformat(), plan.end_date.isoformat()
        recent_days = plan.days_span
    else:
        startdate = enddate = None
        recent_days = 30

    species_presence: dict[str, Any] = {"available": False}
    try:
        occ_kwargs: dict[str, Any] = {}
        if startdate and enddate:
            occ_kwargs = {"startdate": startdate, "enddate": enddate}
        occ = get_species_occurrences(
            scientific_name, latitude, longitude, buffer_deg=2.0, **occ_kwargs
        )
        species_presence = {
            "available": True,
            "scientific_name": scientific_name,
            "total": occ.get("total", 0),
            "returned": occ.get("returned", 0),
            "depth_range_m": occ.get("depth_range_m"),
            "year_range": occ.get("year_range"),
            "date_range": occ.get("date_range"),
        }
        sources.append({"id": "obis", "status": "ok", "total": occ.get("total", 0)})
    except (httpx.HTTPError, ValueError) as exc:
        sources.append({"id": "obis", "status": "error", "detail": str(exc)})

    fishing_activity: dict[str, Any] = {"available": False}
    target_species_activity: dict[str, Any] = {"available": False}
    try:
        # A short window answers "is this area being fished recently?" while a
        # full year gives a seasonality curve for the in-season check.
        recent_effort = get_fishing_effort(latitude, longitude, days=recent_days, today=today)
        yearly_effort = get_fishing_effort(latitude, longitude, days=365, today=today)
        by_month = yearly_effort.get("by_month", {})
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
            "recent_hours": recent_effort.get("total_apparent_fishing_hours", 0.0),
            "total_hours": yearly_effort.get("total_apparent_fishing_hours", 0.0),
            "peak_month": peak_month,
            "current_month": current_key,
            "current_month_hours": round(by_month.get(current_key, 0.0), 1),
            "historical_month_hours": round(historical_month_hours, 1),
            # "in season" = this month-of-year is historically at least half the
            # busiest month's effort.
            "in_season": peak_hours > 0 and historical_month_hours >= 0.5 * peak_hours,
        }
        if species_presence.get("available"):
            presence_total = species_presence.get("total", 0)
            recent_hours = fishing_activity["recent_hours"]
            likely_recent_target_activity = (
                presence_total > 0 and recent_hours >= RECENT_EFFORT_NOTABLE_HOURS
            )
            target_species_activity = {
                "available": True,
                "likely_recent_target_activity": likely_recent_target_activity,
                "species_occurrences_nearby": presence_total,
                "recent_fishing_hours_nearby": recent_hours,
                "gfw_species_specific": False,
                "basis": "OBIS species presence combined with GFW apparent fishing effort",
            }
        sources.append({"id": "global-fishing-watch", "status": "ok"})
    except (httpx.HTTPError, ValueError) as exc:
        # ValueError also covers a missing GFW_API_TOKEN.
        sources.append({"id": "global-fishing-watch", "status": "error", "detail": str(exc)})

    fao_fishstat_context: dict[str, Any] = {"available": False}
    try:
        fao_fishstat_context = get_fishstat_species_summary(
            species=species,
            scientific_name=scientific_name,
            dataset="global_production",
        )
        sources.append(
            {
                "id": "fao-fishstat",
                "status": "ok",
                "record_count": fao_fishstat_context.get("record_count", 0),
            }
        )
    except (httpx.HTTPError, ValueError) as exc:
        sources.append({"id": "fao-fishstat", "status": "error", "detail": str(exc)})

    bathymetry_context: dict[str, Any] = {"available": False}
    try:
        bathymetry_context = get_bathymetry_context(latitude=latitude, longitude=longitude)
        sources.append(
            {
                "id": "noaa-ncei-etopo",
                "status": "ok",
                "depth_m": bathymetry_context.get("depth_m"),
                "structure": bathymetry_context.get("structure"),
            }
        )
    except (httpx.HTTPError, ValueError) as exc:
        sources.append({"id": "noaa-ncei-etopo", "status": "error", "detail": str(exc)})

    mrip_recreational_prior: dict[str, Any] = {"available": False}
    try:
        mrip_recreational_prior = get_mrip_recreational_prior(
            species=species,
            latitude=latitude,
            longitude=longitude,
            target_date=today,
        )
        sources.append(
            {
                "id": "noaa-mrip",
                "status": "ok" if mrip_recreational_prior.get("available") else "unavailable",
                "region": (mrip_recreational_prior.get("region") or {}).get("id"),
            }
        )
    except ValueError as exc:
        sources.append({"id": "noaa-mrip", "status": "error", "detail": str(exc)})

    return {
        "species_input": species,
        "scientific_name": scientific_name,
        "name_resolved": name_resolved,
        "species_presence": species_presence,
        "fishing_activity": fishing_activity,
        "target_species_activity": target_species_activity,
        "fao_fishstat_context": fao_fishstat_context,
        "bathymetry_context": bathymetry_context,
        "mrip_recreational_prior": mrip_recreational_prior,
        "sources": sources,
    }


def collect_area_species(
    latitude: float,
    longitude: float,
    plan: TemporalPlan | None = None,
    buffer_deg: float = 2.0,
    limit: int = 15,
) -> dict[str, Any]:
    """Discover which species are recorded near a lat/lon (OBIS checklist).

    Answers "what fish are here?" rather than targeting one species. Each
    returned taxon is annotated with a common name when we recognize it.
    Degrades to ``{"available": False, ...}`` if OBIS is unavailable.
    """
    startdate = plan.start_date.isoformat() if plan is not None else None
    enddate = plan.end_date.isoformat() if plan is not None else None
    try:
        result = get_area_species(
            latitude,
            longitude,
            buffer_deg=buffer_deg,
            startdate=startdate,
            enddate=enddate,
            limit=limit,
        )
        for entry in result["species"]:
            entry["common_name"] = resolve_common_name(entry["scientific_name"])
        return {"available": True, **result}
    except (httpx.HTTPError, ValueError) as exc:
        return {"available": False, "detail": str(exc)}
