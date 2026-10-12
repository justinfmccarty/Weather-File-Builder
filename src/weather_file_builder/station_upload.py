"""Validate a user-prepared station table before building an AMY or a typical year.

The Boundary Conditions app accepts weather-station uploads under a strict
contract (boundary-conditions ADR-037) and rejects anything else with a
report. Nothing is repaired or guessed here: the user fixes the file and
uploads it again.

Contract
--------
* One table (Parquet for uploads) with a ``timestamp`` column of a timestamp
  type in UTC. Each timestamp marks the **end** of its averaging interval.
* Every other column is named, and in the unit of,
  :data:`weather_file_builder.amy.COLUMN_SPEC`. Unknown columns are errors.
  Required: ``temp_C``, ``rh_pct`` or ``dewpoint_C``, ``ghi_Wm2``,
  ``wind_speed_ms`` and ``wind_dir_deg``.
* Regular spacing of 10, 15, 30 or 60 minutes, on the clock grid (rows may be
  absent; absent and empty rows are both gaps).
* Values inside :data:`RANGES`. A few tolerances are accepted with a warning:
  irradiance down to -10 W/m2 (written as 0) and relative humidity up to 105 %
  (written as 100).
* The clock is checked against the sun: in every month with enough data, the
  irradiance-weighted mean time of day (interval mid-points) must lie within
  ``clock_tolerance_min`` of solar noon. A whole-hour or daylight-saving error
  shows up as 50 minutes or more.

Gaps are **reported, not rejected**, here: whether a gap blocks depends on
what is built. An hour counts when at most ``max_missing_per_hour`` readings
are missing; runs of missing hours up to ``max_gap_hours`` are interpolated by
the builders. For an AMY, every month of the chosen year must have each
required variable either complete (up to such short gaps) or entirely empty
(:attr:`StationValidationReport.amy_years`). For a typical year, each calendar
month needs enough complete candidate years
(:attr:`StationValidationReport.tmy_candidates`).
"""

import datetime
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pvlib

from . import amy

#: Spacings (minutes) the app accepts.
ALLOWED_STEPS = (10, 15, 30, 60)
#: Required variables; ``humidity`` is ``rh_pct`` or ``dewpoint_C``.
REQUIRED = ("temp_C", "humidity", "ghi_Wm2", "wind_speed_ms", "wind_dir_deg")
_UTC_NAMES = {"UTC", "Etc/UTC", "Etc/UCT", "UCT", "Z", "+00:00", "Etc/GMT", "GMT", "utc"}

#: Physical range per column (inclusive). ``None`` bounds are open. Values
#: inside ``accept`` but outside ``valid`` are accepted with a warning.
RANGES: Dict[str, Dict[str, Tuple[Optional[float], Optional[float]]]] = {
    "temp_C": dict(valid=(-90.0, 60.0)),
    "dewpoint_C": dict(valid=(-90.0, 40.0)),
    "rh_pct": dict(valid=(0.0, 100.0), accept=(0.0, 105.0)),
    "pressure_Pa": dict(valid=(30000.0, 110000.0)),
    "ghi_Wm2": dict(valid=(0.0, 1500.0), accept=(-10.0, 1500.0)),
    "dhi_Wm2": dict(valid=(0.0, 1000.0), accept=(-10.0, 1000.0)),
    "dni_Wm2": dict(valid=(0.0, 1400.0), accept=(-10.0, 1400.0)),
    "lw_down_Wm2": dict(valid=(40.0, 700.0)),
    "sunshine_min": dict(valid=(0.0, None)),  # upper bound: the interval length
    "wind_speed_ms": dict(valid=(0.0, 75.0)),
    "wind_dir_deg": dict(valid=(0.0, 360.0)),
    "precip_mm": dict(valid=(0.0, None)),  # upper bound: 5 mm per minute of interval
    "snow_depth_cm": dict(valid=(0.0, 1500.0)),
    "total_sky_cover_tenths": dict(valid=(0.0, 10.0)),
    "opaque_sky_cover_tenths": dict(valid=(0.0, 10.0)),
    "visibility_km": dict(valid=(0.0, 300.0)),
    "ceiling_height_m": dict(valid=(0.0, 30000.0)),
}

