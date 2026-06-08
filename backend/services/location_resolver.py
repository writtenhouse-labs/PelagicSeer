from typing import Any

from connectors.geocoding import geocode_city_state
from connectors.noaa_ndbc import find_nearest_ndbc_station


MAX_OCEAN_DISTANCE_MILES = 20.0
NM_TO_MILES = 1.15078
TOO_FAR_MESSAGE = "You're too far from the Ocean to fish silly"


def resolve_location(city: str, state: str) -> dict[str, Any]:
    """Geocode the location and determine whether it is close enough to fish."""
    location = geocode_city_state(city, state)
    nearest_station = find_nearest_ndbc_station(
        location["latitude"], location["longitude"]
    )
    ocean_distance_miles = round(nearest_station["distance_nm"] * NM_TO_MILES, 1)

    return {
        **location,
        "nearest_ocean_station": nearest_station,
        "ocean_distance_miles": ocean_distance_miles,
        "too_far_from_ocean": ocean_distance_miles > MAX_OCEAN_DISTANCE_MILES,
    }
