# Changelog

All notable changes to weather-file-builder. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions before
2.1.0 are described only by their git tags.

## 2.3.0

### Fixed
- **ERA5 wind direction was reversed.** `era5_to_dataframe` computed
  `atan2(u10, v10)`, the direction the air moves *towards*; EPW and station
  tables need the direction it comes *from*. A westerly (u10 > 0) was written
  as 90 instead of 270. Every ERA5 typical or extreme year built with 2.2.0
  or earlier has wind directions off by 180 degrees; **regenerate them**.
  Speeds and all other fields are unaffected. New helper
  `converters.wind_direction_from_uv`.

### Added
- `core.download_station_table(latitude, longitude, start_date, end_date)`
  and `converters.era5_to_station_table(raw)`: ERA5-Land for a point as a
  station table in the upload contract (UTC `timestamp` marking the end of
  each hour, `COLUMN_SPEC` names and units, `rh_pct` from temperature and dew
  point). Missing values stay missing and 29 February is kept, unlike
  `era5_to_dataframe`. ERA5-Land radiation and precipitation are hourly sums
  labelled at the end of the hour (ECMWF ERA5-Land time-series user guide);
  small negative values from the de-accumulation are set to zero. For filling
  gaps in a measured table after the user has compared and corrected it.

### Changed
- `validate_station_table` is about 2.5x faster and uses half the memory
  (600k 10-minute rows: 10 s to 4 s, +250 MB): it no longer computes the
  sub-hourly clearness variability, and groups months without string
  formatting. New `aggregate_to_hourly(..., variability=False)`.
- The CDS call is split out as `core._retrieve_era5_land`, returning the raw
  records; `download_time_series` behaves as before (apart from the wind fix).

## 2.2.0

### Added
- **Station upload contract** (`station_upload.py`) for the Boundary Conditions
  app (its ADR-037). `read_station_parquet` checks the Parquet schema and row
  count before reading. `validate_station_table` returns a
  `StationValidationReport` (`ok`, `issues`, `to_dict()`, `to_text()`) and
  never repairs anything:
  - errors: missing or unknown columns, non-numeric columns, a `timestamp`
    that is not a tz-aware UTC timestamp, duplicate or off-grid timestamps,
    spacing other than 10/15/30/60 min, values outside `RANGES` (with unit
    hints such as "looks like hPa"), half-hour time zones, and a clock check:
    in every month the irradiance-weighted mean time of day (interval
    mid-points) must be within `clock_tolerance_min` (default 45) of solar noon;
  - warnings: tolerated values (irradiance down to -10 W/m2, RH up to 105 %),
    clock offsets over 20 min, long gaps, months whose brighter hours stay
    far from clear-sky irradiance, fewer than 10 typical-year candidates;
  - gaps are reported, not rejected: `long_gaps`, `short_gap_hours`,
    `month_status` per variable, `amy_years`, `partial_amy_years` and
    `tmy_candidates` say what can be built.
- `build_amy_dataframe(..., empty_months="allow")`: a required variable may
  be entirely empty in a month (each variable on its own). Those months are
  written with EPW missing codes, `report.empty_months` lists them,
  `report.partial` is true and COMMENTS 2 starts with `PARTIAL - months
  written with EPW missing codes: ...`.
- Hours of an AMY year that fall outside the record because of the time-zone
  shift (up to `max_gap_hours + ceil(|utc_offset|)`) are filled from the
  adjacent day, shifted to join the record (`report.edge_filled_hours`).
- Test fixtures from a real 1-minute logger in Zurich
  (`tests/data/station_upload/`, built by
  `scripts/prepare_station_upload_fixtures.py`): one the validator must
  reject and one prepared file that builds a 2025 AMY.

### Changed
- `aggregate_to_hourly` (and the AMY and station TMY builders) keep an hour
  with at most `max_missing_per_hour` missing sub-hourly readings (default 1;
  before, any missing reading dropped the hour). Sums over an incomplete hour
  are scaled to the full hour. `max_missing_per_hour=0` restores the old rule.
  **10-minute AMYs and typical years can change slightly.**
- Snow depth (`agg="last"`) takes the latest reading within the hour rather
  than only the reading at the hour.

## 2.1.0

### Fixed
- `create_tmy(file_type="typical", test_method="zscore")` chose the **coldest**
  year for every month. `z_score` returns a signed value and the selection took
  the smallest, i.e. the most negative. Typical selection now uses its absolute
  value. On Zurich Fluntern 1991-2020 the chosen months moved from rank 1 of 30
  (coldest) in all twelve months to ranks 13-20. **Typical files built with the
  default method in 2.0.5 and earlier should be regenerated.**
- `create_tmy(file_type="extreme_cold", test_method="ks")` chose warm years
  (ranks 20-30 of 30 on the same data): the one-sided KS statistic grows with
  coldness, but the smallest was taken. It now takes the largest.
