"""Station TMY (ISO 15927-4) end to end on synthetic station tables. Offline."""

import numpy as np
import pandas as pd
import pytest
from pyepwmorph.tools.io import (
    EPW_COLUMN_NAMES,
    epw_baseline_range,
    read_epw_dataframe,
    read_epw_string,
)

from weather_file_builder import station_tmy

from .test_amy import LOCATION, _hourly_table

YEARS = list(range(2011, 2021))


@pytest.fixture(scope="module")
def table():
    parts = []
    for i, year in enumerate(YEARS):
        t = _hourly_table(year)
        t["temp_C"] += (i % 5) - 2.0  # years differ, 2 of 10 have offset 0
        t["pressure_Pa"] = 94500.0 + 300 * np.sin(np.arange(len(t)) / 200.0) if year <= 2015 else np.nan  # barometer removed in 2016
        parts.append(t)
    out = pd.concat(parts)
    return out[~out.index.duplicated(keep="first")]


@pytest.fixture(scope="module")
def built(table):
    return station_tmy.build_station_tmy_dataframe(table, LOCATION, (2011, 2020))


def test_rows_and_source_years(built):
    epw, report = built
    assert list(epw.columns) == EPW_COLUMN_NAMES
    assert len(epw) == 8760
    for m, y in report.selection.months.items():
        assert set(epw.loc[epw["month"] == m, "year"]) == {y}
    assert not ((epw["month"] == 2) & (epw["day"] == 29)).any()
    assert (epw["totskycvr_tenths"] != 99).all()
    assert (epw["dewpoint_C"].astype(float) <= epw["drybulb_C"].astype(float) + 1e-9).all()


def test_typical_months_come_from_the_middle_offset(built):
    _, report = built
    offsets = {y: (i % 5) - 2.0 for i, y in enumerate(YEARS)}
    assert all(abs(offsets[y]) <= 1 for y in report.selection.months.values())


def test_pressure_filled_from_station_monthly_mean(table, built):
    epw, report = built
    measured = table["pressure_Pa"].dropna()
    for m, y in report.selection.months.items():
        rows = epw[epw["month"] == m].iloc[12:-12]  # away from the blended joins
        if y >= 2016:
            expected = measured[measured.index.month == m].mean()
            assert np.allclose(rows["atmos_Pa"].astype(float), expected, atol=1.0)
    assert any(y >= 2016 for y in report.selection.months.values())  # the fill is exercised
    assert any("station monthly mean" in k for k in report.filled_hours)


def test_written_file_states_period_and_selection(tmp_path, table):
    path = tmp_path / "tmy.epw"
    report = station_tmy.station_table_to_tmy_epw(table, LOCATION, (2011, 2020), str(path), source_name="synthetic")
    lines = read_epw_string(str(path))
    assert epw_baseline_range(lines) == (2011, 2020)
    comments = [line for line in lines if line.startswith("COMMENTS 1")][0]
    for m, y in report.selection.months.items():
        assert f"{station_tmy.iso15927.MONTH_NAMES[m - 1]}={y}" in comments
    df = read_epw_dataframe(str(path))
    assert len(df) == 8760


def test_too_short_period_raises(table):
    with pytest.raises(ValueError, match="too few"):
        station_tmy.build_station_tmy_dataframe(table, LOCATION, (2011, 2015))
