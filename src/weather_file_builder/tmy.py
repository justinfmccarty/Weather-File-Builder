"""
Typical Meteorological Year (TMY) generation.

This module provides functionality to generate TMY files by selecting
representative months from multi-year weather datasets using statistical
methods (Finkelstein-Schafer statistics and z-score analysis).
"""

import pandas as pd
import numpy as np
import scipy.stats as scst
from typing import Dict, Tuple, Optional
import warnings


def z_score(arr1: np.ndarray, arr2: np.ndarray) -> float:
    """
    Calculate z-score between two arrays.
    
    Parameters
    ----------
    arr1 : np.ndarray
        First array (typically long-term statistics)
    arr2 : np.ndarray
        Second array (typically candidate month)
    
    Returns
    -------
    float
        Z-score indicating similarity between distributions
    """
    top = (np.mean(arr1) - np.mean(arr2))
    bttm = np.sqrt((np.std(arr1)**2) + (np.std(arr2)**2))
    return -1 * (top / bttm)


def calc_q_total(data: pd.DataFrame, variable: str = 'Temperature') -> Dict[int, list]:
    """
    Calculate quantiles for each month across all years (long-term statistics).
    
    Parameters
    ----------
    data : pd.DataFrame
        Multi-year weather data with 'Month' column
    variable : str
        Variable to use for month selection
    
    Returns
    -------
    dict
        Dictionary mapping month (1-12) to list of 100 quantile values
    """
    months = np.arange(1, 13)
    q_total = {}
    
    for month in months:
        sub_data = data[data['Month'] == month]
        q_list = []
        for n in np.linspace(0.00, 1.00, 100):
            # Use forward fill for any missing values
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                q_list.append(sub_data[variable].ffill().quantile(n))
        q_total[month] = q_list
    
    return q_total


def calc_quantile_dict(data: pd.DataFrame, variable: str = 'Temperature') -> Dict[int, Dict[int, list]]:
    """
    Calculate quantiles for each month-year combination.
    
    Parameters
    ----------
    data : pd.DataFrame
        Multi-year weather data with 'Month' and 'Year' columns
    variable : str
        Variable to use for month selection
    
    Returns
    -------
    dict
        Nested dictionary: {month: {year: [quantile_values]}}
    """
    months = np.arange(1, 13)
    quantile_dict = {}
    
    for month in months:
        quantile_dict[month] = {}
        sub_data = data[data['Month'] == month]
        
        for year in data['Year'].unique():
            month_df = sub_data[sub_data['Year'] == year][variable]
            q_a = []
            for n in np.linspace(0.00, 1.00, 100):
                q_a.append(month_df.quantile(n))
            quantile_dict[month][year] = q_a
    
    return quantile_dict


def calc_distances(
    data: pd.DataFrame,
    quantile_dict: Dict[int, Dict[int, list]],
    q_total: Dict[int, list],
    file_type: str = 'typical',
    test: str = 'zscore'
) -> Dict[int, int]:
    """
    Calculate distances between distributions to find best representative months.
    
    Parameters
    ----------
    data : pd.DataFrame
        Multi-year weather data
    quantile_dict : dict
        Quantiles for each month-year combination
    q_total : dict
        Long-term quantiles for each month
    file_type : str
        'typical', 'extreme_warm', or 'extreme_cold'
    test : str
        'zscore' or 'ks' (Kolmogorov-Smirnov)
    
    Returns
    -------
    dict
        Dictionary mapping month (1-12) to selected year
    """
    months = np.arange(1, 13)
    years = data['Year'].unique().tolist()
    best_distances = {}
    
    for month in months:
        year_distances = []
        
        for year in data['Year'].unique():
            test_set = quantile_dict[month][year]
            
            if test == "ks":
                if file_type == 'typical':
                    distance = scst.kstest(q_total[month], test_set, alternative='two-sided')[0]
                elif file_type == 'extreme_warm':
                    distance = scst.kstest(q_total[month], test_set, alternative='greater')[0]
                elif file_type == 'extreme_cold':
                    distance = scst.kstest(q_total[month], test_set, alternative='less')[0]
                else:
                    distance = scst.kstest(q_total[month], test_set, alternative='two-sided')[0]
            else:  # zscore
                distance = z_score(q_total[month], test_set)
            
            year_distances.append(distance)
        
        # Select best year based on file type
        if file_type == 'typical':
            best_distances[month] = years[np.argsort(year_distances)[0]]
        elif file_type == 'extreme_warm':
            best_distances[month] = years[np.argsort(year_distances)[-1]]
        elif file_type == 'extreme_cold':
            best_distances[month] = years[np.argsort(year_distances)[0]]
        else:
            best_distances[month] = years[np.argsort(year_distances)[0]]
    
    return best_distances


