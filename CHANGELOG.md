# Changelog

All notable changes to weather-file-builder. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions before
2.1.0 are described only by their git tags.

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
