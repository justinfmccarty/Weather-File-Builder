# weather-file-builder

Python library and CLI that builds EnergyPlus Weather (EPW) files from
weather records: ERA5 reanalysis downloaded from the Copernicus CDS,
or measured station tables. It builds ISO 15927-4 typical years, extreme years
and actual meteorological years (AMY). It is the home for building weather
files from records; pyepwmorph (a dependency) morphs them and owns EPW I/O.
Published on PyPI as `weather-file-builder`.

Main consumer: the Boundary Conditions web app
(github.com/justinfmccarty/boundary-conditions), see "Downstream contract".
Depends on `pyepwmorph` for the EPW writer (`tools.io.Epw`) and `ts_8760`.

## Commands

- `uv run --extra dev pytest` — tests (offline; CDS tests are marked
  `integration` and need `--run-integration`)
- `uv run --extra dev ruff check src tests` — lint
- `./release.sh patch|minor|major` — on the Mac, with uv (no conda): refuses a
  dirty tree, a branch other than `main`, failing lint/tests or a missing
  CHANGELOG section; bumps `pyproject.toml` and `__init__.py`, relocks
  (`uv.lock` is committed), builds, tags and pushes. The tag push triggers
  `publish.yml` (PyPI upload and GitHub Release).

CI (`.github/workflows/ci.yml`) runs ruff and pytest on Python 3.9-3.13.

## Layout (`src/weather_file_builder/`)

- `core.py` — ERA5 download (`download_time_series`, single/multi year) and
  `comprehensive_workflow`
- `converters.py` — ERA5 dataset to the standard frame (`Temperature`,
  `Dew Point`, `Pressure`, `Wind Speed`, `GHI`, ...; 29 Feb dropped)
- `tmy.py` — `create_tmy` on ERA5 frames: `typical` (default `iso`),
  `extreme_warm`, `extreme_cold` (`zscore` default, or `ks`)
- `iso15927.py` — generic ISO 15927-4 selection (`select_typical_months`),
  `assemble_typical_year`, `blend_joins`; callers map their column names to
  roles `temp`, `ghi`, `rh`, `wind`
- `amy.py` — station table contract (docstring), hourly aggregation, gap
  filling, `derive_epw_rows` (dew point, direct/diffuse, sky cover, pressure,
  EPW columns; shared with the station TMY), AMY build and writer
- `amy_meteoswiss.py` — MeteoSwiss ogd-smn adapter
- `station_tmy.py` — station table to ISO 15927-4 typical year EPW
- `data/amy_diffuse_table.parquet` — diffuse-fraction grid, refitted with
  `scripts/build_amy_diffuse_table.py` (needs scikit-learn, not a dependency)
- `epw.py` — `create_epw` via pyepwmorph's `Epw`; writes `Period of Record`
  and the month source years when given
- `variables.py`, `utils.py`, `visualization.py`, CLI entry points

## Invariants

- Typical selection measures closeness in both directions. Extreme selection
  uses the signed statistic. `tests/test_tmy.py` and `tests/test_iso15927.py`
  check every type and method against synthetic data with a known answer;
  keep them passing.
- Typical-year selection uses measured fields only (temperature, global
  irradiance, RH; wind as tiebreak). Derived fields (direct/diffuse, sky
  cover, dew point, filled pressure) are computed after assembly.
- Station timestamps are hour-ending; an EPW row of hour `h` is the interval
  ending `h:00` local standard time. Tables state their clock
  (`table_utc_offset`). No daylight saving.
- Every typical-year EPW states `Period of Record=<first>-<last>` (the
  selection window) in COMMENTS 1, and each row's `year` is its month's
  source year.
- EPWs have 8760 rows and no 29 February.
- Tests never touch the network.
- Python 3.9 is the floor: no `X | Y` unions, no `match`.
- MIT licence. Do not copy code from GPL/AGPL projects.

## Downstream contract (boundary-conditions backend, `tasks/wfb_task.py`)

- `core.download_time_series(latitude, longitude, start_date, end_date, variables)`
- `core.get_era5_variables(groups_or_None)`
- `tmy.create_tmy(data, file_type=..., test_method=...)` returning
  `(frame, {month: year})`; file types `typical`, `extreme_warm`, `extreme_cold`;
  methods `iso`, `zscore`, `ks`
- `epw.create_epw(data, output_path, location_name, latitude, longitude,
  timezone, elevation, source_type, period_of_record=..., selected_years=...)`

Changing any of these is a breaking change for the app: note it in the
CHANGELOG and update the app in the same piece of work.