def build_new_df(data: pd.DataFrame, best_distances: Dict[int, int]) -> pd.DataFrame:
    """
    Build the constructed weather dataset from selected months.
    
    Parameters
    ----------
    data : pd.DataFrame
        Multi-year weather data
    best_distances : dict
        Dictionary mapping month to selected year
    
    Returns
    -------
    pd.DataFrame
        Single year constructed from selected months
    """
    new_df = []
    
    for n, year in enumerate(best_distances.values()):
        month_sub = data[data['Month'] == n + 1]
        new_df.append(month_sub[month_sub['Year'] == year])
    
    return pd.concat(new_df, axis=0, ignore_index=True)


def create_tmy(
    data: pd.DataFrame,
    variable: str = 'Temperature',
    file_type: str = 'typical',
    test_method: str = 'zscore'
) -> Tuple[pd.DataFrame, Dict[int, int]]:
    """
    Generate a Typical Meteorological Year from multi-year data.
    
    Uses statistical methods to select the most representative month from
    each available year to construct a single year of typical weather.
    
    Parameters
    ----------
    data : pandas.DataFrame
        Multi-year weather data with columns including 'Year', 'Month',
        and the target variable
    variable : str, default 'Temperature'
        Variable to use for month selection (typically 'Temperature')
    file_type : str, default 'typical'
        Type of meteorological year:
        - 'typical': Most representative months (default)
        - 'extreme_warm': Warmest months
        - 'extreme_cold': Coldest months
    test_method : str, default 'zscore'
        Statistical test method:
        - 'zscore': Z-score comparison (default, recommended)
        - 'ks': Kolmogorov-Smirnov test
    
    Returns
    -------
    tuple of (pd.DataFrame, dict)
        - DataFrame: Single year of weather data constructed from selected months
        - dict: Mapping of month (1-12) to selected year
    
    Notes
    -----
    This implementation uses the Sandia TMY method:
    1. Calculate long-term cumulative distribution functions (CDFs) for each month
    2. Compare each candidate month's CDF to the long-term CDF
    3. Select months with minimum distance (Finkelstein-Schafer statistics)
    
    The input DataFrame should have standardized column names:
    - 'Year': Year of observation
    - 'Month': Month (1-12)
    - Variable column (e.g., 'Temperature')
    
    References
    ----------
    - NREL Technical Manual for TMY3
    - Sandia Method for TMY generation
    
    Examples
    --------
    >>> df = download_multi_year(40.7, -74.0, range(2010, 2020))
    >>> tmy_data, selected_years = create_tmy(df, variable='Temperature')
    >>> print(selected_years)
    {1: 2015, 2: 2012, 3: 2018, ...}
    """
    # Normalize column names to match expected format
    data = data.copy()
    
    # Handle different possible column name variations
    col_mapping = {}
    for col in data.columns:
        col_lower = col.lower()
        if col_lower == 'year':
            col_mapping[col] = 'Year'
        elif col_lower == 'month':
            col_mapping[col] = 'Month'
    
    if col_mapping:
        data = data.rename(columns=col_mapping)
    
    # Validate required columns
    if 'Year' not in data.columns or 'Month' not in data.columns:
        raise ValueError("Data must contain 'Year' and 'Month' columns")
    
    if variable not in data.columns:
        raise ValueError(f"Variable '{variable}' not found in data. Available: {list(data.columns)}")
    
    # Check for sufficient data
    n_years = data['Year'].nunique()
    if n_years < 3:
        print(f"Warning: TMY typically requires 10+ years. You have {n_years} years.")
    
    # Calculate quantiles and distances
    print(f"Calculating TMY using {test_method} method for '{variable}'...")
    q_total = calc_q_total(data, variable)
    q_dict = calc_quantile_dict(data, variable)
    distances = calc_distances(data, q_dict, q_total, file_type=file_type, test=test_method)
    
    # Build TMY dataset
    tmy_df = build_new_df(data, distances)
    
    print(f"TMY construction complete. Selected years by month:")
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for month, year in distances.items():
        print(f"  {month_names[month-1]}: {year}")
    
    return tmy_df, distances
