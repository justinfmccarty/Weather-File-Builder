"""Typical meteorological year from a measured station table (ISO 15927-4).

Input is the station table described in :mod:`weather_file_builder.amy`
(column names, units, timestamp convention). Steps:

1. Aggregate to hourly rows in local standard time.
2. Select one year per calendar month from the measured fields only
   (:func:`weather_file_builder.iso15927.select_typical_months`): daily means
   of dry-bulb temperature, global irradiance and relative humidity, wind
   speed as the tiebreak. A month with a gap longer than ``max_gap_hours`` in
   any of these, or in wind direction, is not a candidate.
3. Stitch the months, interpolate short gaps, and smooth the 8 hours either
   side of each join and of December to January (temperature, humidity,
   pressure, longwave; not wind or irradiance).
4. Derive the rest as for an AMY (:func:`weather_file_builder.amy.derive_epw_rows`):
   dew point from temperature and RH, direct/diffuse from global irradiance,
   sky cover from the clear-sky index (night interpolated, one method for every
   month), pressure where it was not measured from the station's monthly mean
   or the standard atmosphere.

The EPW ``year`` field holds each month's source year, and COMMENTS 1 states
``Period of Record=<first>-<last>; Jan=YYYY; ...`` as ClimateOneBuilding does.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from . import amy, iso15927

logger = logging.getLogger(__name__)

#: Columns smoothed across month joins (linear) and as directions (circular).
_SMOOTH = ("temp_C", "rh_pct", "dewpoint_C", "pressure_Pa", "lw_down_Wm2")


@dataclass
class StationTmyReport(amy.AmyReport):
    """What was done to build a station TMY, including the month selection."""

    selection: Optional[iso15927.TypicalYearSelection] = None

    def to_text(self) -> str:
        lines = []
        if self.selection is not None:
            lines.append(self.selection.comments())
            lines.extend(self.selection.notes)
        body = super().to_text().split("\n", 1)
        lines.append(f"source resolution {self.source_step_minutes} min")
        if len(body) > 1:
            lines.append(body[1])
        return "\n".join(lines)


def build_station_tmy_dataframe(
    table: pd.DataFrame,
    location: dict,
    period: Tuple[int, int],
    *,
    timestamp_label: str = "end",
    table_utc_offset: float = 0.0,
    max_gap_hours: int = 6,
    min_years: int = 10,
    join_hours: int = 8,
    join_method: str = "crossfade",
    decomposition: str = "auto",
    sky_cover_night: str = "interpolate",
) -> Tuple[pd.DataFrame, StationTmyReport]:
    """Build the 8760 EPW rows of an ISO 15927-4 typical year.

    Parameters
    ----------
    table : pd.DataFrame
        Station measurements; see :mod:`weather_file_builder.amy`.
    location : dict
        As for :func:`weather_file_builder.amy.build_amy_dataframe`.
    period : (int, int)
        First and last year of the selection window (inclusive), for example
        ``(1991, 2020)``. Written as the Period of Record.
    max_gap_hours, min_years
        See :func:`weather_file_builder.iso15927.select_typical_months`.
    join_hours : int
        Hours either side of each month join that are smoothed (0 to disable).
    join_method : {"crossfade", "linear"}
        See :func:`weather_file_builder.iso15927.blend_joins`.
    decomposition : str
        See :func:`weather_file_builder.amy.build_amy_dataframe`.
    sky_cover_night : {"interpolate", "auto"}
        ``"interpolate"`` (default) uses the same night method for every month;
        ``"auto"`` uses longwave in months that have it.
    """
    amy._check_location(location)
    report = StationTmyReport()
    hourly, step = amy.aggregate_to_hourly(
        table, location, timestamp_label=timestamp_label, table_utc_offset=table_utc_offset
    )
    report.source_step_minutes = step
    climatology = amy.pressure_climatology(hourly)
    hourly = hourly[~((hourly.index.month == 2) & (hourly.index.day == 29))]
    hourly = amy._complete_dewpoint_from_rh(hourly)
    humidity = "rh_pct" if "rh_pct" in hourly.columns else "dewpoint_C"
    if humidity not in hourly.columns:
        raise ValueError("one of 'rh_pct' or 'dewpoint_C' is required")

    selection = iso15927.select_typical_months(
        hourly,
        {"temp": "temp_C", "ghi": "ghi_Wm2", "rh": humidity, "wind": "wind_speed_ms"},
        period=period,
        required=("wind_dir_deg",),
        max_gap_hours=max_gap_hours,
        min_years=min_years,
    )
    report.selection = selection
    report.year = int(selection.months[1])
    for (m, y), r in selection.table[selection.table["selected"]].iterrows():
        logger.info("%s: %d (rank sum %s)", iso15927.MONTH_NAMES[m - 1], y, r.get("rank_sum"))

    year_rows = iso15927.assemble_typical_year(hourly, selection.months)
    year_rows = year_rows.loc[:, year_rows.notna().any()]
    months = year_rows.index.month
    no_pressure = None
    if "pressure_Pa" in year_rows.columns:
        # months without any pressure reading are filled from the station mean below,
        # not by interpolating a few hours in from the neighbouring month
        has = year_rows["pressure_Pa"].notna().groupby(months).any()
        no_pressure = months.isin(has[~has].index)
    solar = amy._solar_frame(year_rows.index, location)
    year_rows = amy._fill_gaps(year_rows, solar, max_gap_hours, "raise", report)
    if no_pressure is not None and no_pressure.any():
        year_rows.loc[no_pressure, "pressure_Pa"] = np.nan
        report.filled_hours.pop("pressure_Pa", None)
        filled = int(year_rows["pressure_Pa"].notna().sum() - (~no_pressure).sum())
        if filled > 0:
            report.filled_hours["pressure_Pa"] = filled
    # fill pressure before smoothing so the joins between measured and filled months are smoothed too
    year_rows["pressure_Pa"] = amy._fill_pressure(year_rows, location, climatology, report)
    year_rows, fallbacks = iso15927.blend_joins(
        year_rows, hourly, _SMOOTH, hours=join_hours, method=join_method
    )
    if fallbacks:
        detail = ", ".join(f"{c} {n}" for c, n in sorted(fallbacks.items()))
        report.notes.append(f"joins smoothed linearly where the record has no continuation: {detail}")
    if "rh_pct" in year_rows.columns and "dewpoint_C" in year_rows.columns:
        # recompute from the smoothed temperature and RH so the three agree
        year_rows = year_rows.drop(columns="dewpoint_C")

    epw, report = amy.derive_epw_rows(
        year_rows, location, year_rows.index.year.to_numpy(), step=step, decomposition=decomposition,
        sky_cover_night=sky_cover_night, pressure_monthly_mean=climatology, report=report,
    )
    return epw, report


def write_station_tmy_epw(
    path: str,
    epw: pd.DataFrame,
    location: dict,
    report: StationTmyReport,
    *,
    source_name: str = "weather station",
    attribution: Optional[str] = None,
) -> None:
    """Write the rows from :func:`build_station_tmy_dataframe` to an EPW file."""
    sel = report.selection
    comments_1 = f"Measured data from {source_name}, built with weather-file-builder - {sel.comments()}"
    comments_2 = (
        "Typical year per ISO 15927-4: months chosen on daily means of dry-bulb temperature, global "
        "irradiance and relative humidity, wind speed as tiebreak; 8 h either side of each month join "
        "blended between the two source years (not wind or irradiance); hourly means in local standard time, hour ending; "
        + "; ".join(amy.report_methods(report))
        + ("; " + attribution if attribution else "")
    )
    amy.write_epw_file(path, epw, location, comments_1, comments_2)


def station_table_to_tmy_epw(
    table: pd.DataFrame,
    location: dict,
    period: Tuple[int, int],
    output_path: str,
    *,
    source_name: str = "weather station",
    attribution: Optional[str] = None,
    **build_kwargs,
) -> StationTmyReport:
    """Build a station TMY and write it to *output_path*. Returns the report."""
    epw, report = build_station_tmy_dataframe(table, location, period, **build_kwargs)
    write_station_tmy_epw(output_path, epw, location, report, source_name=source_name, attribution=attribution)
    return report