- `extreme_warm` (both methods) and `extreme_cold` with `zscore` were correct
  and are unchanged.
- The `{month: year}` dictionary holds plain `int`s, not numpy integers.

### Added
- **ISO 15927-4 typical years** (`iso15927.py`). For each calendar month, the
  Finkelstein-Schafer statistic is computed on daily means of dry-bulb
  temperature, global irradiance and relative humidity. Candidates are ranked
  per variable and the ranks summed, and wind speed decides among the three
  best. A month with a gap longer than `max_gap_hours` (default 6) is not a
  candidate; shorter gaps are interpolated. `select_typical_months` returns
  the choice plus a table of statistics, ranks and eligibility.
- **Join smoothing** (`blend_joins`). The 8 h either side of each month join,
  and of December to January, are blended between the two source years' own
  records. This removes the jump at midnight and keeps the diurnal cycle. The
  standard asks for a smooth transition; a straight line across 16 night
  hours removed the night minimum (Fluntern Feb/Mar join: 1.7 degC became
  about 6 degC), so it is kept only as `method="linear"`, and as a fallback
  where the record has no continuation. Temperature, humidity, pressure and
  longwave are smoothed; wind and irradiance are not.
- **Station typical year** (`station_tmy.py`: `build_station_tmy_dataframe`,
  `station_table_to_tmy_epw`). Selection uses measured fields only. After
  assembly:
  - dew point is computed from temperature and RH;
  - direct/diffuse and sky cover are derived as for an AMY, with sky cover at
    night interpolated in every month so one method covers the whole file;
  - pressure is the measured value with short gaps interpolated; months
    without a barometer take the station's own monthly mean from other
    years, or the standard atmosphere when there is none.

  The EPW `year` field holds each month's source year, and COMMENTS 1 reads
  `Period of Record=YYYY-YYYY; Jan=YYYY; ...`.
- **Actual meteorological year** builder and MeteoSwiss adapter (`amy.py`,
  `amy_meteoswiss.py`, `data/amy_diffuse_table.parquet`,
  `scripts/build_amy_diffuse_table.py`), moved here from pyepwmorph 3.3.0,
  where `pyepwmorph.tools.amy` is deprecated from 3.4.0.
- `create_epw(..., period_of_record=(start, end), selected_years={...})`
  writes `Period of Record` and the source year of each month into COMMENTS 1.
- `examples/station_tmy_meteoswiss.py`: Zurich/Fluntern 1991-2020 typical year
  and 2025 actual year from MeteoSwiss hourly files.
- `tests/test_tmy.py`: synthetic data with a known typical, coldest and
  warmest year for every type and method.
- GitHub Actions CI (`ci.yml`): ruff and pytest on Python 3.9-3.13.
- This changelog and `AGENTS.md`.

### Changed
- `create_tmy` defaults to `test_method="iso"` for `file_type="typical"`
  (needs `Day` and `Hour` columns, which ERA5 frames have). The extremes still
  default to `"zscore"`; ISO 15927-4 defines no extreme year. **Typical years
  built from ERA5 change.** `comprehensive_workflow(method=None)` follows the
  same defaults.
- AMY (compared with pyepwmorph 3.3.0):
  - pressure gaps are filled hour by hour (interpolation, then the station
    monthly mean, then the standard atmosphere), where before any missing
    hour replaced the whole year with the standard atmosphere;
  - a missing dew point is computed from RH, so a year with RH but no dew
    point builds;
  - night sky cover is interpolated where longwave is missing, so years in
    which longwave starts part-way no longer get the 99 missing code at night.
- Requires `pyepwmorph>=3.2.0`.
- Ruff rule set made explicit (`E`, `F`, `I`, `B`), with the few existing
  findings fixed (import order, unused imports, a `stacklevel`).
- `release.sh` uses uv instead of conda, as pyepwmorph does. It stops on a
  dirty tree, a branch other than `main`, failing lint or tests, or a missing
  CHANGELOG section; it relocks and builds with `uv build`. `uv.lock` is now
  committed.

### Validation (Zurich/Fluntern, MeteoSwiss SMA hourly)
- 2004-2018 against the climate.onebuilding Fluntern file for the same
  period: the same year in 2 of 12 months. The reference's choice is among
  our three best rank sums in 10 of 12 months, so the wind tiebreak decides
  most differences. That file uses NCEI ISD observations, with modelled
  irradiance and different wind sampling, so exact agreement is not expected.
- 1991-2020: CH2025 `MorphConfig` reads the baseline as 1991-2020 with no
  warnings, and a GWL 2.0 morph runs. Annual mean temperature 9.95 degC
  (record 9.86), GHI 1142 kWh/m2 (record mean 1163), RH 76.9% (76.3).
