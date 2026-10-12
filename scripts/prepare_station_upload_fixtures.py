"""Turn the raw 1-minute Zurich logger CSV into the station-upload test fixtures.

This is the preparation a user is expected to do before uploading (ADR-037 in
the boundary-conditions repo). Each step is a decision about this particular
logger; ``tests/data/station_upload/README.md`` gives the evidence.

    python scripts/prepare_station_upload_fixtures.py \
        weather_data.csv ogd-smn_reh_t_historical_2020-2029.csv tests/data/station_upload

Outputs
-------
station_upload_pass.parquet
    Hourly, UTC, period-ending, contract column names, calendar year 2025 in
    UTC. Gaps longer than 6 h are filled from MeteoSwiss Zurich/Affoltern
    (REH, 2.1 km away) after a monthly correction fitted on the overlap.
    Shorter gaps are left for the builder to interpolate.
station_upload_reject.parquet
    Three short periods (10-16 February 2025, 16-22 June 2025, 8-12 January 2026) of the raw 1-minute
    values with contract column names and nothing else fixed: wall-clock
    timestamps labelled UTC, hPa pressure, sensor junk, wind directions above
    360 degrees and an unknown column. Validation must reject it.
station_upload_fill_log.csv
    Which hours of which variable were filled from Affoltern.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RENAME = {
    "temperature": "temp_C",
    "relative_humidity": "rh_pct",
    "pressure": "pressure_Pa",
    "irradiation": "ghi_Wm2",
    "average_wind_speed": "wind_speed_ms",
    "wind_direction": "wind_dir_deg",
}
REH_CODES = {
    "tre200s0": "temp_C",
    "ure200s0": "rh_pct",
    "prestas0": "pressure_Pa",
    "gre000z0": "ghi_Wm2",
    "fkl010z0": "wind_speed_ms",
    "dkl010z0": "wind_dir_deg",
}
COLUMNS = list(RENAME.values())
#: Plausible ranges for this site; anything outside is sensor junk (inclusive bounds).
RANGES = {
    "temp_C": (-35.0, 45.0),
    "rh_pct": (0.0, 105.0),
    "pressure_Pa": (85000.0, 105000.0),
    "ghi_Wm2": (0.0, 1500.0),
    "wind_speed_ms": (0.0, 60.0),
    "wind_dir_deg": (0.0, 360.0),
}
MIN_MINUTES = 30  # a logger hour counts with at least 30 one-minute readings
MAX_GAP_H = 6
YEAR = 2025


def read_logger(path):
    raw = pd.read_csv(path)
    # The "+00" suffix is wrong: the logger records Swiss wall-clock time. Drop it.
    raw["wall"] = pd.to_datetime(raw["timestamp"].str.slice(0, 19))
    return raw.drop(columns="timestamp").sort_values("wall").set_index("wall")


def read_reh(path):
    r = pd.read_csv(path, sep=";", encoding="latin-1", usecols=["reference_timestamp", *REH_CODES])
    r.index = pd.DatetimeIndex(pd.to_datetime(r.pop("reference_timestamp"), format="%d.%m.%Y %H:%M")).tz_localize("UTC")
    r = r.rename(columns=REH_CODES)
    r["pressure_Pa"] *= 100.0
    return r


def make_reject(raw, out):
    # winter and summer weeks without outages for the clock (daylight saving), and
    # January 2026 for the failing sensor's junk values
    keep = pd.concat([raw.loc["2025-02-10":"2025-02-16"], raw.loc["2025-06-16":"2025-06-22"],
                      raw.loc["2026-01-08":"2026-01-12"]])
    t = keep.rename(columns=RENAME).drop(columns=["max_wind_speed", "rainfall"])
    t.index = t.index.tz_localize("UTC")  # labelled UTC, as the logger exported it
    t = t.reset_index().rename(columns={"wall": "timestamp"})
    t.round(2).to_parquet(out / "station_upload_reject.parquet", index=False)


def clean_logger(raw, log):
    t = raw.loc["2024-10-27":].rename(columns=RENAME)[COLUMNS].copy()
    # wall clock -> UTC; the repeated hour when daylight saving ends cannot be told apart
    utc = t.index.tz_localize("Europe/Zurich", ambiguous="NaT", nonexistent="NaT")
    log.append(f"ambiguous wall-clock minutes dropped: {int(utc.isna().sum())}")
    t.index = utc
    t = t[~t.index.isna()].tz_convert("UTC")
    t["pressure_Pa"] *= 100.0
    wrap = (t["wind_dir_deg"] > 360) & (t["wind_dir_deg"] <= 720)
    t.loc[wrap, "wind_dir_deg"] -= 360.0
    log.append(f"wind directions 360-720 deg wrapped past north: {int(wrap.sum())}")
    fault = t["temp_C"] == -40.0
    t.loc[fault, "temp_C"] = np.nan
    log.append(f"temperature fault value -40.00: {int(fault.sum())}")
    for col, (lo, hi) in RANGES.items():
        bad = (t[col] < lo) | (t[col] > hi)
        t.loc[bad, col] = np.nan
        log.append(f"{col}: {int(bad.sum())} out-of-range minutes set missing")
    t.loc[t["wind_speed_ms"].isna(), "wind_dir_deg"] = np.nan
    return t


def to_hourly(t, min_count):
    """Period-ending hourly aggregates: means, speed-weighted vector mean for direction."""
    grp = dict(rule="h", label="right", closed="right")
    h = t.resample(**grp).mean()
    n = t.resample(**grp).count()
    rad = np.radians(t["wind_dir_deg"])
    w = t["wind_speed_ms"].where(t["wind_dir_deg"].notna())
    u = (w * np.sin(rad)).resample(**grp).mean()
    v = (w * np.cos(rad)).resample(**grp).mean()
    h["wind_dir_deg"] = np.degrees(np.arctan2(u, v)) % 360.0
    h.loc[np.hypot(u, v) < 1e-9, "wind_dir_deg"] = 0.0
    for col in h.columns:
        h.loc[n[col] < min_count, col] = np.nan
    return h


def long_gap_mask(s, max_gap):
    miss = s.isna().to_numpy()
    mask = np.zeros_like(miss)
    i = 0
    while i < len(miss):
        if miss[i]:
            j = i
            while j < len(miss) and miss[j]:
                j += 1
            if j - i > max_gap:
                mask[i:j] = True
            i = j
        else:
            i += 1
    return pd.Series(mask, index=s.index)


def fit_corrections(logger_h, reh_h):
    """Monthly corrections that map Affoltern onto the logger, fitted where both have data.

    Additive for temperature, humidity and pressure; a ratio for wind speed; a
    ratio by month and hour of day for irradiance (the logger's sensor has its
    own diurnal shape); none for wind direction.
    """
    both = logger_h.join(reh_h, rsuffix="_reh", how="inner")
    month = both.index.month
    corr = {}
    for col in ("temp_C", "rh_pct", "pressure_Pa"):
        d = (both[col] - both[f"{col}_reh"]).groupby(month).mean()
        corr[col] = ("add", d.to_dict())
    ok = both["wind_speed_ms"].notna() & both["wind_speed_ms_reh"].notna()
    r = both.loc[ok, "wind_speed_ms"].groupby(month[ok]).sum() / both.loc[ok, "wind_speed_ms_reh"].groupby(month[ok]).sum()
    corr["wind_speed_ms"] = ("mul", r.to_dict())
    ok = both["ghi_Wm2"].notna() & both["ghi_Wm2_reh"].notna()
    keys = [month[ok], both.index.hour[ok]]
    num = both.loc[ok, "ghi_Wm2"].groupby(keys).sum()
    den = both.loc[ok, "ghi_Wm2_reh"].groupby(keys).sum()
    hourly_ratio = (num / den).where(den > 20 * both.loc[ok, "ghi_Wm2_reh"].groupby(keys).count(), np.nan)
    monthly = both.loc[ok, "ghi_Wm2"].groupby(month[ok]).sum() / both.loc[ok, "ghi_Wm2_reh"].groupby(month[ok]).sum()
    corr["ghi_Wm2"] = ("mul_hour", hourly_ratio.clip(0.2, 3.0).to_dict(), monthly.to_dict())
    return corr


def apply_correction(reh_h, corr):
    out = reh_h.copy()
    m = out.index.month
    for col, spec in corr.items():
        if spec[0] == "add":
            out[col] = out[col] + m.map(spec[1]).to_numpy()
        elif spec[0] == "mul":
            out[col] = out[col] * m.map(spec[1]).to_numpy()
        else:
            hr = [spec[1].get((mm, hh), spec[2].get(mm, 1.0)) for mm, hh in zip(m, out.index.hour)]
            out[col] = out[col] * np.nan_to_num(np.asarray(hr, dtype=float), nan=1.0)
    out["rh_pct"] = out["rh_pct"].clip(1.0, 100.0)
    out["ghi_Wm2"] = out["ghi_Wm2"].clip(lower=0.0)
    out["wind_speed_ms"] = out["wind_speed_ms"].clip(lower=0.0)
    return out


def cross_check(logger_h, reh_fit, reh_raw):
    """Error of corrected and uncorrected Affoltern against the logger on hours both have."""
    rows = []
    for col in COLUMNS:
        if col == "wind_dir_deg":
            d = (reh_fit[col] - logger_h[col] + 180) % 360 - 180
            d0 = d
        else:
            d = reh_fit[col] - logger_h[col]
            d0 = reh_raw[col] - logger_h[col]
        rows.append(dict(variable=col, bias_raw=d0.mean(), bias_corrected=d.mean(),
                         rmse_raw=np.sqrt((d0 ** 2).mean()), rmse_corrected=np.sqrt((d ** 2).mean()),
                         hours=int(d.notna().sum())))
    return pd.DataFrame(rows).set_index("variable")


def make_pass(raw, reh, out):
    log = []
    t = clean_logger(raw, log)
    logger_h = to_hourly(t, MIN_MINUTES)
    reh_h = to_hourly(reh.loc["2024-10-26":], 5)  # REH is 10-minute: 5 of 6
    reh_h = reh_h.reindex(logger_h.index.union(reh_h.index))

    fit_window = logger_h.loc[:f"{YEAR}-12-31 23:00"]
    corr = fit_corrections(fit_window, reh_h)
    reh_fit = apply_correction(reh_h, corr)
    check = cross_check(fit_window, reh_fit.reindex(fit_window.index), reh_h.reindex(fit_window.index))

    hours = pd.date_range(f"{YEAR}-01-01 01:00", f"{YEAR + 1}-01-01 00:00", freq="h", tz="UTC")
    year = logger_h.reindex(hours)
    filled = []
    for col in COLUMNS:
        gap = long_gap_mask(year[col], MAX_GAP_H)
        year.loc[gap, col] = reh_fit.loc[hours[gap.to_numpy()], col].to_numpy()
        filled.append(pd.DataFrame({"timestamp": hours[gap.to_numpy()], "variable": col}))
        log.append(f"{col}: {int(gap.sum())} h filled from Affoltern; "
                   f"{int(year[col].isna().sum())} h left missing (short gaps, for the builder)")
    year.loc[year["wind_speed_ms"] == 0, "wind_dir_deg"] = 0.0

    out_t = year.round(2).rename_axis("timestamp").reset_index()
    out_t["timestamp"] = out_t["timestamp"].astype("datetime64[ms, UTC]")
    out_t.to_parquet(out / "station_upload_pass.parquet", index=False)
    pd.concat(filled).to_csv(out / "station_upload_fill_log.csv", index=False)
    log.append(f"written {len(out_t)} hourly rows, {out_t.timestamp.min()} to {out_t.timestamp.max()}")
    return log, corr, check


def main(csv_path, reh_path, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw = read_logger(csv_path)
    make_reject(raw, out)
    log, corr, check = make_pass(raw, read_reh(reh_path), out)
    print("\n".join(log))
    print("\ncorrections:")
    for col, spec in corr.items():
        if spec[0] == "mul_hour":
            print(f"  {col}: ratio by month and hour; monthly ratios",
                  {k: round(v, 2) for k, v in spec[2].items()})
        else:
            print(f"  {col} ({spec[0]}):", {k: round(v, 2) for k, v in spec[1].items()})
    print("\ncorrected Affoltern vs logger (hours with both):")
    print(check.round(2).to_string())


if __name__ == "__main__":
    main(*sys.argv[1:4])