#: Below this many days with sunshine in a month the clock is not checked for that month.
_CLOCK_MIN_DAYS = 5
#: Irradiance below this (W/m2) is ignored by the clock check (night-time sensor offsets).
_CLOCK_MIN_WM2 = 5.0
#: Months whose offset exceeds this (minutes) get a warning even when they pass.
_CLOCK_WARN_MIN = 20.0


@dataclass
class Issue:
    """One finding. ``severity`` is ``"error"`` (rejects the upload) or ``"warning"``."""

    code: str
    severity: str
    message: str
    column: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StationValidationReport:
    """Everything the app shows after an upload. Times are local standard time unless stated."""

    issues: List[Issue] = field(default_factory=list)
    rows: int = 0
    columns: List[str] = field(default_factory=list)
    step_minutes: Optional[int] = None
    first_utc: Optional[str] = None
    last_utc: Optional[str] = None
    utc_offset: float = 0.0
    #: "YYYY-MM" (UTC) -> irradiance-weighted mean time minus solar noon, minutes.
    clock_offsets_min: Dict[str, float] = field(default_factory=dict)
    #: Runs of missing hours longer than ``max_gap_hours``: column, start, end, hours.
    long_gaps: List[Dict[str, Any]] = field(default_factory=list)
    #: Column -> hours in gaps short enough to interpolate.
    short_gap_hours: Dict[str, int] = field(default_factory=dict)
    #: "YYYY-MM" -> variable -> "complete" | "empty" | "gaps" | "outside".
    month_status: Dict[str, Dict[str, str]] = field(default_factory=dict)
    #: Years that can be built as an AMY (Jan-Dec, local standard time).
    amy_years: List[int] = field(default_factory=list)
    #: Of those, years where some variable is empty for whole months (partial AMY).
    partial_amy_years: List[int] = field(default_factory=list)
    #: Calendar month (1-12) -> years complete in every required variable.
    tmy_candidates: Dict[int, List[int]] = field(default_factory=dict)

    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        """No errors: the table meets the contract (gaps are judged per build)."""
        return not self.errors

    def tmy_ready(self, min_years: int = 5) -> bool:
        """Whether every calendar month has at least *min_years* complete candidate years."""
        return self.ok and all(len(self.tmy_candidates.get(m, [])) >= min_years for m in range(1, 13))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        d["tmy_candidates"] = {str(k): v for k, v in self.tmy_candidates.items()}
        return d

    def to_text(self) -> str:
        lines = [
            f"{'OK' if self.ok else 'REJECTED'}: {self.rows} rows, step {self.step_minutes} min, "
            f"{self.first_utc} to {self.last_utc} (UTC)"
        ]
        for issue in self.issues:
            lines.append(f"[{issue.severity}] {issue.message}")
        if self.long_gaps:
            lines.append(f"{len(self.long_gaps)} gaps longer than the interpolation limit, for example:")
            for g in self.long_gaps[:10]:
                lines.append(f"  {g['column']}: {g['hours']} h from {g['start']}")
        if self.ok:
            lines.append("AMY years: " + (", ".join(map(str, self.amy_years)) or "none"))
            counts = ", ".join(f"{amy._MONTH_ABBR[m - 1]} {len(v)}" for m, v in sorted(self.tmy_candidates.items()))
            lines.append("typical-year candidates per month: " + counts)
        return "\n".join(lines)


# --------------------------------------------------------------------------- reading


