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


def test_create_epw_writes_period_of_record(tmp_path):
    import numpy as np
    import pandas as pd
    from pyepwmorph.tools.io import epw_baseline_range, read_epw_string

    from weather_file_builder.epw import create_epw

    data = pd.DataFrame({"Year": 2015, "Temperature": np.full(8760, 10.0), "Pressure": 950.0})
    path = tmp_path / "x.epw"
    create_epw(data, str(path), "Somewhere", 47.0, 8.0, 1, 500.0,
               period_of_record=(1991, 2020), selected_years={m: 2000 + m for m in range(1, 13)})
    lines = read_epw_string(str(path))
    assert epw_baseline_range(lines) == (1991, 2020)
    assert "Jan=2001; Feb=2002" in [line for line in lines if line.startswith("COMMENTS 1")][0]


def test_create_epw_writes_extraterrestrial_radiation(tmp_path):
    """Both extraterrestrial columns are filled: pyepwmorph needs them to split
    morphed global radiation, and at 0 it returned no direct normal at all."""
    from pyepwmorph.tools.io import Epw

    path = str(tmp_path / "etr.epw")
    create_epw(
        data=_make_synthetic_year(2023), output_path=path, location_name="Zurich",
        latitude=47.41, longitude=8.51, timezone=1, elevation=440,
    )
    df = Epw(path).dataframe
    eth = df["exthorrad_Whm2"].to_numpy(dtype=float)
    etn = df["extdirrad_Whm2"].to_numpy(dtype=float)
    # both are zero at night; by day the normal value is near the solar constant
    assert eth[0] == 0 and etn[0] == 0 and eth.max() < 1420
    day = etn > 0
    assert (etn[day] > 1300).all() and etn.max() < 1420
    assert (eth[~day] == 0).all() and 4300 < day.sum() < 4500
    # annual horizontal total at 47 N is about 2600 kWh/m2 (AMY writer: 2604)
    assert 2500 < eth.sum() / 1000 < 2700
    # the hour-ending 13:00 row is near solar noon in June, beyond any other hour of the day
    june = df[(df["month"] == 6) & (df["day"] == 21)]
    assert int(june.loc[june["exthorrad_Whm2"].idxmax(), "hour"]) == 13
