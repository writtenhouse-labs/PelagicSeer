from agents.temporal_router import TemporalPlan
from api.schemas import AdviceRequest

# Fields the score depends on. Used to report how complete the input was and
# to derive a confidence level when live sources only provide some of them.
SCORABLE_FIELDS = (
    "wind_speed_kts",
    "wave_height_ft",
    "sea_surface_temp_f",
    "current_speed_kts",
    "barometric_pressure_mb",
)

# Apparent fishing hours (over the GFW year window) at or above which the area
# reads as notably active.
_EFFORT_NOTABLE_HOURS = 50.0
_RECENT_EFFORT_NOTABLE_HOURS = 10.0
_FT_TO_M = 0.3048


def _score_signals(
    request: AdviceRequest,
    signals: dict,
    score: int,
    reasons: list[str],
) -> tuple[int, dict]:
    """Add species-presence and fishing-activity factors to the score.

    Each factor only moves the score when its source provided data; otherwise
    it is reported as unavailable. Returns the new score and a summary of which
    signals were used.
    """
    used: list[str] = []
    missing: list[str] = []
    species_label = signals.get("scientific_name") or request.species

    presence = signals.get("species_presence", {})
    if not presence.get("available"):
        missing.append("species_presence")
        reasons.append("Species occurrence data was unavailable (OBIS).")
    elif presence.get("total", 0) > 0:
        used.append("species_presence")
        score += 10
        reasons.append(
            f"{species_label} has {presence['total']} recorded occurrence(s) near here (OBIS)."
        )
        depth = presence.get("depth_range_m")
        if request.target_depth_ft and depth and depth.get("min") is not None:
            target_m = request.target_depth_ft * _FT_TO_M
            if depth["min"] <= target_m <= depth["max"]:
                score += 5
                reasons.append(
                    "Target depth falls within the observed depth range for this species."
                )
    else:
        used.append("species_presence")
        score -= 5
        reasons.append(
            f"No OBIS records of {species_label} near here; presence is uncertain."
        )

    activity = signals.get("fishing_activity", {})
    if not activity.get("available"):
        missing.append("fishing_activity")
        reasons.append("Fishing-effort data was unavailable (GFW).")
    else:
        recent_hours = activity.get("recent_hours", activity.get("total_hours", 0.0))
        hours = activity.get("total_hours", 0.0)
        if recent_hours >= _RECENT_EFFORT_NOTABLE_HOURS:
            used.append("fishing_activity")
            score += 8
            reasons.append(
                f"Recent commercial fishing effort nearby ({recent_hours:.0f} hrs in the last 30 days) suggests active grounds."
            )
        elif recent_hours > 0:
            used.append("fishing_activity")
            score += 3
            reasons.append(
                f"Some recent commercial fishing effort nearby ({recent_hours:.0f} hrs in the last 30 days)."
            )
        elif hours >= _EFFORT_NOTABLE_HOURS:
            used.append("fishing_activity")
            score += 5
            reasons.append(
                f"Historically high commercial fishing effort nearby ({hours:.0f} hrs over the past year)."
            )
        elif hours > 0:
            used.append("fishing_activity")
            reasons.append(f"Some historical commercial fishing effort nearby ({hours:.0f} hrs over the past year).")
        else:
            used.append("fishing_activity")
            reasons.append("No recent commercial fishing effort recorded nearby (GFW).")
        if activity.get("in_season"):
            score += 5
            reasons.append("This month is historically active for fishing at this location.")

    target_activity = signals.get("target_species_activity", {})
    if not target_activity.get("available"):
        missing.append("target_species_activity")
    elif target_activity.get("likely_recent_target_activity"):
        used.append("target_species_activity")
        score += 7
        reasons.append(
            f"Recent GFW fishing effort overlaps nearby {species_label} occurrence records; GFW effort is not species-specific catch data."
        )
    elif target_activity.get("species_occurrences_nearby", 0) > 0:
        used.append("target_species_activity")
        reasons.append(
            f"{species_label} has nearby occurrence records, but GFW does not show notable recent fishing effort in this area."
        )

    summary = {
        "used": used,
        "missing": missing,
        "species_name_resolved": signals.get("name_resolved"),
    }
    return score, summary


