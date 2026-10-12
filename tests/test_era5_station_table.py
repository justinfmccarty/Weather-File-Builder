"""ERA5-Land records as a station table (gap filler for uploads). Offline, synthetic."""

import numpy as np
import pandas as pd
import pvlib
import pytest

from weather_file_builder import converters, station_upload
from weather_file_builder.amy import COLUMN_SPEC

LAT, LON = 47.41, 8.51


def _raw(start="2024-02-27 01:00", hours=24 * 30):
    """CSV-like records as the CDS returns them: valid_time (UTC) and short names."""
    t = pd.date_range(start, periods=hours, freq="h")
    loc = pvlib.location.Location(LAT, LON, altitude=500)
    # radiation is an hourly sum labelled at the end of the hour: use the clear sky at the middle
    ghi = loc.get_clearsky((t - pd.Timedelta(minutes=30)).tz_localize("UTC"))["ghi"].to_numpy() * 0.7
    hour = np.arange(hours) % 24
    return pd.DataFrame({
        "valid_time": t.strftime("%Y-%m-%d %H:%M:%S"),
        "t2m": 278.15 + 4 * np.sin((hour - 9) / 24 * 2 * np.pi),
        "d2m": 274.15 + 0 * hour,
        "sp": 95500.0 + 0 * hour,
        "ssrd": ghi * 3600.0,
        "strd": 300.0 * 3600.0 + 0 * hour,
        "tp": np.where(hour == 5, 0.0012, -1e-9),
        "u10": 3.0 + 0 * hour,  # air moving east: a westerly
        "v10": 0.0 * hour,
    })


def test_units_names_and_timing():
    table = converters.era5_to_station_table(_raw())
    assert str(table["timestamp"].dt.tz) == "UTC"
    assert set(table.columns) - {"timestamp"} <= set(COLUMN_SPEC)
    row = table.iloc[0]
    assert row["pressure_Pa"] == pytest.approx(95500.0)
    assert row["lw_down_Wm2"] == pytest.approx(300.0)
    assert table["dewpoint_C"].iloc[0] == pytest.approx(1.0)
    assert (table["rh_pct"] <= 100).all()
    assert (table["precip_mm"] >= 0).all() and table["precip_mm"].max() == pytest.approx(1.2)
    assert (table["ghi_Wm2"] >= 0).all()
    assert table["wind_speed_ms"].iloc[0] == pytest.approx(3.0)
    assert table["wind_dir_deg"].iloc[0] == pytest.approx(270.0)  # from the west


def test_missing_values_and_leap_day_are_kept():
    raw = _raw()
    raw.loc[10:12, "t2m"] = np.nan
    table = converters.era5_to_station_table(raw)
    assert table["temp_C"].isna().sum() == 3  # not filled with 0
    assert ((table["timestamp"].dt.month == 2) & (table["timestamp"].dt.day == 29)).sum() == 24


def test_station_table_passes_the_upload_contract():
    table = converters.era5_to_station_table(_raw(start="2025-06-01 01:00"))
    report = station_upload.validate_station_table(table, LAT, LON, 1.0, elevation=500)
    assert report.ok, report.to_text()
    assert abs(report.clock_offsets_min["2025-06"]) < 10


@pytest.mark.parametrize("u,v,expected", [(0, -5, 0.0), (-5, 0, 90.0), (0, 5, 180.0), (5, 0, 270.0)])
def test_wind_direction_is_where_the_wind_comes_from(u, v, expected):
    assert converters.wind_direction_from_uv(u, v) == pytest.approx(expected)


def test_era5_to_dataframe_wind_direction_fixed():
    out = converters.era5_to_dataframe(_raw().head(5), latitude=LAT, longitude=LON)
    assert out["Wind Direction"].iloc[0] == pytest.approx(270.0)
