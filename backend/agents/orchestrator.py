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


def build_fishing_advice(request: AdviceRequest, conditions: dict) -> dict:
    """Rule-based advisor placeholder for the future Claude/LangChain agent.

    Tolerates missing condition fields: any factor without data is skipped
    (neither helping nor hurting the score) and reported, and the result
    carries a confidence level reflecting how much real data was available.
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

    if request.target_depth_ft and request.target_depth_ft > 1000:
        score -= 5
        reasons.append("Very deep targets add complexity for a simple trip plan.")

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

    return {
        "score": score,
        "label": label,
        "summary": f"{label.title()} conditions for {request.species.lower()} fishing.",
        "reasons": reasons,
        "confidence": confidence,
        "data_completeness": {"available": available, "missing": missing},
    }
