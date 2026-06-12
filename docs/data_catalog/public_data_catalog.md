# PelagicSeer Public Data Source Catalog

Generated on 2026-06-12 from configured connectors in `backend/connectors`.
Secrets and authentication headers are omitted or redacted.

## FAO - FishStat placeholder

- Endpoint: `N/A`
- Notes: Connector exists as stub only; no public endpoint configured.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| source | string | Integration/source identifier returned by PelagicSeer or upstream service. | fao-fishstat |
| status | string | Inferred upstream field; meaning based on API context and field name. | not_implemented |

## Global Fishing Watch - 4Wings apparent fishing effort

- Endpoint: `https://gateway.api.globalfishingwatch.org/v3/4wings/report?spatial-resolution=LOW&temporal-resolution=MONTHLY&datasets%5B0%5D=public-global-fishing-effort%3Alatest&date-range=2026-05-13%2C2026-06-12&format=JSON&group-by=FLAG`
- Notes: Bearer token required; Authorization header redacted and not stored. 30-day, low-resolution sample.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| entries | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"public-global-fishing-effort:v4.0": [{"date": "2026-05", "flag": "USA", "hours": 0.5575, "lat": 32.2, "lon": -117.3, "vesselIDs": 1}, {"date": "2026-06", "fl |
| entries[].public-global-fishing-effort:v4.0 | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"date": "2026-05", "flag": "USA", "hours": 0.5575, "lat": 32.2, "lon": -117.3, "vesselIDs": 1}, {"date": "2026-06", "flag": "USA", "hours": 0.8744444444444446 |
| entries[].public-global-fishing-effort:v4.0[].date | string | Observation date or month bucket. | 2026-05; 2026-06 |
| entries[].public-global-fishing-effort:v4.0[].flag | string | Vessel flag state code/name. | USA |
| entries[].public-global-fishing-effort:v4.0[].hours | number | Apparent fishing effort hours reported by GFW. | 0.5575; 0.8744444444444446; 0.8675000000000004 |
| entries[].public-global-fishing-effort:v4.0[].lat | number | Latitude in decimal degrees, often encoded as a string by the upstream API. | 32.2; 32.4; 32.6 |
| entries[].public-global-fishing-effort:v4.0[].lon | number | Longitude in decimal degrees, often encoded as a string by the upstream API. | -117.3; -117.1 |
| entries[].public-global-fishing-effort:v4.0[].vesselIDs | integer | Inferred upstream field; meaning based on API context and field name. | 1 |
| entries_sample_note | string | Inferred upstream field; meaning based on API context and field name. | Original array truncated to 1 of 1 rows. |
| limit | null | Inferred upstream field; meaning based on API context and field name. |  |
| metadata | object | Inferred upstream field; meaning based on API context and field name. | {} |
| nextOffset | null | Inferred upstream field; meaning based on API context and field name. |  |
| offset | null | Inferred upstream field; meaning based on API context and field name. |  |
| total | integer | Inferred upstream field; meaning based on API context and field name. | 1 |

## NOAA CO-OPS - Data Getter water_level latest

- Endpoint: `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station=9410170&product=water_level&date=latest&time_zone=gmt&units=english&format=json&application=PelagicSeer&datum=MLLW`
- Notes: No token. Safe latest observation for San Diego station.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| data | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"f": "1,0,0,0", "q": "p", "s": "0.072", "t": "2026-06-12 18:12", "v": "3.086"}] |
| data[].f | string | Inferred upstream field; meaning based on API context and field name. | 1,0,0,0 |
| data[].q | string | Inferred upstream field; meaning based on API context and field name. | p |
| data[].s | string | Inferred upstream field; meaning based on API context and field name. | 0.072 |
| data[].t | string | Inferred upstream field; meaning based on API context and field name. | 2026-06-12 18:12 |
| data[].v | string | Inferred upstream field; meaning based on API context and field name. | 3.086 |
| data_sample_note | string | Inferred upstream field; meaning based on API context and field name. | Original array truncated to 1 of 1 rows. |
| metadata | object | Inferred upstream field; meaning based on API context and field name. | {"id": "9410170", "lat": "32.7156", "lon": "-117.1767", "name": "San Diego"} |
| metadata.id | string | Upstream identifier. | 9410170 |
| metadata.lat | string | Latitude in decimal degrees, often encoded as a string by the upstream API. | 32.7156 |
| metadata.lon | string | Longitude in decimal degrees, often encoded as a string by the upstream API. | -117.1767 |
| metadata.name | string | Human-readable station, dataset, or place name. | San Diego |

