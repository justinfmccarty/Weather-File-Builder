"""Typical year selection after ISO 15927-4 (hourly data for annual energy use).

For each calendar month the method picks one real month from the record:

1. Daily means of dry-bulb temperature, global horizontal irradiance and
   relative humidity are computed for every candidate month.
2. For each variable, the Finkelstein-Schafer statistic compares the
   cumulative distribution of the candidate's daily means with that of all
   candidates' daily means for the same calendar month:
   ``FS = sum_i |F(i) - Phi(i)|`` with ``F(i) = J(i)/(n+1)`` (rank within the
   candidate month) and ``Phi(i) = K(i)/(N+1)`` (rank within the pooled set).
3. Candidates are ranked per variable (1 = smallest FS) and the ranks summed.
4. Among the three candidates with the lowest rank sum, the one whose monthly
   mean wind speed is closest to the multi-year monthly mean is chosen.

The selected months are stitched into one year and the 8 hours either side
of each midnight join (including December to January) are smoothed. ISO
15927-4 asks for a smooth transition at the joins; the default here blends the
two source years' own records across the window, so the jump disappears and the
diurnal cycle is kept (see :func:`blend_joins`). Temperature, humidity,
pressure and longwave are smoothed. Wind is not (it varies too much within a
day to need it) and neither is irradiance (the window reaches into daylight
in summer).

This module is generic: callers name their columns through ``columns``.
:func:`weather_file_builder.tmy.create_tmy` uses it for ERA5 data and
:mod:`weather_file_builder.station_tmy` for station tables.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

#: Variables ranked by the Finkelstein-Schafer statistic, in ISO order.
PRIMARY_ROLES = ("temp", "ghi", "rh")
#: Role used to break ties among the best candidates.
WIND_ROLE = "wind"

MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass
class TypicalYearSelection:
    """Result of :func:`select_typical_months`."""

    months: Dict[int, int]
    period: Tuple[int, int]
    #: One row per (month, year) candidate: FS and rank per variable, rank sum,
    #: wind deviation, and whether the candidate was eligible.
    table: pd.DataFrame
    eligible_years: Dict[int, List[int]] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def comments(self) -> str:
        """``Period of Record=YYYY-YYYY; Jan=YYYY; ...`` as ClimateOneBuilding writes it."""
        months = "; ".join(f"{MONTH_NAMES[m - 1]}={y}" for m, y in sorted(self.months.items()))
        return f"Period of Record={self.period[0]}-{self.period[1]}; {months}"


def _longest_nan_run(values: np.ndarray) -> int:
    longest = run = 0
    for missing in values:
        run = run + 1 if missing else 0
        longest = max(longest, run)
    return longest


def _hours_of(year: int, month: int) -> pd.DatetimeIndex:
    start = pd.Timestamp(year=year, month=month, day=1)
    hours = pd.date_range(start, start + pd.offsets.MonthBegin(1), freq="h", inclusive="left")
    return hours[~((hours.month == 2) & (hours.day == 29))]


def _finkelstein_schafer(candidate: np.ndarray, pooled_sorted: np.ndarray) -> float:
    x = np.sort(candidate)
    n, big_n = len(x), len(pooled_sorted)
    f = np.arange(1, n + 1) / (n + 1.0)
    phi = np.searchsorted(pooled_sorted, x, side="right") / (big_n + 1.0)
    return float(np.abs(f - phi).sum())


def select_typical_months(
    hourly: pd.DataFrame,
    columns: Dict[str, str],
    *,
    period: Optional[Tuple[int, int]] = None,
    required: Iterable[str] = (),
    max_gap_hours: int = 6,
    min_years: int = 10,
    tiebreak_candidates: int = 3,
) -> TypicalYearSelection:
    """Choose one year for each calendar month (ISO 15927-4).

    Parameters
    ----------
    hourly : pd.DataFrame
        Hourly values indexed by the hour *start* (tz-naive, in the clock that
        defines the months, normally local standard time).
    columns : dict
        Role -> column name. Roles ``"temp"``, ``"ghi"`` and ``"rh"`` are ranked;
        ``"wind"`` breaks ties. ``"temp"`` is required; a missing role is
        skipped with a note.
    period : (int, int), optional
        First and last year to consider (inclusive). Default: all years in *hourly*.
    required : iterable of str
        Further columns that must be complete (up to short gaps) for a month to
        be a candidate, e.g. wind direction for an EPW.
    max_gap_hours : int
        A candidate month is eligible only if no ranked, tiebreak or required
        column has a run of missing hours longer than this. Shorter gaps are
        interpolated before daily means are taken.
    min_years : int
        Raise if any calendar month has fewer eligible candidates. ISO 15927-4
        asks for at least 10 years.
    tiebreak_candidates : int
        How many of the lowest rank sums go to the wind tiebreak.
    """
    if "temp" not in columns or columns["temp"] not in hourly.columns:
        raise ValueError("the 'temp' role is required and must name a column of hourly")
    if not isinstance(hourly.index, pd.DatetimeIndex):
        raise ValueError("hourly needs a DatetimeIndex of hour starts")
    notes: List[str] = []
    roles = {}
    for role in PRIMARY_ROLES + (WIND_ROLE,):
        name = columns.get(role)
        if name is not None and name in hourly.columns and hourly[name].notna().any():
            roles[role] = name
        elif role != "temp":
            notes.append(f"no '{role}' column: not used in the selection")
    ranked = [r for r in PRIMARY_ROLES if r in roles]
    checked = list(dict.fromkeys(list(roles.values()) + [c for c in required if c in hourly.columns]))
    missing_required = [c for c in required if c not in hourly.columns]
    if missing_required:
        raise ValueError(f"required columns not in hourly: {missing_required}")

    years = sorted(set(hourly.index.year))
    if period is not None:
        years = [y for y in years if period[0] <= y <= period[1]]
    if not years:
        raise ValueError("no data in the requested period")
    first, last = (period if period is not None else (years[0], years[-1]))

    data = hourly[checked].sort_index()
    data = data[~data.index.duplicated(keep="first")]

    rows = []
    daily: Dict[Tuple[int, int], pd.DataFrame] = {}
    for month in range(1, 13):
        for year in years:
            idx = _hours_of(year, month)
            block = data.reindex(idx)
            gaps = {c: _longest_nan_run(block[c].isna().to_numpy()) for c in checked}
            worst = max(gaps, key=gaps.get)
            eligible = gaps[worst] <= max_gap_hours
            row = dict(month=month, year=year, eligible=eligible, longest_gap_h=gaps[worst],
                       gap_column=worst if gaps[worst] else "")
            if eligible:
                filled = block[[roles[r] for r in roles]].interpolate(limit_direction="both")
                daily[(month, year)] = filled.groupby(filled.index.normalize()).mean()
            rows.append(row)
    table = pd.DataFrame(rows).set_index(["month", "year"])
    table["selected"] = False

    eligible_years = {
        m: [y for y in years if table.loc[(m, y), "eligible"]] for m in range(1, 13)
    }
    short = {m: len(v) for m, v in eligible_years.items() if len(v) < min_years}
    if short:
        detail = ", ".join(f"{MONTH_NAMES[m - 1]} {n}" for m, n in short.items())
        raise ValueError(
            f"too few complete candidate months (need {min_years}): {detail}. "
            "Widen the period, raise max_gap_hours, or lower min_years."
        )
    if min(len(v) for v in eligible_years.values()) < 10:
        notes.append("fewer than 10 candidate years for some months (ISO 15927-4 asks for 10)")
    dropped = table[~table["eligible"]]
    for (m, y), r in dropped.iterrows():
        notes.append(f"{MONTH_NAMES[m - 1]} {y} not a candidate: {r['gap_column']} gap of {int(r['longest_gap_h'])} h")

    selected: Dict[int, int] = {}
    for month in range(1, 13):
        cands = eligible_years[month]
        for role in ranked:
            name = roles[role]
            pooled = np.sort(np.concatenate([daily[(month, y)][name].to_numpy() for y in cands]))
            fs = pd.Series({y: _finkelstein_schafer(daily[(month, y)][name].to_numpy(), pooled) for y in cands})
            rank = fs.rank(method="min")
            for y in cands:
                table.loc[(month, y), f"fs_{role}"] = fs[y]
                table.loc[(month, y), f"rank_{role}"] = rank[y]
        sub = table.loc[month].loc[cands]
        sub = sub.assign(rank_sum=sub[[f"rank_{r}" for r in ranked]].sum(axis=1),
                         fs_sum=sub[[f"fs_{r}" for r in ranked]].sum(axis=1))
        for y in cands:
            table.loc[(month, y), "rank_sum"] = sub.loc[y, "rank_sum"]
        best = sub.sort_values(["rank_sum", "fs_sum"], kind="mergesort").head(tiebreak_candidates)
        if WIND_ROLE in roles:
            wname = roles[WIND_ROLE]
            overall = np.mean([daily[(month, y)][wname].mean() for y in cands])
            dev = pd.Series({y: abs(daily[(month, y)][wname].mean() - overall) for y in best.index})
            for y in best.index:
                table.loc[(month, y), "wind_deviation"] = dev[y]
            choice = int(dev.sort_values(kind="mergesort").index[0])
        else:
            choice = int(best.index[0])
        selected[month] = choice
        table.loc[(month, choice), "selected"] = True

    return TypicalYearSelection(months=selected, period=(int(first), int(last)), table=table,
                                eligible_years=eligible_years, notes=notes)


def blend_joins(
    year_rows: pd.DataFrame,
    source: pd.DataFrame,
    columns: Iterable[str] = (),
    circular_columns: Iterable[str] = (),
    hours: int = 8,
    method: str = "crossfade",
    wrap: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Smooth the ``hours`` either side of each month join (and December to January).

    *year_rows* are the stitched months, indexed by each row's real timestamp
    (see :func:`assemble_typical_year`); *source* is the full record they came
    from, used to continue each month's own year past the join.

    ``method="crossfade"`` (default) blends the two source years across the
    ``2 * hours`` window: the outgoing year's record continues into the next
    month and the incoming year's record is taken back into the last hours of
    the previous month, weighted linearly from one to the other. The jump at
    midnight disappears and the diurnal cycle is kept. ``method="linear"``
    replaces the window by a straight line between the values just outside
    it, which also removes the night-time minimum or maximum. Where the
    continuation is not in *source* (start or end of the record, gaps), that
    join falls back to linear.

    Returns the smoothed frame and, per column, the number of joins that fell
    back to linear.
    """
    if method not in ("crossfade", "linear"):
        raise ValueError("method must be 'crossfade' or 'linear'")
    out = year_rows.copy()
    if hours <= 0:
        return out, {}
    source = source[~source.index.duplicated(keep="first")].sort_index()
    months = out.index.month.to_numpy()
    joins = list(np.flatnonzero(np.diff(months) != 0) + 1)
    n = len(out)
    if wrap and n > 2 * hours:
        joins.append(n)  # December to January
    w = (np.arange(2 * hours) + 0.5) / (2 * hours)
    fallbacks: Dict[str, int] = {}
    cols = [c for c in columns if c in out.columns]
    circ = [c for c in circular_columns if c in out.columns]
    for j in joins:
        rows = np.arange(j - hours, j + hours) % n
        a_idx = out.index[(j - 1) % n]  # last hour of the outgoing month
        b_idx = out.index[j % n]        # first hour of the incoming month
        after_a = source.loc[source.index > a_idx].head(hours)
        before_b = source.loc[source.index < b_idx].tail(hours)
        for c in cols + circ:
            vals = out[c].to_numpy(dtype=float)[rows]
            ext_a = after_a[c].to_numpy(dtype=float) if c in after_a.columns else np.array([])
            ext_b = before_b[c].to_numpy(dtype=float) if c in before_b.columns else np.array([])
            use_cross = (
                method == "crossfade" and len(ext_a) == hours and len(ext_b) == hours
                and np.isfinite(ext_a).all() and np.isfinite(ext_b).all()
            )
            if use_cross:
                series_a = np.concatenate([vals[:hours], ext_a])
                series_b = np.concatenate([ext_b, vals[hours:]])
            else:
                if method == "crossfade":
                    fallbacks[c] = fallbacks.get(c, 0) + 1
                va, vb = out[c].iat[(j - hours - 1) % n], out[c].iat[(j + hours) % n]
                if not (np.isfinite(va) and np.isfinite(vb)):
                    continue
                wl = np.arange(1, 2 * hours + 1) / (2 * hours + 1.0)
                if c in circ:
                    series_a, series_b, w_use = np.full(2 * hours, va), np.full(2 * hours, vb), wl
                else:
                    out.iloc[rows, out.columns.get_loc(c)] = va + (vb - va) * wl
                    continue
            w_use = w if use_cross else w_use
            if c in circ:
                ra, rb = np.radians(series_a), np.radians(series_b)
                u = (1 - w_use) * np.sin(ra) + w_use * np.sin(rb)
                v = (1 - w_use) * np.cos(ra) + w_use * np.cos(rb)
                blended = np.degrees(np.arctan2(u, v)) % 360.0
            else:
                blended = (1 - w_use) * series_a + w_use * series_b
            if np.isfinite(blended).all():
                out.iloc[rows, out.columns.get_loc(c)] = blended
    return out, fallbacks


def assemble_typical_year(hourly: pd.DataFrame, months: Dict[int, int]) -> pd.DataFrame:
    """Stitch the selected months into 8760 rows, keeping each row's real timestamp.

    The index is not monotonic across joins (January 2011, then February
    2008, ...), which keeps solar geometry exact for measured irradiance.
    Missing hours are NaN; fill them before use.
    """
    hourly = hourly[~hourly.index.duplicated(keep="first")]
    parts = []
    for month in range(1, 13):
        idx = _hours_of(months[month], month)
        parts.append(hourly.reindex(idx))
    out = pd.concat(parts)
    if len(out) != 8760:
        raise AssertionError(f"assembled {len(out)} rows, expected 8760")
    return out
