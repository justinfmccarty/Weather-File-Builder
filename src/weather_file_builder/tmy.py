"""
Typical Meteorological Year (TMY) generation.

Selects one month from the record for each calendar month and stitches them
into a year. ``test_method="iso"`` (the default for a typical year) follows
ISO 15927-4 (:mod:`weather_file_builder.iso15927`). ``"zscore"`` and ``"ks"``
compare the distribution of a single variable and are the methods for the
extreme warm and cold years.
"""

import logging
import warnings
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import scipy.stats as scst

from . import iso15927
from .converters import calculate_relative_humidity

logger = logging.getLogger(__name__)


def z_score(arr1: np.ndarray, arr2: np.ndarray) -> float:
    """Calculate z-score between two arrays.

    Parameters
    ----------
    arr1 : np.ndarray
        First array (typically long-term statistics).
    arr2 : np.ndarray
        Second array (typically candidate month).

    Returns
    -------
    float
        Signed z-score: positive when ``arr2`` has a higher mean than ``arr1``
        (a warmer candidate month for temperature), negative when lower.
        Take the absolute value to measure closeness.
    """
    top = np.mean(arr1) - np.mean(arr2)
    bttm = np.sqrt(np.std(arr1) ** 2 + np.std(arr2) ** 2)
    return -1 * (top / bttm)


def calc_q_total(data: pd.DataFrame, variable: str = "Temperature") -> Dict[int, list]:
    """Calculate quantiles for each month across all years.

    Parameters
    ----------
    data : pd.DataFrame
        Multi-year weather data with ``'Month'`` column.
    variable : str
        Variable to use for month selection.

    Returns
    -------
    dict
        Dictionary mapping month (1-12) to list of 100 quantile values.
    """
    months = np.arange(1, 13)
    q_total = {}

    for month in months:
        sub_data = data[data["Month"] == month]
        q_list = []
        for n in np.linspace(0.00, 1.00, 100):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                q_list.append(sub_data[variable].ffill().quantile(n))
        q_total[month] = q_list

    return q_total


def calc_quantile_dict(
    data: pd.DataFrame, variable: str = "Temperature"
) -> Dict[int, Dict[int, list]]:
    """Calculate quantiles for each month-year combination.

    Parameters
    ----------
    data : pd.DataFrame
        Multi-year weather data with ``'Month'`` and ``'Year'`` columns.
    variable : str
        Variable to use for month selection.

    Returns
    -------
    dict
        Nested dictionary: ``{month: {year: [quantile_values]}}``.
    """
    months = np.arange(1, 13)
    quantile_dict: Dict[int, Dict[int, list]] = {}

    for month in months:
        quantile_dict[month] = {}
        sub_data = data[data["Month"] == month]

        for year in data["Year"].unique():
            month_df = sub_data[sub_data["Year"] == year][variable]
            q_a = []
            for n in np.linspace(0.00, 1.00, 100):
                q_a.append(month_df.quantile(n))
            quantile_dict[month][year] = q_a

    return quantile_dict


def calc_distances(
    data: pd.DataFrame,
    quantile_dict: Dict[int, Dict[int, list]],
    q_total: Dict[int, list],
    file_type: str = "typical",
    test: str = "zscore",
) -> Dict[int, int]:
    """Calculate distances between distributions to find best representative months.

    Parameters
    ----------
    data : pd.DataFrame
        Multi-year weather data.
    quantile_dict : dict
        Quantiles for each month-year combination.
    q_total : dict
        Long-term quantiles for each month.
    file_type : str
        ``'typical'``, ``'extreme_warm'``, or ``'extreme_cold'``.
    test : str
        ``'zscore'`` or ``'ks'`` (Kolmogorov-Smirnov).

    Returns
    -------
    dict
        Dictionary mapping month (1-12) to selected year.
    """
    months = np.arange(1, 13)
    years = data["Year"].unique().tolist()
    best_distances: Dict[int, int] = {}

    for month in months:
        year_distances = []

        for year in data["Year"].unique():
            test_set = quantile_dict[month][year]

            if test == "ks":
                # One-sided statistics grow as the candidate moves away from the
                # long-term distribution in the requested direction: "greater"
                # for warmer candidates, "less" for colder ones.
                if file_type == "extreme_warm":
                    distance = scst.kstest(q_total[month], test_set, alternative="greater")[0]
                elif file_type == "extreme_cold":
                    distance = scst.kstest(q_total[month], test_set, alternative="less")[0]
                else:
                    distance = scst.kstest(q_total[month], test_set, alternative="two-sided")[0]
            else:
                distance = z_score(q_total[month], test_set)
                if file_type not in ("extreme_warm", "extreme_cold"):
                    # Typical: closeness in either direction, not the most negative.
                    distance = abs(distance)

            year_distances.append(distance)

        order = np.argsort(year_distances)
        if file_type == "extreme_warm":
            pick = order[-1]
        elif file_type == "extreme_cold":
            # Signed z-score: most negative is coldest. One-sided KS "less":
            # the largest statistic is the coldest.
            pick = order[-1] if test == "ks" else order[0]
        else:
            pick = order[0]
        best_distances[int(month)] = int(years[pick])

    return best_distances


def build_new_df(data: pd.DataFrame, best_distances: Dict[int, int]) -> pd.DataFrame:
    """Build the constructed weather dataset from selected months.

    Parameters
    ----------
    data : pd.DataFrame
        Multi-year weather data.
    best_distances : dict
        Dictionary mapping month to selected year.

    Returns
    -------
    pd.DataFrame
        Single year constructed from selected months.
    """
    new_df = []

    for n, year in enumerate(best_distances.values()):
        month_sub = data[data["Month"] == n + 1]
        new_df.append(month_sub[month_sub["Year"] == year])

    return pd.concat(new_df, axis=0, ignore_index=True)