## NOAA CO-OPS - Station Metadata

- Endpoint: `https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels`
- Notes: No token. Metadata sample limited by upstream response.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| count | integer | Inferred upstream field; meaning based on API context and field name. | 301 |
| self | null | Inferred upstream field; meaning based on API context and field name. |  |
| stations | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"HTFhistorical": true, "HTFmonthly": true, "affiliations": "NWLON", "benchmarks": {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1 |
| stations[].HTFhistorical | boolean | Inferred upstream field; meaning based on API context and field name. | True; False |
| stations[].HTFmonthly | boolean | Inferred upstream field; meaning based on API context and field name. | True; False |
| stations[].affiliations | string | Inferred upstream field; meaning based on API context and field name. | NWLON; PORTS |
| stations[].benchmarks | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/benchmarks.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/benchmarks.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/benchmarks.json"} |
| stations[].benchmarks.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/benchmarks.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/benchmarks.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/benchmarks.json |
| stations[].datums | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/datums.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/datums.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/datums.json"} |
| stations[].datums.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/datums.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/datums.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/datums.json |
| stations[].details | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/details.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/details.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/details.json"} |
| stations[].details.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/details.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/details.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/details.json |
| stations[].disclaimers | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/disclaimers.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/disclaimers.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/disclaimers.json"} |
| stations[].disclaimers.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/disclaimers.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/disclaimers.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/disclaimers.json |
| stations[].expand | string | Inferred upstream field; meaning based on API context and field name. | details,sensors,floodlevels,datums,harcon,tidepredoffsets,ofsmapoffsets,products,disclaimers,notices |
| stations[].floodlevels | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/floodlevels.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/floodlevels.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/floodlevels.json"} |
| stations[].floodlevels.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/floodlevels.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/floodlevels.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/floodlevels.json |
| stations[].forecast | boolean | Inferred upstream field; meaning based on API context and field name. | False |
| stations[].greatlakes | boolean | Inferred upstream field; meaning based on API context and field name. | False |
| stations[].harmonicConstituents | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/harcon.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/harcon.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/harcon.json"} |
| stations[].harmonicConstituents.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/harcon.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/harcon.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/harcon.json |
| stations[].id | string | Upstream identifier. | 1611400; 1612340; 1612401 |
| stations[].inundationdb | boolean | Inferred upstream field; meaning based on API context and field name. | True |
| stations[].lat | number | Latitude in decimal degrees, often encoded as a string by the upstream API. | 21.9544; 21.303333; 21.3675 |
| stations[].lng | number | Inferred upstream field; meaning based on API context and field name. | -159.3561; -157.86453; -157.9639 |
| stations[].name | string | Human-readable station, dataset, or place name. | Nawiliwili; Honolulu; Pearl Harbor |
| stations[].nearby | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/nearby.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/nearby.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/nearby.json"} |
| stations[].nearby.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/nearby.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/nearby.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/nearby.json |
| stations[].nonNavigational | boolean | Inferred upstream field; meaning based on API context and field name. | False |
| stations[].notices | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/notices.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/notices.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/notices.json"} |
| stations[].notices.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/notices.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/notices.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/notices.json |
| stations[].observedst | boolean | Inferred upstream field; meaning based on API context and field name. | False; True |
| stations[].ofsMapOffsets | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/ofsmapoffsets.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/ofsmapoffsets.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/ofsmapoffsets.json"} |
| stations[].ofsMapOffsets.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/ofsmapoffsets.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/ofsmapoffsets.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/ofsmapoffsets.json |
| stations[].outlook | boolean | Inferred upstream field; meaning based on API context and field name. | True; False |
| stations[].portscode | null \| string | Inferred upstream field; meaning based on API context and field name. | ph |
| stations[].products | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/products.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/products.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/products.json"} |
| stations[].products.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/products.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/products.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/products.json |
| stations[].self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401.json |
| stations[].sensors | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/sensors.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/sensors.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/sensors.json"} |
| stations[].sensors.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/sensors.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/sensors.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/sensors.json |
| stations[].shefcode | string | Inferred upstream field; meaning based on API context and field name. | NWWH1; OOUH1; PRHH1 |
| stations[].state | string | Inferred upstream field; meaning based on API context and field name. | HI |
| stations[].stormsurge | boolean | Inferred upstream field; meaning based on API context and field name. | False |
| stations[].supersededdatums | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/supersededdatums.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/supersededdatums.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/supersededdatums.json"} |
| stations[].supersededdatums.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/supersededdatums.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/supersededdatums.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/supersededdatums.json |
| stations[].tidal | boolean | Inferred upstream field; meaning based on API context and field name. | True |
| stations[].tidePredOffsets | object | Inferred upstream field; meaning based on API context and field name. | {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/tidepredoffsets.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/tidepredoffsets.json"}; {"self": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/tidepredoffsets.json"} |
| stations[].tidePredOffsets.self | string | Inferred upstream field; meaning based on API context and field name. | https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1611400/tidepredoffsets.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612340/tidepredoffsets.json; https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/1612401/tidepredoffsets.json |
| stations[].tideType | string | Inferred upstream field; meaning based on API context and field name. | Mixed |
| stations[].timezone | string | Inferred upstream field; meaning based on API context and field name. | HAST |
| stations[].timezonecorr | integer | Inferred upstream field; meaning based on API context and field name. | -10 |
| stations_sample_note | string | Inferred upstream field; meaning based on API context and field name. | Original array truncated to 3 of 301 rows. |
| units | null | Inferred upstream field; meaning based on API context and field name. |  |

## NOAA ERDDAP - erdMH1chla8day chlorophyll

- Endpoint: `https://coastwatch.pfeg.noaa.gov/erddap/griddap/erdMH1chla8day.json?chlorophyll[(last)][(32.0)][(-118.0)]`
- Notes: No token. Single grid-cell query.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| table | object | Inferred upstream field; meaning based on API context and field name. | {"columnNames": ["time", "latitude", "longitude"], "columnTypes": ["String", "float", "float"], "columnUnits": ["UTC", "degrees_north", "degrees_east"], "rows": |
| table.columnNames | array<string> | Inferred upstream field; meaning based on API context and field name. | ["time", "latitude", "longitude"] |
| table.columnTypes | array<string> | Inferred upstream field; meaning based on API context and field name. | ["String", "float", "float"] |
| table.columnUnits | array<string> | Inferred upstream field; meaning based on API context and field name. | ["UTC", "degrees_north", "degrees_east"] |
| table.rows | array<array<number\|string>> | Inferred upstream field; meaning based on API context and field name. | [["2022-06-14T00:00:00Z", 32.020832, -118.02083]] |
| table.rows[] | array<number\|string> | Inferred upstream field; meaning based on API context and field name. | ["2022-06-14T00:00:00Z", 32.020832, -118.02083] |

## NOAA ERDDAP - jplMURSST41 analysed_sst

- Endpoint: `https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.json?analysed_sst[(last)][(32.7157)][(-117.1611)]`
- Notes: No token. Single grid-cell query.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| table | object | Inferred upstream field; meaning based on API context and field name. | {"columnNames": ["time", "latitude", "longitude"], "columnTypes": ["String", "float", "float"], "columnUnits": ["UTC", "degrees_north", "degrees_east"], "rows": |
| table.columnNames | array<string> | Inferred upstream field; meaning based on API context and field name. | ["time", "latitude", "longitude"] |
| table.columnTypes | array<string> | Inferred upstream field; meaning based on API context and field name. | ["String", "float", "float"] |
| table.columnUnits | array<string> | Inferred upstream field; meaning based on API context and field name. | ["UTC", "degrees_north", "degrees_east"] |
| table.rows | array<array<number\|string>> | Inferred upstream field; meaning based on API context and field name. | [["2026-06-11T09:00:00Z", 32.72, -117.16]] |
| table.rows[] | array<number\|string> | Inferred upstream field; meaning based on API context and field name. | ["2026-06-11T09:00:00Z", 32.72, -117.16] |

## NOAA InPort - Item XML

- Endpoint: `https://www.fisheries.noaa.gov/inport/item/79931/inport-xml`
- Notes: No token. XML parsed into catalog metadata and distributions.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| parsed_metadata | object | Inferred upstream field; meaning based on API context and field name. | {"catalog_item_id": "79931", "catalog_item_type": "Data Set", "description": "Original Dataset Product: Classified LAS 1.4 files, formatted to individual 1,000m |
| parsed_metadata.catalog_item_id | string | Inferred upstream field; meaning based on API context and field name. | 79931 |
| parsed_metadata.catalog_item_type | string | Inferred upstream field; meaning based on API context and field name. | Data Set |
| parsed_metadata.description | string | Free-text description supplied by upstream metadata. | Original Dataset Product: Classified LAS 1.4 files, formatted to individual 1,000m x 1,000m tiles covering the CA North Sierra 2022 project area. Original Datas |
| parsed_metadata.distribution_count | integer | Inferred upstream field; meaning based on API context and field name. | 18 |
| parsed_metadata.distributions | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"classification": "Unknown", "connector": "unknown", "description": "The Data Access Viewer (DAV) allows a user to search for and download elevation, imagery, |
| parsed_metadata.distributions[].classification | string | PelagicSeer classification of a distribution URL. | Unknown |
| parsed_metadata.distributions[].connector | string | PelagicSeer downstream connector type for a distribution URL. | unknown |
| parsed_metadata.distributions[].description | string | Free-text description supplied by upstream metadata. | The Data Access Viewer (DAV) allows a user to search for and download elevation, imagery, and land cover data for the coastal U.S. and its territories. The data; Link to the lidar report for CA_SierraNevada_10; Link to the lidar report for CA_SierraNevada_11 |
| parsed_metadata.distributions[].name | string | Human-readable station, dataset, or place name. | NOAA's Office for Coastal Management (OCM) Data Access Viewer (DAV); Lidar Report - CA_SierraNevada_10; Lidar Report - CA_SierraNevada_11 |
| parsed_metadata.distributions[].source_section | string | Inferred upstream field; meaning based on API context and field name. | urls |
| parsed_metadata.distributions[].url | string | Distribution or access URL. | https://coast.noaa.gov/dataviewer/; https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/metadata/CA_SierraNevada_B22/CA_SierraNevada_10_2022/reports/CA_SierraNevada_10_2022_Lidar_Mapping_Rep; https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/metadata/CA_SierraNevada_B22/CA_SierraNevada_11_B22/reports/140G0222F0176_CA_SierraNevada_2022_WU_3004 |
| parsed_metadata.distributions[].url_type | string | Inferred upstream field; meaning based on API context and field name. | Online Resource |
| parsed_metadata.guid | string | Inferred upstream field; meaning based on API context and field name. | gov.noaa.nmfs.inport:79931 |
| parsed_metadata.owner_organization | string | Inferred upstream field; meaning based on API context and field name. | OCM Partners |
| parsed_metadata.source | string | Integration/source identifier returned by PelagicSeer or upstream service. | inport |
| parsed_metadata.title | string | Catalog item title. | 2021 - 2022 UCSD/USGS Lidar: Sierra Nevada, CA |
| xml_excerpt | string | Inferred upstream field; meaning based on API context and field name. | <?xml version="1.0" encoding="UTF-8"?> <inport-metadata xmlns:xs="http://www.w3.org/2001/XMLSchema" version="1.11" source="https://www.fisheries.noaa.gov"> <ite |

## NOAA NCEI/CDO - CDO datasets

- Endpoint: `https://www.ncdc.noaa.gov/cdo-web/api/v2/datasets?limit=3`
- Notes: Token required; token header redacted and not stored. Limit 3.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| metadata | object | Inferred upstream field; meaning based on API context and field name. | {"resultset": {"count": 11, "limit": 3, "offset": 1}} |
| metadata.resultset | object | Inferred upstream field; meaning based on API context and field name. | {"count": 11, "limit": 3, "offset": 1} |
| metadata.resultset.count | integer | Inferred upstream field; meaning based on API context and field name. | 11 |
| metadata.resultset.limit | integer | Inferred upstream field; meaning based on API context and field name. | 3 |
| metadata.resultset.offset | integer | Inferred upstream field; meaning based on API context and field name. | 1 |
| results | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"datacoverage": 1, "id": "GHCND", "maxdate": "2026-06-09", "mindate": "1763-01-01", "name": "Daily Summaries", "uid": "gov.noaa.ncdc:C00861"}, {"datacoverage" |
| results[].datacoverage | integer | Inferred upstream field; meaning based on API context and field name. | 1 |
| results[].id | string | Upstream identifier. | GHCND; GSOM; GSOY |
| results[].maxdate | string | Inferred upstream field; meaning based on API context and field name. | 2026-06-09; 2026-06-01; 2026-01-01 |
| results[].mindate | string | Inferred upstream field; meaning based on API context and field name. | 1763-01-01 |
| results[].name | string | Human-readable station, dataset, or place name. | Daily Summaries; Global Summary of the Month; Global Summary of the Year |
| results[].uid | string | Inferred upstream field; meaning based on API context and field name. | gov.noaa.ncdc:C00861; gov.noaa.ncdc:C00946; gov.noaa.ncdc:C00947 |
| results_sample_note | string | Inferred upstream field; meaning based on API context and field name. | Original array truncated to 3 of 3 rows. |

## NOAA NDBC - Active Stations

- Endpoint: `https://www.ndbc.noaa.gov/activestations.xml`
- Notes: No token. XML parsed into station attributes.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| parsed_station_sample | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"latitude": 12.0, "longitude": -23.0, "name": "NE Extension", "station": "13001", "type": "buoy"}, {"latitude": 21.0, "longitude": -23.0, "name": "NE Extensio |
| parsed_station_sample[].latitude | number | Latitude in decimal degrees. | 12.0; 21.0; 15.0 |
| parsed_station_sample[].longitude | number | Longitude in decimal degrees. | -23.0; -38.0 |
| parsed_station_sample[].name | string | Human-readable station, dataset, or place name. | NE Extension; Reggae |
| parsed_station_sample[].station | string | Station identifier. | 13001; 13002; 13008 |
| parsed_station_sample[].type | string | Inferred upstream field; meaning based on API context and field name. | buoy |
| xml_excerpt | string | Inferred upstream field; meaning based on API context and field name. | <?xml version="1.0" encoding="utf-8"?><stations created="2026-06-12T18:10:04UTC" count="1355"> <!--Site Elevation (elev attribute), when present, is reported in |

## NOAA NDBC - realtime2 text feed

- Endpoint: `https://www.ndbc.noaa.gov/data/realtime2/46086.txt`
- Notes: No token. Text parsed into header/unit/sample rows.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| header | array<string> | Inferred upstream field; meaning based on API context and field name. | ["YY", "MM", "DD", "hh", "mm", "WDIR", "WSPD", "GST", "WVHT", "DPD", "APD", "MWD", "PRES", "ATMP", "WTMP", "DEWP", "VIS", "PTDY", "TIDE"] |
| rows | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"APD": "MM", "ATMP": "17.8", "DD": "12", "DEWP": "17.2", "DPD": "MM", "GST": "6.0", "MM": "06", "MWD": "MM", "PRES": "1011.9", "PTDY": "MM", "TIDE": "MM", "VI |
| rows[].APD | string | Inferred upstream field; meaning based on API context and field name. | MM; 8.9 |
| rows[].ATMP | string | Inferred upstream field; meaning based on API context and field name. | 17.8; 17.7 |
| rows[].DD | string | Inferred upstream field; meaning based on API context and field name. | 12 |
| rows[].DEWP | string | Inferred upstream field; meaning based on API context and field name. | 17.2; 17.1; 17.0 |
| rows[].DPD | string | Inferred upstream field; meaning based on API context and field name. | MM; 15 |
| rows[].GST | string | Inferred upstream field; meaning based on API context and field name. | 6.0; 5.0 |
| rows[].MM | string | Inferred upstream field; meaning based on API context and field name. | 06 |
| rows[].MWD | string | Inferred upstream field; meaning based on API context and field name. | MM; 184 |
| rows[].PRES | string | Inferred upstream field; meaning based on API context and field name. | 1011.9; 1011.8; 1012.0 |
| rows[].PTDY | string | Inferred upstream field; meaning based on API context and field name. | MM |
| rows[].TIDE | string | Inferred upstream field; meaning based on API context and field name. | MM |
| rows[].VIS | string | Inferred upstream field; meaning based on API context and field name. | MM |
| rows[].WDIR | string | Inferred upstream field; meaning based on API context and field name. | 330; 320 |
| rows[].WSPD | string | Inferred upstream field; meaning based on API context and field name. | 5.0; 4.0 |
| rows[].WTMP | string | Inferred upstream field; meaning based on API context and field name. | 19.7 |
| rows[].WVHT | string | Inferred upstream field; meaning based on API context and field name. | MM; 1.4 |
| rows[].YY | string | Inferred upstream field; meaning based on API context and field name. | 2026 |
| rows[].hh | string | Inferred upstream field; meaning based on API context and field name. | 17 |
| rows[].mm | string | Inferred upstream field; meaning based on API context and field name. | 40; 30; 20 |
| text_excerpt | string | Inferred upstream field; meaning based on API context and field name. | #YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP DEWP VIS PTDY TIDE #yr mo dy hr mn degT m/s m/s m sec sec degT hPa degC degC degC nmi hPa ft 2026  |
| units | array<string> | Inferred upstream field; meaning based on API context and field name. | ["yr", "mo", "dy", "hr", "mn", "degT", "m/s", "m/s", "m", "sec", "sec", "degT", "hPa", "degC", "degC", "degC", "nmi", "hPa", "ft"] |

## OBIS - Checklist

- Endpoint: `https://api.obis.org/v3/checklist?geometry=POLYGON+%28%28-119.1611+30.7157%2C+-115.1611+30.7157%2C+-115.1611+34.7157%2C+-119.1611+34.7157%2C+-119.1611+30.7157%29%29`
- Notes: No token. Area checklist for sample box.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| results | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"acceptedNameUsage": "Macrocystis pyrifera", "acceptedNameUsageID": 232231, "class": "Phaeophyceae", "classid": 830, "family": "Laminariaceae", "familyid": 14 |
| results[].acceptedNameUsage | string | Inferred upstream field; meaning based on API context and field name. | Macrocystis pyrifera; Megastraea undosa; Mesocentrotus franciscanus |
| results[].acceptedNameUsageID | integer | Inferred upstream field; meaning based on API context and field name. | 232231; 528084; 591102 |
| results[].class | string | Inferred upstream field; meaning based on API context and field name. | Phaeophyceae; Gastropoda; Echinoidea |
| results[].classid | integer | Inferred upstream field; meaning based on API context and field name. | 830; 101; 123082 |
| results[].family | string | Inferred upstream field; meaning based on API context and field name. | Laminariaceae; Turbinidae; Strongylocentrotidae |
| results[].familyid | integer | Inferred upstream field; meaning based on API context and field name. | 143755; 503; 123161 |
| results[].genus | string | Inferred upstream field; meaning based on API context and field name. | Macrocystis; Megastraea; Mesocentrotus |
| results[].genusid | integer | Inferred upstream field; meaning based on API context and field name. | 206527; 528082; 591101 |
| results[].infraclass | string | Inferred upstream field; meaning based on API context and field name. | Carinacea |
| results[].infraclassid | integer | Inferred upstream field; meaning based on API context and field name. | 510517 |
| results[].infrakingdom | string | Inferred upstream field; meaning based on API context and field name. | Heterokonta |
| results[].infrakingdomid | integer | Inferred upstream field; meaning based on API context and field name. | 368898 |
| results[].infraorder | string | Inferred upstream field; meaning based on API context and field name. | Echinidea |
| results[].infraorderid | integer | Inferred upstream field; meaning based on API context and field name. | 510534 |
| results[].is_brackish | boolean | Inferred upstream field; meaning based on API context and field name. | False |
| results[].is_freshwater | boolean | Inferred upstream field; meaning based on API context and field name. | False |
| results[].is_marine | boolean | Inferred upstream field; meaning based on API context and field name. | True |
| results[].is_terrestrial | boolean | Inferred upstream field; meaning based on API context and field name. | False |
| results[].kingdom | string | Inferred upstream field; meaning based on API context and field name. | Chromista; Animalia |
| results[].kingdomid | integer | Inferred upstream field; meaning based on API context and field name. | 7; 2 |
| results[].ncbi_id | integer | Inferred upstream field; meaning based on API context and field name. | 35122; 529768; 1328066 |
| results[].order | string | Inferred upstream field; meaning based on API context and field name. | Laminariales; Trochida; Camarodonta |
| results[].orderid | integer | Inferred upstream field; meaning based on API context and field name. | 845; 1052448; 510518 |
| results[].phylum | string | Inferred upstream field; meaning based on API context and field name. | Ochrophyta; Mollusca; Echinodermata |
| results[].phylumid | integer | Inferred upstream field; meaning based on API context and field name. | 345465; 51; 1806 |
| results[].records | integer | Count of records for a taxon/checklist row. | 246059; 34882; 34087 |
| results[].scientificName | string | Taxonomic scientific name. | Macrocystis pyrifera; Megastraea undosa; Mesocentrotus franciscanus |
| results[].scientificNameAuthorship | string | Inferred upstream field; meaning based on API context and field name. | (Linnaeus) C.Agardh, 1820; (W. Wood, 1828); (A. Agassiz, 1863) |
| results[].species | string | Inferred upstream field; meaning based on API context and field name. | Macrocystis pyrifera; Megastraea undosa; Mesocentrotus franciscanus |
| results[].speciesid | integer | Inferred upstream field; meaning based on API context and field name. | 232231; 528084; 591102 |
| results[].subclass | string | Inferred upstream field; meaning based on API context and field name. | Fucophycidae; Vetigastropoda; Euechinoidea |
| results[].subclassid | integer | Inferred upstream field; meaning based on API context and field name. | 1304856; 156485; 149854 |
| results[].subfamily | string | Inferred upstream field; meaning based on API context and field name. | Turbininae |
| results[].subfamilyid | integer | Inferred upstream field; meaning based on API context and field name. | 225151 |
| results[].subkingdom | string | Inferred upstream field; meaning based on API context and field name. | Harosa |
| results[].subkingdomid | integer | Inferred upstream field; meaning based on API context and field name. | 582419 |
| results[].subphylum | string | Inferred upstream field; meaning based on API context and field name. | Echinozoa |
| results[].subphylumid | integer | Inferred upstream field; meaning based on API context and field name. | 148744 |
| results[].subterclass | string | Inferred upstream field; meaning based on API context and field name. | Echinacea |
| results[].subterclassid | integer | Inferred upstream field; meaning based on API context and field name. | 149855 |
| results[].superfamily | string | Inferred upstream field; meaning based on API context and field name. | Trochoidea; Odontophora |
| results[].superfamilyid | integer | Inferred upstream field; meaning based on API context and field name. | 156489; 510604 |
| results[].taxonID | integer | Inferred upstream field; meaning based on API context and field name. | 232231; 528084; 591102 |
| results[].taxonRank | string | Inferred upstream field; meaning based on API context and field name. | Species |
| results[].taxonomicStatus | string | Inferred upstream field; meaning based on API context and field name. | accepted |
| results_sample_note | string | Inferred upstream field; meaning based on API context and field name. | Original array truncated to 3 of 10 rows. |
| total | integer | Inferred upstream field; meaning based on API context and field name. | 9066 |

## OBIS - Occurrence

- Endpoint: `https://api.obis.org/v3/occurrence?scientificname=Thunnus+albacares&geometry=POLYGON+%28%28-119.1611+30.7157%2C+-115.1611+30.7157%2C+-115.1611+34.7157%2C+-119.1611+34.7157%2C+-119.1611+30.7157%29%29&size=3`
- Notes: No token. Size limited to 3 records.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| results | array<unknown> | Inferred upstream field; meaning based on API context and field name. | [] |
| results_sample_note | string | Inferred upstream field; meaning based on API context and field name. | Original array truncated to 0 of 0 rows. |
| total | integer | Inferred upstream field; meaning based on API context and field name. | 0 |

## OpenStreetMap - Nominatim Search

- Endpoint: `https://nominatim.openstreetmap.org/search?city=San+Diego&state=CA&country=USA&format=jsonv2&limit=1`
- Notes: No token. User-Agent configured in connector.

| Field Name | Data Type | Description/Inferred Meaning | Example Values |
|---|---|---|---|
| root | array<object> | Inferred upstream field; meaning based on API context and field name. | [{"addresstype": "city", "boundingbox": ["32.5347979", "33.1141940", "-117.3098161"], "category": "boundary", "display_name": "San Diego, San Diego County, Cali |
| root[].addresstype | string | Inferred upstream field; meaning based on API context and field name. | city |
| root[].boundingbox | array<string> | Inferred upstream field; meaning based on API context and field name. | ["32.5347979", "33.1141940", "-117.3098161"] |
| root[].category | string | Inferred upstream field; meaning based on API context and field name. | boundary |
| root[].display_name | string | Inferred upstream field; meaning based on API context and field name. | San Diego, San Diego County, California, United States |
| root[].importance | number | Inferred upstream field; meaning based on API context and field name. | 0.731977951818745 |
| root[].lat | string | Latitude in decimal degrees, often encoded as a string by the upstream API. | 32.7174202 |
| root[].licence | string | Inferred upstream field; meaning based on API context and field name. | Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright |
| root[].lon | string | Longitude in decimal degrees, often encoded as a string by the upstream API. | -117.1627720 |
| root[].name | string | Human-readable station, dataset, or place name. | San Diego |
| root[].osm_id | integer | Inferred upstream field; meaning based on API context and field name. | 253832 |
| root[].osm_type | string | Inferred upstream field; meaning based on API context and field name. | relation |
| root[].place_id | integer | Inferred upstream field; meaning based on API context and field name. | 317794838 |
| root[].place_rank | integer | Inferred upstream field; meaning based on API context and field name. | 16 |
| root[].type | string | Inferred upstream field; meaning based on API context and field name. | administrative |
