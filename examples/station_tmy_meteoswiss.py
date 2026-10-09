"""Typical (ISO 15927-4) and actual years for Zurich/Fluntern from MeteoSwiss open data.

Inputs (not in git, see .gitignore), in examples/station_data/:
    ogd-smn_sma_h_historical_1990-1999.csv ... _2020-2029.csv
        hourly decade files from https://opendatadocs.meteoswiss.ch/ (station SMA)

Outputs in examples/station_result/:
    fluntern_tmy_1991-2020.epw   typical year over the CH2025 reference period
    fluntern_amy_2025.epw        actual year 2025

Station metadata (coordinates, elevation) is written out below; with the
ogd-smn_meta_stations.csv file use amy_meteoswiss.meteoswiss_location instead.
"""

import logging
from pathlib import Path

import pandas as pd

from weather_file_builder import amy, amy_meteoswiss, station_tmy

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "station_data"
OUT_DIR = HERE / "station_result"

LOCATION = dict(
    site="Zurich-Fluntern", province="ZH", country_code="CHE", type="MeteoSwiss-SMA", usaf="06660",
    latitude=47.381003, longitude=8.567194, elevation=604.0,
    utc_offset=1.0,  # standard time, no daylight saving
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    files = sorted(DATA_DIR.glob("ogd-smn_sma_h_historical_*.csv"))
    if not files:
        raise SystemExit(f"put the MeteoSwiss SMA hourly files in {DATA_DIR}")
    table = pd.concat([amy_meteoswiss.read_meteoswiss_ogd(str(f)) for f in files])
    table = table[~table.index.duplicated(keep="first")]
    OUT_DIR.mkdir(exist_ok=True)

    report = station_tmy.station_table_to_tmy_epw(
        table, LOCATION, (1991, 2020), str(OUT_DIR / "fluntern_tmy_1991-2020.epw"),
        source_name="MeteoSwiss SMA", attribution=amy_meteoswiss.ATTRIBUTION,
    )
    print(report.to_text())

    report = amy.station_table_to_epw(
        table, LOCATION, 2025, str(OUT_DIR / "fluntern_amy_2025.epw"),
        source_name="MeteoSwiss SMA", attribution=amy_meteoswiss.ATTRIBUTION,
    )
    print(report.to_text())


if __name__ == "__main__":
    main()
