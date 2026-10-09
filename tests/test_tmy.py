"""Month selection in create_tmy, on synthetic data with a known answer."""

import numpy as np
import pandas as pd
import pytest

from weather_file_builder.tmy import create_tmy

N_YEARS = 15
FIRST_YEAR = 2001


def _synthetic(seed: int = 0) -> pd.DataFrame:
    """Hourly temperatures where year k is shifted by k * 0.5 K in every month.

    The shuffle decouples the shift from the calendar year, so a selection
    that works by accident on sorted years would fail here. The middle shift
    is the typical year; the smallest and largest are the extremes.
    """
    rng = np.random.default_rng(seed)
    shifts = rng.permutation(N_YEARS) * 0.5
    frames = []
    for i, year in enumerate(range(FIRST_YEAR, FIRST_YEAR + N_YEARS)):
        idx = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h")
        idx = idx[~((idx.month == 2) & (idx.day == 29))]
        seasonal = 10 - 8 * np.cos(2 * np.pi * (idx.dayofyear - 15) / 365)
        noise = rng.normal(0, 2.0, len(idx))
        frames.append(
            pd.DataFrame(
                {
                    "Temperature": seasonal + shifts[i] + noise,
                    "Year": idx.year,
                    "Month": idx.month,
                }
            )
        )
    data = pd.concat(frames, ignore_index=True)
    data.attrs["shift_by_year"] = dict(zip(range(FIRST_YEAR, FIRST_YEAR + N_YEARS), shifts))
    return data


def _rank_of(data: pd.DataFrame, selected: dict) -> list:
    """1-based rank of each selected month's mean among all years (1 = coldest)."""
    means = data.groupby(["Month", "Year"])["Temperature"].mean()
    return [int((means[m] < means[m][y]).sum()) + 1 for m, y in selected.items()]


@pytest.mark.parametrize("method", ["zscore", "ks"])
def test_typical_picks_a_middle_year(method):
    data = _synthetic()
    _, selected = create_tmy(data, "Temperature", "typical", method)
    ranks = _rank_of(data, selected)
    # With a 0.5 K step and 2 K noise the exact median can move by a rank or
    # two; the coldest/warmest years must never be chosen.
    assert all(5 <= r <= 11 for r in ranks), ranks


@pytest.mark.parametrize("method", ["zscore", "ks"])
def test_extreme_cold_picks_the_coldest_year(method):
    data = _synthetic()
    _, selected = create_tmy(data, "Temperature", "extreme_cold", method)
    assert all(r <= 2 for r in _rank_of(data, selected))


@pytest.mark.parametrize("method", ["zscore", "ks"])
def test_extreme_warm_picks_the_warmest_year(method):
    data = _synthetic()
    _, selected = create_tmy(data, "Temperature", "extreme_warm", method)
    assert all(r >= N_YEARS - 1 for r in _rank_of(data, selected))


def test_typical_is_not_extreme_cold():
    data = _synthetic()
    _, typical = create_tmy(data, "Temperature", "typical", "zscore")
    _, cold = create_tmy(data, "Temperature", "extreme_cold", "zscore")
    assert typical != cold


def test_output_has_one_year_of_rows():
    data = _synthetic()
    tmy, selected = create_tmy(data, "Temperature", "typical", "zscore")
    assert sorted(selected) == list(range(1, 13))
    assert len(tmy) == 8760
