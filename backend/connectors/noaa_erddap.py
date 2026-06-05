def get_mock_conditions(latitude: float, longitude: float) -> dict:
    """Return NOAA ERDDAP-shaped mock marine conditions for local development."""
    return {
        "source": "mock-noaa-erddap",
        "latitude": latitude,
        "longitude": longitude,
        "sea_surface_temp_f": 72.4,
        "wind_speed_kts": 9.0,
        "wave_height_ft": 2.1,
        "barometric_pressure_mb": 1016.2,
        "current_speed_kts": 0.8,
        "visibility_nm": 8.5,
    }
