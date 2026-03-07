"""Tests for EPW file generation."""

import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from weather_file_builder.epw import create_epw


def _make_synthetic_year(year: int = 2023) -> pd.DataFrame:
    """Create a synthetic 8760-row weather DataFrame for testing."""
    hours = 8760
    rng = np.random.default_rng(42)

    df = pd.DataFrame()
    dates = pd.date_range(f"{year}-01-01", periods=hours, freq="h")
    # Skip leap day if present
    dates = dates[~((dates.month == 2) & (dates.day == 29))]
    dates = dates[:hours]

    df["Year"] = dates.year
    df["Month"] = dates.month
    df["Day"] = dates.day
    df["Hour"] = dates.hour
    df["Minute"] = 0
    df["Latitude"] = 40.7
    df["Longitude"] = -74.0
    df["Temperature"] = 15.0 + 10.0 * np.sin(np.linspace(0, 2 * np.pi, hours)) + rng.normal(0, 2, hours)
    df["Dew Point"] = df["Temperature"] - 5.0
    df["Relative Humidity"] = 60.0 + rng.normal(0, 10, hours)
    df["Pressure"] = 1013.25 + rng.normal(0, 5, hours)
    df["Wind Speed"] = np.abs(3.0 + rng.normal(0, 1.5, hours))
    df["Wind Direction"] = rng.uniform(0, 360, hours)
    df["GHI"] = np.clip(200 * np.sin(np.linspace(0, 2 * np.pi, hours)), 0, None)
    df["DNI"] = df["GHI"] * 0.7
    df["DHI"] = df["GHI"] * 0.3
    df["IR"] = 300.0 + rng.normal(0, 20, hours)
    df["Cloud Cover"] = rng.uniform(0, 1, hours)
    df["Precipitation"] = np.clip(rng.exponential(0.1, hours), 0, 10)

    return df


def test_create_epw_basic():
    """Test that create_epw writes a valid EPW file."""
    df = _make_synthetic_year(2023)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.epw")
        result = create_epw(
            data=df,
            output_path=path,
            location_name="New York City, NY, US",
            latitude=40.7128,
            longitude=-74.0060,
            timezone=-5,
            elevation=10,
        )

        assert result == path
        assert os.path.isfile(path)

        with open(path, "r") as f:
            lines = f.readlines()

        # EPW must have 8 header lines + 8760 data lines
        assert len(lines) == 8 + 8760

        # First line must start with LOCATION
        assert lines[0].startswith("LOCATION,")
        assert "New York City" in lines[0]

        # Data lines must have 35 comma-separated fields
        data_line = lines[8].strip()
        assert len(data_line.split(",")) == 35


def test_create_epw_wrong_row_count():
    """Test that create_epw rejects non-8760 row DataFrames."""
    df = _make_synthetic_year(2023).head(100)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "bad.epw")
        with pytest.raises(ValueError, match="8760"):
            create_epw(
                data=df,
                output_path=path,
                location_name="Test",
                latitude=0,
                longitude=0,
                timezone=0,
            )