def read_station_parquet(path, max_rows: int = 1_200_000) -> Tuple[Optional[pd.DataFrame], List[Issue]]:
    """Read an uploaded Parquet file after checking its schema and size.

    Returns ``(table, issues)``; *table* is ``None`` when the file cannot be
    used at all. The row count is checked from the file metadata before any
    data is read, so a small file that expands to millions of rows is refused
    cheaply (``max_rows`` default: 22 years of 10-minute data).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    issues: List[Issue] = []
    try:
        pf = pq.ParquetFile(path)
    except Exception as exc:  # not Parquet, truncated, encrypted
        return None, [Issue("not_parquet", "error", f"the file could not be read as Parquet ({exc})")]
    n = pf.metadata.num_rows
    if n > max_rows:
        return None, [Issue("too_many_rows", "error", f"the file has {n:,} rows; at most {max_rows:,} are accepted",
                            details=dict(rows=n, max_rows=max_rows))]
    schema = pf.schema_arrow
    if "timestamp" not in schema.names:
        issues.append(Issue("no_timestamp", "error", "no 'timestamp' column"))
    else:
        typ = schema.field("timestamp").type
        if not pa.types.is_timestamp(typ):
            issues.append(Issue("timestamp_type", "error",
                                f"'timestamp' must be a Parquet timestamp in UTC, not {typ}", column="timestamp"))
        elif typ.tz is None:
            issues.append(Issue("timestamp_tz", "error",
                                "'timestamp' has no time zone; store it as UTC (tz-aware)", column="timestamp"))
        elif typ.tz not in _UTC_NAMES:
            issues.append(Issue("timestamp_tz", "error",
                                f"'timestamp' is in time zone {typ.tz}; convert it to UTC", column="timestamp"))
    if issues:
        return None, issues
    return pf.read().to_pandas(), issues


# --------------------------------------------------------------------------- validation


def validate_station_table(
    table: pd.DataFrame,
    latitude: float,
    longitude: float,
    utc_offset: float,
    *,
    elevation: float = 0.0,
    clock_tolerance_min: float = 45.0,
    max_gap_hours: int = 6,
    max_missing_per_hour: int = 1,
) -> StationValidationReport:
    """Check a station table against the upload contract.

    Parameters
    ----------
    table : pd.DataFrame
        A ``timestamp`` column (tz-aware UTC, interval end) and contract columns.
    latitude, longitude : float
        Site location (degrees, east positive).
    utc_offset : float
        Hours east of UTC of the site's standard time (no daylight saving).
        Months and years are judged in this clock. Must be whole hours.
    elevation : float
        Metres; only used for the clear-sky irradiance check.
    clock_tolerance_min : float
        Largest accepted offset between the irradiance-weighted mean time of
        day and solar noon, in any month.
    max_gap_hours, max_missing_per_hour : int
        As for :func:`weather_file_builder.amy.build_amy_dataframe`.
    """
    report = StationValidationReport(utc_offset=float(utc_offset))
    add = report.issues.append

    if abs(float(utc_offset) - round(float(utc_offset))) > 1e-9:
        add(Issue("half_hour_zone", "error",
                  f"the site's standard time is UTC{float(utc_offset):+g}; time zones with a "
                  "fractional offset are not supported yet"))

    ts = _timestamps(table, add)
    data = table.drop(columns=["timestamp"], errors="ignore")
    report.rows = int(len(table))
    report.columns = [str(c) for c in data.columns]
    data = _check_columns(data, add)
    if ts is None or data is None:
        return report

    order = np.argsort(ts.values, kind="stable")
    ts = ts[order]
    data = data.iloc[order].set_axis(ts)
    report.first_utc = str(ts[0]) if len(ts) else None
    report.last_utc = str(ts[-1]) if len(ts) else None
    if len(ts) < 2:
        add(Issue("too_short", "error", "the table needs at least two rows"))
        return report

    step, raw_step = _check_spacing(ts, add)
    report.step_minutes = step
    data = _check_ranges(data, step, add)
    # the clock check also runs on a rejected spacing, so one upload reports every problem
    ghi = data.get("ghi_Wm2")
    if ghi is not None:
        lo, hi = RANGES["ghi_Wm2"]["accept"]
        ghi = ghi.where((ghi >= lo) & (ghi <= hi))  # sensor junk already reported; keep it out of the clock
    offsets = _clock_offsets(ts, ghi, raw_step, latitude, longitude)
    report.clock_offsets_min = {k: round(v, 1) for k, v in offsets.items()}
    _judge_clock(offsets, clock_tolerance_min, add)

    if not report.ok or step is None:
        return report
    _coverage(report, data, step, latitude, longitude, elevation, max_gap_hours, max_missing_per_hour)
    return report


def table_for_builders(table: pd.DataFrame) -> pd.DataFrame:
    """A validated upload as the builders expect it: tz-naive UTC index (``table_utc_offset=0``)."""
    t = table.copy()
    ts = pd.DatetimeIndex(t.pop("timestamp")).tz_convert("UTC").tz_localize(None)
    t.index = ts
    return t.sort_index()


def _timestamps(table: pd.DataFrame, add) -> Optional[pd.DatetimeIndex]:
    if "timestamp" not in table.columns:
        add(Issue("no_timestamp", "error", "no 'timestamp' column"))
        return None
    col = table["timestamp"]
    if not pd.api.types.is_datetime64_any_dtype(col):
        add(Issue("timestamp_type", "error", f"'timestamp' must be a timestamp type, not {col.dtype}",
                  column="timestamp"))
        return None
    ts = pd.DatetimeIndex(col)
    if ts.tz is None:
        add(Issue("timestamp_tz", "error", "'timestamp' has no time zone; store it as UTC (tz-aware)",
                  column="timestamp"))
        return None
    if str(ts.tz) not in _UTC_NAMES:
        add(Issue("timestamp_tz", "error", f"'timestamp' is in time zone {ts.tz}; convert it to UTC",
                  column="timestamp"))
        return None
    if ts.isna().any():
        add(Issue("timestamp_missing", "error", f"{int(ts.isna().sum())} rows have no timestamp",
                  column="timestamp"))
        return None
    if ts.has_duplicates:
        dup = ts[ts.duplicated()]
        add(Issue("timestamp_duplicate", "error", f"{len(dup)} duplicate timestamps, first {dup[0]}",
                  column="timestamp", details=dict(count=int(len(dup)), first=str(dup[0]))))
        return None
    return ts.tz_convert("UTC").tz_localize(None)


def _check_columns(data: pd.DataFrame, add) -> Optional[pd.DataFrame]:
    unknown = [str(c) for c in data.columns if c not in amy.COLUMN_SPEC]
    if unknown:
        add(Issue("unknown_columns", "error",
                  "unknown columns (rename to the contract names or remove): " + ", ".join(unknown),
                  details=dict(columns=unknown)))
    known = [c for c in data.columns if c in amy.COLUMN_SPEC]
    bad_type = [c for c in known if not pd.api.types.is_numeric_dtype(data[c])]
    for c in bad_type:
        add(Issue("not_numeric", "error", f"'{c}' must be numeric, not {data[c].dtype}", column=c))
    numeric = data[[c for c in known if c not in bad_type]].astype(float)
    present = [c for c in numeric.columns if numeric[c].notna().any()]
    for c in numeric.columns:
        if c not in present:
            add(Issue("empty_column", "warning", f"'{c}' has no values and is ignored", column=c))
    for name in ("temp_C", "ghi_Wm2", "wind_speed_ms", "wind_dir_deg"):
        if name not in present:
            add(Issue("missing_required", "error", f"required column '{name}' is missing or empty", column=name))
    if "rh_pct" not in present and "dewpoint_C" not in present:
        add(Issue("missing_required", "error", "one of 'rh_pct' or 'dewpoint_C' is required", column="rh_pct"))
    # keep checking the known columns so one upload reports every problem
    return numeric[present]


def _check_spacing(ts: pd.DatetimeIndex, add) -> Tuple[Optional[int], float]:
    """Return the accepted step in minutes (``None`` if rejected) and the most common spacing."""
    diffs = (ts[1:] - ts[:-1]).total_seconds().to_numpy() / 60.0
    step = float(pd.Series(diffs).mode().iloc[0])
    raw = step
    if step not in ALLOWED_STEPS:
        hint = " Aggregate it to 10 minutes or coarser." if step < 10 else ""
        add(Issue("spacing", "error",
                  f"the most common spacing is {step:g} minutes; use 10, 15, 30 or 60.{hint}",
                  details=dict(step_minutes=step)))
        return None, raw
    step = int(step)
    off = (diffs % step) != 0
    minute_of_day = ts.hour * 60 + ts.minute
    off_grid = (minute_of_day % step != 0) | (ts.second != 0) | (ts.microsecond != 0)
    if off.any() or off_grid.any():
        first = ts[np.flatnonzero(off_grid)[0]] if off_grid.any() else ts[np.flatnonzero(off)[0] + 1]
        add(Issue("irregular", "error",
                  f"{int(off_grid.sum())} timestamps are not on the {step}-minute grid "
                  f"(for example {first}); the spacing must be regular",
                  details=dict(off_grid=int(off_grid.sum()), first=str(first))))
        return None, raw
    return step, raw


def _check_ranges(data: pd.DataFrame, step: Optional[int], add) -> pd.DataFrame:
    for col in data.columns:
        spec = RANGES.get(col)
        if spec is None:
            continue
        lo, hi = spec["valid"]
        if col == "sunshine_min" and step:
            hi = float(step)
        if col == "precip_mm" and step:
            hi = 5.0 * step
        alo, ahi = spec.get("accept", (lo, hi))
        s = data[col]
        below = s < alo if alo is not None else pd.Series(False, index=s.index)
        above = s > ahi if ahi is not None else pd.Series(False, index=s.index)
        bad = below | above
        if bad.any():
            first = s.index[bad.to_numpy()][:3]
            add(Issue(
                "out_of_range", "error",
                f"'{col}': {int(bad.sum())} values outside {_fmt_range(alo, ahi)} "
                f"(min {s.min():g}, max {s.max():g}; first at {', '.join(map(str, first))} UTC)"
                + _unit_hint(col, s),
                column=col,
                details=dict(count=int(bad.sum()), min=float(s.min()), max=float(s.max()),
                             first_utc=[str(t) for t in first]),
            ))
        tolerated = ((s < lo) if lo is not None else False) | ((s > hi) if hi is not None else False)
        tolerated = tolerated & ~bad
        if np.any(tolerated):
            what = "written as 0" if col.endswith("_Wm2") else "capped at 100"
            add(Issue("tolerated_range", "warning",
                      f"'{col}': {int(np.sum(tolerated))} values slightly outside {_fmt_range(lo, hi)} are "
                      f"accepted and {what}", column=col, details=dict(count=int(np.sum(tolerated)))))
        if col == "rh_pct" and s.max() <= 1.5:
            add(Issue("unit_suspect", "warning",
                      "'rh_pct' never exceeds 1.5: is it a fraction instead of percent?", column=col))
    return data


def _fmt_range(lo, hi) -> str:
    return f"[{'-inf' if lo is None else f'{lo:g}'}, {'inf' if hi is None else f'{hi:g}'}]"


def _unit_hint(col: str, s: pd.Series) -> str:
    med = float(s.median())
    if col == "pressure_Pa" and 300 <= med <= 1100:
        return ". The values look like hPa: multiply by 100."
    if col == "pressure_Pa" and 30 <= med <= 110:
        return ". The values look like kPa: multiply by 1000."
    if col in ("temp_C", "dewpoint_C") and 200 <= med <= 330:
        return ". The values look like kelvin: subtract 273.15."
    if col == "wind_dir_deg" and s.max() > 360:
        return ". Directions above 360 may wrap past north (subtract 360); much larger values are sensor errors."
    if col == "rh_pct" and s.max() > 105:
        return ". Values far above 100 % are sensor errors."
    return ". Remove or fix these values (they are often sensor error codes)."


# --------------------------------------------------------------------------- clock


def _clock_offsets(
    ts: pd.DatetimeIndex, ghi: Optional[pd.Series], step: float, latitude: float, longitude: float
) -> Dict[str, float]:
    """Irradiance-weighted mean apparent solar time minus noon, per UTC month (minutes).

    Interval mid-points are used, so a correct hour-ending table is not shifted
    by half an hour. Samples under 5 W/m2 are ignored.
    """
    if ghi is None:
        return {}
    g = ghi.to_numpy(dtype=float)
    mid = ts - pd.Timedelta(minutes=step / 2.0)
    doy = mid.dayofyear.to_numpy()
    eot = pvlib.solarposition.equation_of_time_spencer71(doy)
    clock_min = mid.hour.to_numpy() * 60.0 + mid.minute.to_numpy() + mid.second.to_numpy() / 60.0
    solar_min = clock_min + 4.0 * float(longitude) + eot
    rel = (solar_min - 720.0 + 720.0) % 1440.0 - 720.0
    # weight by the measured irradiance alone: masking by the computed sun position would cut off
    # light that a wrong clock places after sunset and hide part of the error
    w = np.where(np.isfinite(g) & (g > _CLOCK_MIN_WM2), g, 0.0)
    month_key = mid.year.to_numpy() * 100 + mid.month.to_numpy()
    day = mid.year.to_numpy() * 1000 + mid.dayofyear.to_numpy()
    frame = pd.DataFrame({"w": w, "wr": w * rel, "month": month_key, "sunny_day": np.where(w > 0, day, -1)})
    totals = frame.groupby("month")[["w", "wr"]].sum()
    sunny = frame[frame["sunny_day"] >= 0].groupby("month")["sunny_day"].nunique()
    out = {}
    for key, row in totals.iterrows():
        if sunny.get(key, 0) < _CLOCK_MIN_DAYS or row["w"] <= 0:
            continue
        out[f"{key // 100}-{key % 100:02d}"] = float(row["wr"] / row["w"])
    return out


def _judge_clock(offsets: Dict[str, float], tolerance: float, add) -> None:
    if not offsets:
        add(Issue("clock_unchecked", "error",
                  f"the clock could not be checked: no month has {_CLOCK_MIN_DAYS} days with irradiance"))
        return
    bad = {k: v for k, v in offsets.items() if abs(v) > tolerance}
    if bad:
        detail = ", ".join(f"{k} {v:+.0f}" for k, v in sorted(bad.items()))
        late = sum(v > 0 for v in bad.values()) >= len(bad) / 2
        hint = (" Peaks this late usually mean local time labelled as UTC; if months in summer are about an hour "
                "later than months in winter, the clock also follows daylight saving." if late else
                " Peaks this early usually mean the timestamps are in a time zone west of the site, or mark the "
                "start of each interval instead of the end.")
        add(Issue("clock", "error",
                  f"irradiance peaks too far from solar noon (minutes, limit {tolerance:g}): {detail}.{hint}",
                  details=dict(offsets_min={k: round(v, 1) for k, v in bad.items()}, tolerance_min=tolerance)))
        return
    warn = {k: v for k, v in offsets.items() if abs(v) > _CLOCK_WARN_MIN}
    if warn:
        detail = ", ".join(f"{k} {v:+.0f}" for k, v in sorted(warn.items()))
        add(Issue("clock_offset", "warning",
                  f"irradiance peaks {detail} min from solar noon (accepted). A shaded or tilted sensor "
                  "does this; check the mounting if the offsets are large.",
                  details=dict(offsets_min={k: round(v, 1) for k, v in warn.items()})))


# --------------------------------------------------------------------------- coverage


def _coverage(
    report: StationValidationReport,
    data: pd.DataFrame,
    step: int,
    latitude: float,
    longitude: float,
    elevation: float,
    max_gap_hours: int,
    max_missing_per_hour: int,
) -> None:
    location = dict(latitude=latitude, longitude=longitude, elevation=elevation, utc_offset=report.utc_offset)
    clean = data.copy()
    for col in ("ghi_Wm2", "dhi_Wm2", "dni_Wm2"):
        if col in clean.columns:
            clean[col] = clean[col].clip(lower=0)
    if "rh_pct" in clean.columns:
        clean["rh_pct"] = clean["rh_pct"].clip(upper=100)
    hourly, _ = amy.aggregate_to_hourly(
        clean, location, max_missing_per_hour=max_missing_per_hour, variability=False,
    )
    hourly = hourly.drop(columns="ghi_kt_std", errors="ignore")
    hourly = amy._complete_dewpoint_from_rh(hourly)
    first, last = hourly.index.min(), hourly.index.max()
    full = pd.date_range(first.replace(month=1, day=1, hour=0), last.replace(month=12, day=31, hour=23), freq="h")
    h = hourly.reindex(full)
    inside = (full >= first) & (full <= last)

    variables = {"temp_C": ["temp_C"], "humidity": [c for c in ("rh_pct", "dewpoint_C") if c in h.columns],
                 "ghi_Wm2": ["ghi_Wm2"], "wind_speed_ms": ["wind_speed_ms"], "wind_dir_deg": ["wind_dir_deg"]}
    missing = {v: ~h[cols].notna().any(axis=1) for v, cols in variables.items()}
    for col in h.columns:
        if col not in sum(variables.values(), []):
            missing[col] = h[col].isna()

    # gaps inside the record (edges outside the record are not gaps)
    for name, miss in missing.items():
        runs = amy._runs(miss & pd.Series(inside, index=full))
        short = 0
        for start, length in runs:
            if length > max_gap_hours:
                report.long_gaps.append(dict(column=name, start=f"{start:%Y-%m-%d %H:%M}",
                                             end=f"{start + pd.Timedelta(hours=length - 1):%Y-%m-%d %H:%M}",
                                             hours=int(length)))
            else:
                short += length
        if short:
            report.short_gap_hours[name] = int(short)
    report.long_gaps.sort(key=lambda g: (g["start"], g["column"]))
    if report.long_gaps:
        required_gaps = [g for g in report.long_gaps if g["column"] in REQUIRED]
        optional_gaps = [g for g in report.long_gaps if g["column"] not in REQUIRED]
        if required_gaps:
            report.issues.append(Issue(
                "long_gaps", "warning",
                f"{len(required_gaps)} gaps longer than {max_gap_hours} h in required variables "
                f"({sum(g['hours'] for g in required_gaps)} h). A month containing one cannot be used for an AMY "
                "unless that variable is emptied for the whole month, and is not a typical-year candidate.",
                details=dict(count=len(required_gaps))))
        if optional_gaps:
            names = sorted({g["column"] for g in optional_gaps})
            report.issues.append(Issue(
                "long_gaps_optional", "warning",
                f"long gaps in optional columns {', '.join(names)}: pressure is filled from the station's "
                "monthly mean, other optional fields are written as missing for those hours. Drop the column "
                "if you prefer.", details=dict(columns=names)))

    allowance = max_gap_hours + int(np.ceil(abs(report.utc_offset)))
    years = sorted(set(full.year))
    candidates: Dict[int, List[int]] = {m: [] for m in range(1, 13)}
    for year in years:
        year_ok, year_partial = True, False
        for month in range(1, 13):
            sel = (full.year == year) & (full.month == month)
            leap = (full.month == 2) & (full.day == 29)
            sel = sel & ~leap
            key = f"{year}-{month:02d}"
            status = {}
            outside_hours = int((sel & ~inside).sum())
            for name in REQUIRED:
                miss = missing[name][sel]
                if not inside[sel].any() or outside_hours > allowance:
                    status[name] = "outside"
                elif miss[inside[sel]].all() and outside_hours == 0:
                    status[name] = "empty"
                elif max([0] + [n for _, n in amy._runs(miss & inside[sel])]) > max_gap_hours:
                    status[name] = "gaps"
                else:
                    status[name] = "complete"
            report.month_status[key] = status
            in_year = (full.year == year)
            lead = int(((full < first) & in_year).sum())
            trail = int(((full > last) & in_year).sum())
            edge_ok = lead <= allowance and trail <= allowance
            values = set(status.values())
            if "gaps" in values or "outside" in values or not edge_ok:
                year_ok = False
            if "empty" in values:
                year_partial = True
            if values == {"complete"}:
                candidates[month].append(year)
        if year_ok and all(
            any(report.month_status[f"{year}-{m:02d}"][v] == "complete" for m in range(1, 13)) for v in REQUIRED
        ):
            report.amy_years.append(year)
            if year_partial:
                report.partial_amy_years.append(year)
    report.tmy_candidates = candidates
    if not report.amy_years:
        report.issues.append(Issue(
            "no_amy_year", "warning",
            "no calendar year can be built as an AMY: each needs every month of every required variable "
            f"complete (gaps up to {max_gap_hours} h) or entirely empty"))
    fewest = min(len(v) for v in candidates.values())
    if fewest < 10:
        report.issues.append(Issue(
            "few_tmy_years", "warning",
            f"some calendar months have only {fewest} complete candidate year{'s' if fewest != 1 else ''}; "
            "a typical year needs at least 5 "
            "and ISO 15927-4 asks for 10", details=dict(fewest=fewest)))

    _irradiance_level(report, h, location)


def _irradiance_level(report: StationValidationReport, h: pd.DataFrame, location: dict) -> None:
    """Warn about months whose brighter hours stay far from (or far above) clear-sky irradiance.

    For each month, the 90th percentile of the clear-sky index over hours with
    the sun reasonably high. An unshaded, level sensor reaches about 0.9-1.0
    in all but the cloudiest months. Warnings only: fog or a very dull month
    can also do this.
    """
    ghi = h["ghi_Wm2"].dropna()
    if len(ghi) < 24 * 30:
        return
    solar = amy._solar_frame(ghi.index, location)
    loc = pvlib.location.Location(location["latitude"], location["longitude"], altitude=location["elevation"])
    tz = datetime.timezone(datetime.timedelta(hours=float(report.utc_offset)))
    mid = (ghi.index + pd.Timedelta(minutes=30)).tz_localize(tz)
    clear = loc.get_clearsky(mid, model="ineichen", linke_turbidity=3.0)["ghi"].to_numpy()
    high = (solar["zenith"].to_numpy() < 70) & (clear > 200)
    kc = pd.Series(ghi.to_numpy()[high] / clear[high], index=ghi.index[high])
    groups = kc.groupby([f"{y}-{m:02d}" for y, m in zip(kc.index.year, kc.index.month)])
    p90 = groups.quantile(0.9)[groups.size() >= 30]
    low = {k: round(float(v), 2) for k, v in p90.items() if v < 0.5}
    high_months = {k: round(float(v), 2) for k, v in p90.items() if v > 1.3}
    if low:
        report.issues.append(Issue(
            "irradiance_low", "warning",
            "global irradiance stays well below clear-sky levels in " + ", ".join(sorted(low))
            + " (90th percentile of the clear-sky index under 0.5). The sensor may be shaded, tilted, dirty or "
            "not in W/m2; direct/diffuse and sky cover derived from it would be wrong.",
            column="ghi_Wm2", details=dict(p90_clear_sky_index=low)))
    if high_months:
        report.issues.append(Issue(
            "irradiance_high", "warning",
            "global irradiance is often well above clear-sky levels in " + ", ".join(sorted(high_months))
            + ". Check the unit and whether the sensor is tilted.",
            column="ghi_Wm2", details=dict(p90_clear_sky_index=high_months)))


def describe_contract() -> pd.DataFrame:
    """The upload contract as a table: column, unit, required, accepted range."""
    spec = amy.describe_columns().copy()
    spec["required"] = [
        "yes" if c in ("temp_C", "ghi_Wm2", "wind_speed_ms", "wind_dir_deg")
        else ("rh_pct or dewpoint_C" if c in ("rh_pct", "dewpoint_C") else "no")
        for c in spec.index
    ]
    spec["range"] = [_fmt_range(*RANGES[c].get("accept", RANGES[c]["valid"])) if c in RANGES else "" for c in spec.index]
    return spec


__all__: Sequence[str] = (
    "ALLOWED_STEPS", "RANGES", "Issue", "StationValidationReport", "read_station_parquet",
    "validate_station_table", "table_for_builders", "describe_contract",
)
