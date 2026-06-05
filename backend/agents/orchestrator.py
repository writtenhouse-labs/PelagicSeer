from api.schemas import AdviceRequest


def build_fishing_advice(request: AdviceRequest, conditions: dict) -> dict:
    """Rule-based advisor placeholder for the future Claude/LangChain agent."""
    score = 50
    reasons: list[str] = []

    wind_speed = conditions["wind_speed_kts"]
    wave_height = conditions["wave_height_ft"]
    sea_temp = conditions["sea_surface_temp_f"]
    current_speed = conditions["current_speed_kts"]
    pressure = conditions["barometric_pressure_mb"]

    if wind_speed <= 12:
        score += 15
        reasons.append("Light wind should make fishing conditions easier.")
    else:
        score -= 20
        reasons.append("Stronger wind may make boat handling and casting harder.")

    if wave_height <= 3:
        score += 15
        reasons.append("Low seas are favorable for safe, comfortable fishing.")
    else:
        score -= 20
        reasons.append("Higher seas reduce comfort and safety.")

    if 68 <= sea_temp <= 78:
        score += 15
        reasons.append("Water temperature is in a productive range for many pelagic species.")
    else:
        score -= 10
        reasons.append("Water temperature is outside the preferred general range.")

    if 0.4 <= current_speed <= 1.5:
        score += 10
        reasons.append("Moderate current can help concentrate bait.")
    else:
        score -= 5
        reasons.append("Current is less ideal for concentrating bait.")

    if pressure >= 1012:
        score += 5
        reasons.append("Stable pressure supports a better bite window.")

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

    return {
        "score": score,
        "label": label,
        "summary": f"{label.title()} conditions for {request.species.lower()} fishing.",
        "reasons": reasons,
    }
