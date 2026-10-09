"""ISO 15927-4 month selection and join smoothing, on synthetic data with known answers."""

import numpy as np
import pandas as pd
import pytest

from weather_file_builder import iso15927
from weather_file_builder.tmy import create_tmy

YEARS = list(range(2001, 2016))  # 15 years


def _hours(years):
    idx = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31 23:00", freq="h")
    return idx[~((idx.month == 2) & (idx.day == 29))]


def _frame(shift_by_year, seed=0, noise=1.0):
    """Daily-varying weather where each year is offset by its shift in every variable."""
    rng = np.random.default_rng(seed)
    idx = _hours(YEARS)
    shift = idx.year.map(shift_by_year).to_numpy(dtype=float)
    doy = ((idx.month - 1) * 30.42 + idx.day).to_numpy()  # same in leap and common years
    hod = idx.hour.to_numpy()
    day_noise = rng.normal(0, noise, len(idx) // 24 + 1)[np.arange(len(idx)) // 24]
    return pd.DataFrame(
        {
            "T": 10 - 8 * np.cos(2 * np.pi * (doy - 15) / 365) + 3 * np.sin(2 * np.pi * (hod - 9) / 24) + shift + day_noise,
            "G": np.clip(400 * np.sin(np.pi * (hod - 6) / 12), 0, None) * (1 + 0.05 * shift),
            "RH": 75 - 2 * shift + day_noise,
            "W": np.full(len(idx), 3.0),
            "D": np.full(len(idx), 200.0),
        },
        index=idx,
    )


COLS = {"temp": "T", "ghi": "G", "rh": "RH", "wind": "W"}


def test_typical_year_is_the_middle_one():
    rng = np.random.default_rng(1)
    shifts = dict(zip(YEARS, rng.permutation(len(YEARS)) - 7.0))  # -7 ... +7, 0 is typical
    sel = iso15927.select_typical_months(_frame(shifts, noise=0.3), COLS)
    picked = {m: shifts[y] for m, y in sel.months.items()}
    assert all(abs(v) <= 1 for v in picked.values()), picked


def test_wind_breaks_ties_among_the_best_three():
    shifts = {y: 0.0 for y in YEARS}
    data = _frame(shifts, noise=0.0)  # every year identical: all rank sums tie
    windy = {y: 3.0 + 0.1 * i for i, y in enumerate(YEARS)}  # mean of the three best is not one of them
    data["W"] = data.index.year.map(windy).to_numpy()
    sel = iso15927.select_typical_months(data, COLS)
    best3 = YEARS[:3]  # all tied, so the first three in year order go to the tiebreak
    mean_all = np.mean(list(windy.values()))
    expected = min(best3, key=lambda y: abs(windy[y] - mean_all))
    assert set(sel.months.values()) == {expected}


def test_finkelstein_schafer_rewards_distribution_not_only_mean():
    """Two candidates with the same monthly mean: the one with the right spread wins."""
    rng = np.random.default_rng(3)
    idx = _hours(YEARS)
    day = np.arange(len(idx)) // 24
    daily = rng.normal(10, 3, day.max() + 1)
    t = daily[day]
    bimodal_year = 2005
    in_bad = idx.year == bimodal_year
    days_bad = np.unique(day[in_bad])
    alt = np.where(np.arange(len(days_bad)) % 2 == 0, 10 - 6, 10 + 6)  # mean 10, spread too wide
    t[in_bad] = alt[np.searchsorted(days_bad, day[in_bad])]
    data = pd.DataFrame({"T": t}, index=idx)
    sel = iso15927.select_typical_months(data, {"temp": "T"})
    table = sel.table
    for m in range(1, 13):
        fs = table.loc[m]["fs_temp"]
        assert fs[bimodal_year] > fs.median()
        assert sel.months[m] != bimodal_year


def test_month_with_long_gap_is_not_a_candidate():
    data = _frame({y: 0.0 for y in YEARS})
    data.loc["2003-07-10 00:00":"2003-07-10 09:00", "G"] = np.nan  # 10 h
    data.loc["2004-07-10 00:00":"2004-07-10 03:00", "G"] = np.nan  # 4 h: interpolated
    sel = iso15927.select_typical_months(data, COLS, required=("D",))
    assert 2003 not in sel.eligible_years[7]
    assert 2004 in sel.eligible_years[7]
    assert any("Jul 2003" in n for n in sel.notes)


def test_too_few_years_raises():
    data = _frame({y: 0.0 for y in YEARS})
    with pytest.raises(ValueError, match="too few"):
        iso15927.select_typical_months(data, COLS, period=(2001, 2005))
    sel = iso15927.select_typical_months(data, COLS, period=(2001, 2005), min_years=5)
    assert sel.period == (2001, 2005)
    assert sel.comments().startswith("Period of Record=2001-2005; Jan=")


def test_assemble_keeps_real_timestamps_and_8760_rows():
    data = _frame({y: 0.0 for y in YEARS})
    months = {m: 2001 + m for m in range(1, 13)}
    rows = iso15927.assemble_typical_year(data, months)
    assert len(rows) == 8760
    assert rows.index[0] == pd.Timestamp("2002-01-01 00:00")
    assert rows.index[-1] == pd.Timestamp("2013-12-31 23:00")
    assert (rows.groupby(rows.index.month).apply(lambda g: g.index.year.unique()[0]) == pd.Series(months)).all()


def _step_source():
    """Two years of hourly data: a smooth diurnal cycle, 2001 at 0 degC and 2002 at 10 degC."""
    idx = _hours([2001, 2002])
    base = 3 * np.sin(2 * np.pi * (idx.hour - 9) / 24)
    level = np.where(idx.year == 2001, 0.0, 10.0)
    return pd.DataFrame({"T": base + level}, index=idx)


def test_crossfade_removes_the_jump_and_keeps_the_diurnal_cycle():
    src = _step_source()
    rows = iso15927.assemble_typical_year(src, {m: (2001 if m <= 6 else 2002) for m in range(1, 13)})
    out, fallbacks = iso15927.blend_joins(rows, src, ["T"], hours=8, wrap=False)
    j = int(np.flatnonzero(rows.index.month == 7)[0])
    # the 10 K jump at midnight is gone: hour-to-hour change stays small
    assert np.abs(np.diff(out["T"].to_numpy()[j - 10:j + 10])).max() < 2.5
    # outside the window nothing changes
    assert out["T"].iloc[j - 9] == rows["T"].iloc[j - 9]
    assert out["T"].iloc[j + 8] == rows["T"].iloc[j + 8]
    # inside, the value stays between the two years' own records at that hour
    mid = out["T"].iloc[j]
    assert rows["T"].iloc[j] - 10 - 1e-9 <= mid <= rows["T"].iloc[j] + 1e-9
    # joins inside one source year are unchanged by a crossfade
    k = int(np.flatnonzero(rows.index.month == 3)[0])
    assert np.allclose(out["T"].iloc[k - 8:k + 8], rows["T"].iloc[k - 8:k + 8])
    assert fallbacks == {}


def test_linear_and_fallback_when_no_continuation():
    src = _step_source()
    rows = iso15927.assemble_typical_year(src, {m: (2001 if m <= 6 else 2002) for m in range(1, 13)})
    lin, _ = iso15927.blend_joins(rows, src, ["T"], hours=8, method="linear", wrap=False)
    j = int(np.flatnonzero(rows.index.month == 7)[0])
    seg = lin["T"].to_numpy()[j - 9:j + 9]
    assert np.allclose(np.diff(seg), np.diff(seg)[0])  # a straight line between the anchors
    # December 2002 -> January 2001 wraps; 2003 is not in the record, so it falls back
    _, fallbacks = iso15927.blend_joins(rows, src, ["T"], hours=8, wrap=True)
    assert fallbacks == {"T": 1}


def _era5_like():
    data = _frame({y: float(i % 5 - 2) for i, y in enumerate(YEARS)}, noise=0.5)
    out = pd.DataFrame(
        {
            "Year": data.index.year, "Month": data.index.month, "Day": data.index.day, "Hour": data.index.hour,
            "Minute": 0, "Temperature": data["T"].to_numpy(), "GHI": data["G"].to_numpy(),
            "Wind Speed": data["W"].to_numpy(), "Wind Direction": data["D"].to_numpy(),
            "Pressure": 950.0,
        }
    )
    out["Dew Point"] = out["Temperature"] - 4.0
    from weather_file_builder.converters import calculate_relative_humidity

    out["Relative Humidity"] = calculate_relative_humidity(out["Temperature"], out["Dew Point"])
    return out


def test_create_tmy_defaults_to_iso_for_typical():
    data = _era5_like()
    tmy, selected = create_tmy(data)
    assert len(tmy) == 8760
    assert sorted(selected) == list(range(1, 13))
    for m, y in selected.items():
        assert set(tmy.loc[tmy["Month"] == m, "Year"]) == {y}
    assert (tmy["Dew Point"] <= tmy["Temperature"] + 1e-9).all()
    assert tmy["Relative Humidity"].between(0, 100).all()


def test_create_tmy_iso_rejects_extremes():
    with pytest.raises(ValueError, match="only a typical year"):
        create_tmy(_era5_like(), file_type="extreme_warm", test_method="iso")