def build_fishing_advice(
    request: AdviceRequest,
    conditions: dict,
    signals: dict | None = None,
    plan: TemporalPlan | None = None,
) -> dict:
    """Rule-based advisor placeholder for the future Claude/LangChain agent.

    Tolerates missing condition fields: any factor without data is skipped
    (neither helping nor hurting the score) and reported, and the result
    carries a confidence level reflecting how much real data was available.

    When ``signals`` (species presence + fishing activity) are supplied, they
    contribute additional scored factors, each likewise skipped if unavailable.

    When ``plan`` is supplied, the temporal mode is reported and a future-dated
    (forecast) window caps confidence, since conditions are then only a nowcast
    proxy rather than real observations for the requested days.
    """
    score = 50
    reasons: list[str] = []

    wind_speed = conditions.get("wind_speed_kts")
    wave_height = conditions.get("wave_height_ft")
    sea_temp = conditions.get("sea_surface_temp_f")
    current_speed = conditions.get("current_speed_kts")
    pressure = conditions.get("barometric_pressure_mb")

    if wind_speed is None:
        reasons.append("Wind data was unavailable, so it did not factor into the score.")
    elif wind_speed <= 12:
        score += 15
        reasons.append("Light wind should make fishing conditions easier.")
    else:
        score -= 20
        reasons.append("Stronger wind may make boat handling and casting harder.")

    if wave_height is None:
        reasons.append("Wave data was unavailable, so it did not factor into the score.")
    elif wave_height <= 3:
        score += 15
        reasons.append("Low seas are favorable for safe, comfortable fishing.")
    else:
        score -= 20
        reasons.append("Higher seas reduce comfort and safety.")

    if sea_temp is None:
        reasons.append("Water temperature was unavailable, so it did not factor into the score.")
    elif 68 <= sea_temp <= 78:
        score += 15
        reasons.append("Water temperature is in a productive range for many pelagic species.")
    else:
        score -= 10
        reasons.append("Water temperature is outside the preferred general range.")

    if current_speed is None:
        reasons.append("Current data was unavailable, so it did not factor into the score.")
    elif 0.4 <= current_speed <= 1.5:
        score += 10
        reasons.append("Moderate current can help concentrate bait.")
    else:
        score -= 5
        reasons.append("Current is less ideal for concentrating bait.")

    if pressure is not None and pressure >= 1012:
        score += 5
        reasons.append("Stable pressure supports a better bite window.")
    elif pressure is None:
        reasons.append("Pressure data was unavailable, so it did not factor into the score.")

    # Chlorophyll is a productivity proxy: moderate values mark fertile water
    # that feeds the bait pelagics follow; very low is a blue-water desert and
    # very high is often murky, near-shore bloom. Extra context, not part of the
    # confidence math, so it is only scored when present.
    chlorophyll = conditions.get("chlorophyll_mg_m3")
    if chlorophyll is not None:
        if 0.1 <= chlorophyll <= 2.0:
            score += 8
            reasons.append(
                f"Chlorophyll ({chlorophyll} mg/m^3) indicates productive water likely to hold bait."
            )
        elif chlorophyll < 0.1:
            score -= 3
            reasons.append(
                f"Low chlorophyll ({chlorophyll} mg/m^3) suggests sparse, blue-water conditions."
            )
        else:
            reasons.append(
                f"High chlorophyll ({chlorophyll} mg/m^3) suggests turbid, near-shore bloom water."
            )

    if request.target_depth_ft and request.target_depth_ft > 1000:
        score -= 5
        reasons.append("Very deep targets add complexity for a simple trip plan.")

    signal_summary: dict | None = None
    if signals is not None:
        score, signal_summary = _score_signals(request, signals, score, reasons)

    score = max(0, min(100, score))

    if score >= 80:
        label = "excellent"
    elif score >= 60:
        label = "good"
    elif score >= 40:
        label = "fair"
    else:
        label = "poor"

    available = [field for field in SCORABLE_FIELDS if conditions.get(field) is not None]
    missing = [field for field in SCORABLE_FIELDS if conditions.get(field) is None]

    if len(available) == len(SCORABLE_FIELDS):
        confidence = "high"
    elif len(available) >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    # A future-dated window has no real observations, so conditions are only a
    # nowcast proxy: report the mode and never claim better than medium.
    if plan is not None:
        if plan.mode == "historical":
            reasons.append(
                f"Conditions reflect archived observations near {plan.target_date.isoformat()} "
                "(historical window)."
            )
        elif plan.mode == "forecast":
            used_forecast = "nws-forecast" in (conditions.get("provenance") or {}).values()
            if used_forecast:
                reasons.append(
                    f"Future window: wind/waves come from the NWS forecast for "
                    f"{plan.target_date.isoformat()}; SST is the latest-observation proxy. "
                    "Forecast uncertainty caps confidence."
                )
            else:
                reasons.append(
                    "Requested window is in the future; conditions are a latest-observation proxy, "
                    "so confidence is capped."
                )
            if confidence == "high":
                confidence = "medium"

    result = {
        "score": score,
        "label": label,
        "summary": f"{label.title()} conditions for {request.species.lower()} fishing.",
        "reasons": reasons,
        "confidence": confidence,
        "data_completeness": {"available": available, "missing": missing},
    }
    if plan is not None:
        result["temporal_mode"] = plan.mode
    if signal_summary is not None:
        result["signals_considered"] = signal_summary
    return result
