"""Test lat/lon column integration in converter output."""

import pandas as pd
import numpy as np
import xarray as xr

from weather_file_builder.converters import era5_to_dataframe


def test_era5_to_dataframe_with_latlon():
    """Test that lat/lon columns are added when coordinates are provided."""
    times = pd.date_range("2020-01-01", periods=3, freq="h")
    ds = xr.Dataset(
        {
            "t2m": ("valid_time", [293.15, 294.15, 295.15]),
            "d2m": ("valid_time", [290.15, 291.15, 292.15]),
            "sp": ("valid_time", [101325.0, 101300.0, 101275.0]),
        },
        coords={"valid_time": times},
    )

    output = era5_to_dataframe(ds, latitude=40.7, longitude=-74.0, remove_leap_days=False)

    assert "Latitude" in output.columns
    assert "Longitude" in output.columns
    assert all(output["Latitude"] == 40.7)
    assert all(output["Longitude"] == -74.0)


def test_era5_to_dataframe_without_latlon():
    """Test backward compatibility when coordinates are not provided."""
    times = pd.date_range("2020-01-01", periods=3, freq="h")
    ds = xr.Dataset(
        {
            "t2m": ("valid_time", [293.15, 294.15, 295.15]),
        },
        coords={"valid_time": times},
    )

    output = era5_to_dataframe(ds, remove_leap_days=False)

    assert "Latitude" not in output.columns
    assert "Longitude" not in output.columns
