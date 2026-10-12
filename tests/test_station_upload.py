"""Station-upload contract: validation, partial AMYs, edge hours. Offline.

Two fixtures come from a real 1-minute logger in Zurich (see
``tests/data/station_upload/README.md``):

* ``station_upload_reject.parquet``: the logger's own export with contract
  column names and nothing else fixed. Validation must reject it for the
  right reasons.
* ``station_upload_pass.parquet``: the same logger prepared as a user is
  expected to (UTC, hourly, units, junk removed, long gaps filled from
  MeteoSwiss Zurich/Affoltern). It must pass and build a 2025 AMY.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pyepwmorph.tools.io import read_epw_dataframe

from weather_file_builder import amy, station_tmy, station_upload

from .test_amy import LOCATION, _hourly_table

DATA = Path(__file__).parent / "data" / "station_upload"
SITE = dict(latitude=47.41, longitude=8.51, utc_offset=1.0, elevation=530.0)


def _upload(table: pd.DataFrame) -> pd.DataFrame:
    """A builder-style table (tz-naive UTC index) as an upload (tz-aware ``timestamp`` column)."""
    out = table.copy()
    out.insert(0, "timestamp", out.index.tz_localize("UTC"))
    return out.reset_index(drop=True)


def _validate(table, **kwargs):
    loc = dict(latitude=LOCATION["latitude"], longitude=LOCATION["longitude"], utc_offset=LOCATION["utc_offset"],
               elevation=LOCATION["elevation"])
    loc.update(kwargs.pop("loc", {}))
    return station_upload.validate_station_table(
        table, loc["latitude"], loc["longitude"], loc["utc_offset"], elevation=loc["elevation"], **kwargs
    )


def _codes(report, severity=None):
    return {i.code for i in report.issues if severity is None or i.severity == severity}


@pytest.fixture(scope="module")
def year_table():
    return _hourly_table(2025)


# --------------------------------------------------------------------------- real fixtures


@pytest.fixture(scope="module")
def reject_report():
    table, issues = station_upload.read_station_parquet(DATA / "station_upload_reject.parquet")
    assert issues == []
    return station_upload.validate_station_table(table, **SITE)


def test_raw_logger_export_is_rejected_for_every_problem(reject_report):
    r = reject_report
    assert not r.ok
    errors = _codes(r, "error")
    assert {"unknown_columns", "spacing", "out_of_range", "clock"} <= errors
    messages = " ".join(i.message for i in r.errors)
    assert "wind_gust" in messages
    assert "1 minutes" in messages
    assert "look like hPa" in messages
    assert "wrap past north" in messages
    out_of_range = {i.column for i in r.errors if i.code == "out_of_range"}
    assert {"pressure_Pa", "wind_dir_deg", "temp_C", "rh_pct", "ghi_Wm2"} <= out_of_range


def test_raw_logger_clock_is_local_time_with_daylight_saving(reject_report):
    offsets = reject_report.clock_offsets_min
    # wall-clock timestamps labelled UTC: about +1 h in winter, +2 h in summer, plus the sensor's own lag
    # one week each: a cloudy winter week moves the centroid by +-25 min, so February sits just over
    # the limit (the full months of this logger are 68-92 min in winter and 118-157 min in summer)
    assert offsets["2025-02"] > 45
    assert 120 < offsets["2025-06"] < 190
    assert offsets["2025-06"] - offsets["2025-02"] > 60
    assert "2026-01" not in offsets or offsets["2026-01"] < 100


@pytest.fixture(scope="module")
def pass_table():
    table, issues = station_upload.read_station_parquet(DATA / "station_upload_pass.parquet")
    assert issues == []
    return table


@pytest.fixture(scope="module")
def pass_report(pass_table):
    return station_upload.validate_station_table(pass_table, **SITE)


def test_prepared_logger_file_passes(pass_report):
    r = pass_report
    assert r.ok, r.to_text()
    assert r.step_minutes == 60
    assert r.amy_years == [2025]
    assert r.partial_amy_years == []
    assert r.long_gaps == []
    assert all(abs(v) <= 45 for v in r.clock_offsets_min.values())
    # the logger's sensor is lopsided and reads low in summer: accepted, but said
    assert {"clock_offset", "irradiance_low", "few_tmy_years"} <= _codes(r, "warning")
    assert not r.tmy_ready(min_years=5)
    assert r.to_dict()["ok"] is True


def test_prepared_logger_file_builds_an_amy(pass_table, tmp_path):
    table = station_upload.table_for_builders(pass_table)
    loc = dict(SITE, site="Zurich test logger", country_code="CHE")
    path = tmp_path / "amy.epw"
    report = amy.station_table_to_epw(table, loc, 2025, str(path), empty_months="allow")
    assert not report.partial
    # the table starts at 01:00 UTC on 1 January = 02:00 local: one hour lies outside the record
    assert report.edge_filled_hours == 1
    df = read_epw_dataframe(str(path))
    assert len(df) == 8760
    assert (df["drybulb_C"].astype(float) < 50).all()
    first, second = df["drybulb_C"].astype(float).iloc[:2]
    assert abs(first - second) < 2.0  # the edge hour joins the record without a jump


# --------------------------------------------------------------------------- reading


def test_parquet_schema_is_checked_before_reading(tmp_path, year_table):
    good = _upload(year_table.head(48))
    naive = good.assign(timestamp=good["timestamp"].dt.tz_localize(None))
    zurich = good.assign(timestamp=good["timestamp"].dt.tz_convert("Europe/Zurich"))
    text = good.assign(timestamp=good["timestamp"].astype(str))
    for name, frame, code in (("naive", naive, "timestamp_tz"), ("zurich", zurich, "timestamp_tz"),
                              ("text", text, "timestamp_type")):
        path = tmp_path / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        table, issues = station_upload.read_station_parquet(path)
        assert table is None and [i.code for i in issues] == [code], name
    path = tmp_path / "good.parquet"
    good.to_parquet(path, index=False)
    table, issues = station_upload.read_station_parquet(path)
    assert issues == [] and len(table) == 48
    table, issues = station_upload.read_station_parquet(path, max_rows=10)
    assert table is None and issues[0].code == "too_many_rows"
    (tmp_path / "junk.parquet").write_text("timestamp,temp_C\n")
    assert station_upload.read_station_parquet(tmp_path / "junk.parquet")[1][0].code == "not_parquet"


# --------------------------------------------------------------------------- contract checks


def test_synthetic_year_passes(year_table):
    r = _validate(_upload(year_table))
    assert r.ok, r.to_text()
    assert r.amy_years == [2025]
    assert all(abs(v) < 10 for v in r.clock_offsets_min.values())


def test_columns(year_table):
    up = _upload(year_table.head(24 * 10))
    r = _validate(up.drop(columns=["wind_dir_deg"]))
    assert any(i.code == "missing_required" and i.column == "wind_dir_deg" for i in r.errors)
    r = _validate(up.drop(columns=["rh_pct"]))
    assert any(i.code == "missing_required" for i in r.errors)
    r = _validate(up.assign(Temperature=1.0))
    assert "unknown_columns" in _codes(r, "error")
    r = _validate(up.assign(wind_speed_ms="calm"))
    assert "not_numeric" in _codes(r, "error")


@pytest.mark.parametrize("step,ok", [(5, False), (10, True), (15, True), (30, True), (60, True)])
def test_spacing(step, ok):
    index = pd.date_range("2025-06-01 00:00", "2025-06-15 00:00", freq=f"{step}min")[1:]
    hourly = _hourly_table(2025).reindex(index.ceil("h"))
    hourly.index = index
    r = _validate(_upload(hourly))
    assert ("spacing" not in _codes(r)) is ok


def test_off_grid_timestamps_are_rejected(year_table):
    up = _upload(year_table.head(24 * 10))
    up.loc[5, "timestamp"] += pd.Timedelta(minutes=7)
    assert "irregular" in _codes(_validate(up), "error")
    up = _upload(year_table.head(24 * 10))
    up.loc[5, "timestamp"] = up.loc[4, "timestamp"]
    assert "timestamp_duplicate" in _codes(_validate(up), "error")


def test_ranges_and_tolerances(year_table):
    up = _upload(year_table.head(24 * 10))
    r = _validate(up.assign(rh_pct=np.where(np.arange(len(up)) == 3, 102.0, up["rh_pct"])))
    assert r.ok and "tolerated_range" in _codes(r, "warning")
    r = _validate(up.assign(ghi_Wm2=np.where(up["ghi_Wm2"] == 0, -4.0, up["ghi_Wm2"])))
    assert r.ok and "tolerated_range" in _codes(r, "warning")
    r = _validate(up.assign(ghi_Wm2=np.where(np.arange(len(up)) == 3, -20.0, up["ghi_Wm2"])))
    assert "out_of_range" in _codes(r, "error")
    r = _validate(up.assign(temp_C=up["temp_C"] + 273.15))
    assert "kelvin" in " ".join(i.message for i in r.errors)
    r = _validate(up.assign(rh_pct=up["rh_pct"] / 100.0))
    assert "unit_suspect" in _codes(r, "warning")


def test_half_hour_time_zone_is_rejected(year_table):
    r = _validate(_upload(year_table.head(24 * 10)), loc=dict(utc_offset=5.5))
    assert "half_hour_zone" in _codes(r, "error")


# --------------------------------------------------------------------------- clock


@pytest.mark.parametrize("shift_h", [1, 2, -1])
def test_clock_errors_are_rejected(year_table, shift_h):
    up = _upload(year_table)
    up["timestamp"] += pd.Timedelta(hours=shift_h)  # labels an hour late or early
    r = _validate(up)
    assert "clock" in _codes(r, "error")
    assert all(abs(v - 60 * shift_h) < 15 for v in r.clock_offsets_min.values())


def test_start_labelled_hourly_data_is_rejected(year_table):
    up = _upload(year_table)
    up["timestamp"] -= pd.Timedelta(hours=1)  # interval start instead of end
    assert "clock" in _codes(_validate(up), "error")


def _ten_minute_june(delay_min):
    """Two June weeks of 10-minute data whose irradiance lags the sun by *delay_min*."""
    import pvlib

    index = pd.date_range("2025-06-01 00:10", "2025-06-15 00:00", freq="10min")
    loc = pvlib.location.Location(LOCATION["latitude"], LOCATION["longitude"], altitude=LOCATION["elevation"])
    mid = (index - pd.Timedelta(minutes=5 + delay_min)).tz_localize("UTC")
    ghi = loc.get_clearsky(mid)["ghi"].to_numpy() * 0.8
    table = pd.DataFrame(dict(temp_C=18.0, rh_pct=60.0, ghi_Wm2=ghi, wind_speed_ms=2.0, wind_dir_deg=220.0),
                         index=index)
    return _upload(table)


def test_clock_tolerance():
    assert abs(_validate(_ten_minute_june(0)).clock_offsets_min["2025-06"]) < 3
    late = _ten_minute_june(30)
    r = _validate(late)
    assert 25 < r.clock_offsets_min["2025-06"] < 35
    assert r.ok and "clock_offset" in _codes(r, "warning")
    assert "clock" in _codes(_validate(late, clock_tolerance_min=20), "error")


# --------------------------------------------------------------------------- gaps and AMY readiness


def test_gaps_are_reported_not_rejected(year_table):
    t = year_table.copy()
    t.loc["2025-04-10 00:00":"2025-04-10 11:00", "temp_C"] = np.nan  # 12 h
    t.loc["2025-05-02 00:00":"2025-05-02 03:00", "temp_C"] = np.nan  # 4 h, interpolated
    r = _validate(_upload(t))
    assert r.ok
    assert [g["column"] for g in r.long_gaps] == ["temp_C"]
    assert r.long_gaps[0]["hours"] == 12
    assert r.short_gap_hours["temp_C"] == 4
    assert r.month_status["2025-04"]["temp_C"] == "gaps"
    assert r.month_status["2025-05"]["temp_C"] == "complete"
    assert r.amy_years == []
    assert "long_gaps" in _codes(r, "warning")
    assert 2025 not in r.tmy_candidates[4] and 2025 in r.tmy_candidates[5]


def test_one_missing_reading_per_hour_is_tolerated():
    index = pd.date_range("2025-01-01 00:10", "2026-01-01 00:00", freq="10min")
    base = _hourly_table(2025, with_sunshine=False).drop(columns="precip_mm")
    t = base.reindex(index.ceil("h"))
    t.index = index
    t = t.drop(index=t.index[3::6])  # one 10-minute reading missing in every hour
    r = _validate(_upload(t))
    assert r.ok and r.long_gaps == [] and r.amy_years == [2025]


def test_empty_months_make_a_partial_amy(year_table, tmp_path):
    t = year_table.copy()
    # a UTC end label is the local (UTC+1) start of the same hour, so months follow the labels
    lst = t.index
    t.loc[lst.month == 3, "temp_C"] = np.nan
    t.loc[lst.month == 7, "ghi_Wm2"] = np.nan
    t.loc[(lst.month == 9) | (lst.month == 10), ["wind_speed_ms", "wind_dir_deg"]] = np.nan
    r = _validate(_upload(t))
    assert r.month_status["2025-03"]["temp_C"] == "empty"
    assert r.month_status["2025-03"]["humidity"] == "complete"
    assert r.amy_years == [2025] and r.partial_amy_years == [2025]

    with pytest.raises(ValueError, match="gaps longer"):
        amy.build_amy_dataframe(t, LOCATION, 2025)
    epw, report = amy.build_amy_dataframe(t, LOCATION, 2025, empty_months="allow")
    assert report.partial
    assert report.empty_months == {"temp_C": [3], "ghi_Wm2": [7], "wind_speed_ms": [9, 10], "wind_dir_deg": [9, 10]}
    m = epw["month"]
    assert (epw.loc[m == 3, "drybulb_C"] == 99.9).all() and (epw.loc[m == 3, "dewpoint_C"] == 99.9).all()
    assert (epw.loc[m == 3, "relhum_percent"] != 999).all()  # RH was measured
    assert (epw.loc[m == 4, "drybulb_C"] != 99.9).all()
    for col, code in (("glohorrad_Whm2", 9999), ("dirnorrad_Whm2", 9999), ("difhorrad_Whm2", 9999),
                      ("totskycvr_tenths", 99)):
        assert (epw.loc[m == 7, col] == code).all(), col
        assert not (epw.loc[m == 6, col] == code).any(), col
    assert (epw.loc[m.isin([9, 10]), "windspd_ms"] == 999).all()
    assert (epw.loc[m.isin([9, 10]), "winddir_deg"] == 999).all()
    assert (epw.loc[m == 8, "windspd_ms"] != 999).all()

    path = tmp_path / "partial.epw"
    amy.write_amy_epw(str(path), epw, LOCATION, report)
    header = path.read_text().splitlines()[6]
    assert header.startswith('COMMENTS 2,"PARTIAL')
    assert "temperature Mar" in header and "global irradiance Jul" in header
    assert len(read_epw_dataframe(str(path))) == 8760


def test_a_month_with_some_values_and_a_long_gap_still_raises(year_table):
    t = year_table.copy()
    t.loc["2025-03-05":"2025-03-08", "temp_C"] = np.nan
    with pytest.raises(ValueError, match="gaps longer"):
        amy.build_amy_dataframe(t, LOCATION, 2025, empty_months="allow")


def test_edge_hours_outside_the_record(year_table):
    # the table starts 3 h late: within the allowance (6 h + 1 h for UTC+1)
    epw, report = amy.build_amy_dataframe(year_table.iloc[3:], LOCATION, 2025)
    assert report.edge_filled_hours == 3
    assert np.isfinite(epw["drybulb_C"].astype(float)).all()
    with pytest.raises(ValueError, match="starts 10 h"):
        amy.build_amy_dataframe(year_table.iloc[10:], LOCATION, 2025)
    # far west: 31 December local evening lies in next year's UTC; up to 16 h allowed at UTC-10
    west = dict(LOCATION, longitude=-155.0, latitude=19.7, utc_offset=-10.0)
    # the table's last label, 23:00 UTC on 31 December, ends the hour 12:00-13:00 local: 11 h follow
    epw, report = amy.build_amy_dataframe(_hourly_table(2025), west, 2025)
    assert report.edge_filled_hours == 11


def test_station_tmy_accepts_five_years():
    parts = []
    for i, year in enumerate(range(2016, 2021)):
        t = _hourly_table(year)
        t["temp_C"] += i - 2.0
        parts.append(t)
    table = pd.concat(parts)
    table = table[~table.index.duplicated(keep="first")]
    with pytest.raises(ValueError, match="need 10"):
        station_tmy.build_station_tmy_dataframe(table, LOCATION, (2016, 2020))
    epw, report = station_tmy.build_station_tmy_dataframe(table, LOCATION, (2016, 2020), min_years=5)
    assert len(epw) == 8760
    assert any("fewer than 10" in n for n in report.selection.notes)


def test_describe_contract_lists_ranges():
    spec = station_upload.describe_contract()
    assert spec.loc["wind_dir_deg", "required"] == "yes"
    assert spec.loc["rh_pct", "range"] == "[0, 105]"
