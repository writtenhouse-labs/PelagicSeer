# NOAA Data Sources

PelagicSeer should treat NOAA as several related data systems rather than one API.

## CO-OPS Tides and Currents

Best for station-based near-real-time and historical observations:

- Water temperature
- Currents and current predictions
- Water levels and tide predictions
- Wind
- Air temperature
- Barometric pressure
- Conductivity
- Salinity
- Visibility
- Humidity

Connector: `backend/connectors/noaa_coops.py`

Useful agent: a station-observation agent that selects nearby stations, chooses products, normalizes units, and summarizes fishing-relevant conditions.

## NDBC Buoys

Best for buoy and C-MAN station conditions:

- Significant wave height
- Dominant and average wave period
- Wind direction, speed, and gusts
- Sea surface temperature
- Air temperature
- Sea-level pressure
- Visibility where available

Connector: `backend/connectors/noaa_ndbc.py`

Useful agent: a buoy-matching agent that finds nearby offshore stations, checks data freshness, and extracts wave and temperature features.

## CoastWatch ERDDAP

Best for gridded and satellite data:

- Sea surface temperature grids
- Chlorophyll and ocean color
- Environmental rasters over larger areas
- Time slices for model features

Connector: `backend/connectors/noaa_erddap.py`

Useful agent: a geospatial extraction agent that selects datasets, builds bounded ERDDAP queries, samples a lat/lon box, and returns model-ready features.

## NCEI Archives

Best for historical ocean and climate records:

- Historical currents
- Archived buoy and marine observations
- Long-term sea surface temperature records
- Climate normals and anomalies

Connector: `backend/connectors/noaa_ncei.py`

Useful agent: a historical-feature agent that retrieves archives for training windows and builds lagged features for predictive models.

## NOAA Fisheries DisMAP

Best for species distribution context:

- Fish and invertebrate survey distributions
- Biomass distribution surfaces
- Distribution indicators over time
- Regional survey-based species presence context

Useful agent: a species-distribution agent that maps target species to survey products and combines historical distribution with live environmental features.

## Practical Agent Plan

Start with three small agents:

1. `EnvironmentCollectorAgent` gathers NOAA station, buoy, and gridded environmental data.
2. `SpeciesContextAgent` gathers species distribution, habitat preferences, and seasonal context.
3. `FishingAdvisorAgent` combines environmental features and species context into a score, explanation, and uncertainty level.

Keep the first version deterministic. Add Claude later as a planner/explainer once the connectors return clean, testable data.
