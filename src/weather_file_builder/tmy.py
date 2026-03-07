"""
Typical Meteorological Year (TMY) generation.

This module provides functionality to generate TMY files by selecting
representative months from multi-year weather datasets using statistical
methods (Finkelstein-Schafer statistics and z-score analysis).
"""

import logging
import warnings
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import scipy.stats as scst

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
        Z-score indicating similarity between distributions.
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
                if file_type == "extreme_warm":
                    distance = scst.kstest(q_total[month], test_set, alternative="greater")[0]
                elif file_type == "extreme_cold":
                    distance = scst.kstest(q_total[month], test_set, alternative="less")[0]
                else:
                    distance = scst.kstest(q_total[month], test_set, alternative="two-sided")[0]
            else:
                distance = z_score(q_total[month], test_set)

            year_distances.append(distance)

        if file_type == "extreme_warm":
            best_distances[month] = years[np.argsort(year_distances)[-1]]
        else:
            best_distances[month] = years[np.argsort(year_distances)[0]]

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


def create_tmy(
    data: pd.DataFrame,
    variable: str = "Temperature",
    file_type: str = "typical",
    test_method: str = "zscore",
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
        Variable to use for month selection.
    file_type : str, default ``'typical'``
        Type of meteorological year:
        ``'typical'``, ``'extreme_warm'``, or ``'extreme_cold'``.
    test_method : str, default ``'zscore'``
        Statistical test method: ``'zscore'`` or ``'ks'``.

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