#: ERA5 frame columns for the ISO 15927-4 roles.
_ISO_ROLES = {"temp": "Temperature", "ghi": "GHI", "rh": "Relative Humidity", "wind": "Wind Speed"}
#: ERA5 columns smoothed across month joins (RH is recomputed afterwards).
_ISO_SMOOTH = ("Temperature", "Dew Point", "Pressure", "IR")


def _create_tmy_iso(data: pd.DataFrame, join_hours: int = 8) -> Tuple[pd.DataFrame, Dict[int, int]]:
    for col in ("Year", "Month", "Day", "Hour"):
        if col not in data.columns:
            raise ValueError(f"test_method='iso' needs a '{col}' column")
    index = pd.to_datetime(
        pd.DataFrame({"year": data["Year"], "month": data["Month"], "day": data["Day"], "hour": data["Hour"]})
    )
    hourly = data.set_index(pd.DatetimeIndex(index))
    hourly = hourly[~((hourly.index.month == 2) & (hourly.index.day == 29))]
    n_years = hourly.index.year.nunique()
    if n_years < 10:
        logger.warning("ISO 15927-4 asks for at least 10 years; the record has %d.", n_years)
    selection = iso15927.select_typical_months(hourly, _ISO_ROLES, min_years=1)
    for note in selection.notes:
        logger.info(note)
    year_rows = iso15927.assemble_typical_year(hourly, selection.months)
    year_rows, _ = iso15927.blend_joins(year_rows, hourly, _ISO_SMOOTH, hours=join_hours)
    if {"Temperature", "Dew Point", "Relative Humidity"} <= set(year_rows.columns):
        year_rows["Dew Point"] = np.minimum(year_rows["Dew Point"], year_rows["Temperature"])
        year_rows["Relative Humidity"] = calculate_relative_humidity(
            year_rows["Temperature"], year_rows["Dew Point"]
        )
    return year_rows.reset_index(drop=True), {int(m): int(y) for m, y in selection.months.items()}


def create_tmy(
    data: pd.DataFrame,
    variable: str = "Temperature",
    file_type: str = "typical",
    test_method: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[int, int]]:
    """Generate a Typical Meteorological Year from multi-year data.

    Uses statistical methods to select the most representative month from
    each available year to construct a single year of typical weather.

    Parameters
    ----------
    data : pandas.DataFrame
        Multi-year weather data with columns including ``'Year'``,
        ``'Month'``, and the target variable.
    variable : str, default ``'Temperature'``
        Variable used by ``'zscore'`` and ``'ks'``. ``'iso'`` always ranks
        temperature, GHI and relative humidity (wind speed as tiebreak).
    file_type : str, default ``'typical'``
        Type of meteorological year:
        ``'typical'``, ``'extreme_warm'``, or ``'extreme_cold'``.
    test_method : str, optional
        ``'iso'`` (ISO 15927-4; default for ``'typical'``, needs ``Day`` and
        ``Hour`` columns), ``'zscore'`` (default for the extremes) or ``'ks'``.
        ISO 15927-4 defines only a typical year.

    Returns
    -------
    tuple of (pd.DataFrame, dict)
        - DataFrame: Single year of weather data constructed from selected months.
        - dict: Mapping of month (1-12) to selected year.
    """
    data = data.copy()

    col_mapping = {}
    for col in data.columns:
        col_lower = col.lower()
        if col_lower == "year":
            col_mapping[col] = "Year"
        elif col_lower == "month":
            col_mapping[col] = "Month"

    if col_mapping:
        data = data.rename(columns=col_mapping)

    if "Year" not in data.columns or "Month" not in data.columns:
        raise ValueError("Data must contain 'Year' and 'Month' columns")

    if variable not in data.columns:
        raise ValueError(
            f"Variable '{variable}' not found in data. Available: {list(data.columns)}"
        )

    if test_method is None:
        test_method = "iso" if file_type == "typical" else "zscore"
    if test_method not in ("iso", "zscore", "ks"):
        raise ValueError("test_method must be 'iso', 'zscore' or 'ks'")
    if file_type not in ("typical", "extreme_warm", "extreme_cold"):
        raise ValueError("file_type must be 'typical', 'extreme_warm' or 'extreme_cold'")
    if test_method == "iso":
        if file_type != "typical":
            raise ValueError("ISO 15927-4 defines only a typical year; use 'zscore' or 'ks' for extremes")
        logger.info("Calculating TMY per ISO 15927-4...")
        tmy_df, distances = _create_tmy_iso(data)
        for month, year in distances.items():
            logger.info("  %s: %d", iso15927.MONTH_NAMES[month - 1], year)
        return tmy_df, distances

    n_years = data["Year"].nunique()
    if n_years < 3:
        logger.warning("TMY typically requires 10+ years. You have %d years.", n_years)

    logger.info("Calculating TMY using %s method for '%s'...", test_method, variable)
    q_total = calc_q_total(data, variable)
    q_dict = calc_quantile_dict(data, variable)
    distances = calc_distances(data, q_dict, q_total, file_type=file_type, test=test_method)

    tmy_df = build_new_df(data, distances)

    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    logger.info("TMY construction complete. Selected years by month:")
    for month, year in distances.items():
        logger.info("  %s: %d", month_names[month - 1], year)

    return tmy_df, distances
