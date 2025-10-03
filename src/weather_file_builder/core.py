"""
Core ERA5 data download functionality.
"""

import cdsapi
import xarray as xr
import pandas as pd
import numpy as np
import tempfile
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Union
import requests

from .variables import get_era5_variables
from .converters import era5_to_dataframe


def download_weather_data(
    latitude: float,
    longitude: float,
    year: int,
    variables: Optional[List[str]] = None,
    retry_attempts: int = 3,
    max_workers: int = 12
) -> pd.DataFrame:
    """
    Download weather data for a single year from ERA5.
    
    This is the main single-year download function. It downloads all months
    for the specified year concurrently and returns a complete DataFrame.
    
    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees (-90 to 90)
    longitude : float
        Longitude in decimal degrees (-180 to 180)
    year : int
        Year to download (1940 to present)
    variables : list of str, optional
        Variables to download. Can be group names ('temperature', 'wind', etc.)
        or ERA5 variable names. If None, downloads all variables.
    retry_attempts : int, default 3
        Number of retry attempts for failed downloads
    max_workers : int, default 4
        Maximum number of concurrent downloads. Conservative: 2-3, Balanced: 4-5,
        Aggressive: 6-8. Maximum 12. Higher values may hit CDS API rate limits.
    
    Returns
    -------
    pandas.DataFrame
        Weather data with standardized columns
    
    Examples
    --------
    >>> df = download_weather_data(40.7, -74.0, 2020)
    >>> print(df.shape)
    (8760, 15)
    
    >>> df = download_weather_data(40.7, -74.0, 2020, variables=['temperature', 'wind'])
    
    >>> df = download_weather_data(40.7, -74.0, 2020, max_workers=6)  # More aggressive
    """
    print(f"Downloading ERA5 data for {year} at ({latitude:.2f}, {longitude:.2f})")
    print(f"Using {max_workers} concurrent workers")
    
    # Convert variable names
    era5_vars = get_era5_variables(variables)
    
    # Run async download
    try:
        df_year = asyncio.run(_download_year_async(
            latitude, longitude, year, era5_vars, retry_attempts, max_workers
        ))
    except RuntimeError as e:
        # Handle case where event loop is already running (e.g., in Jupyter)
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            loop = asyncio.get_event_loop()
            df_year = loop.run_until_complete(_download_year_async(
                latitude, longitude, year, era5_vars, retry_attempts, max_workers
            ))
        else:
            raise
    
    print(f"✓ Complete: {len(df_year)} total records for {year}")
    
    return df_year


async def _download_year_async(
    latitude: float,
    longitude: float,
    year: int,
    era5_vars: List[str],
    retry_attempts: int,
    max_workers: int
) -> pd.DataFrame:
    """
    Async function to download all months for a year concurrently.
    """
    loop = asyncio.get_event_loop()
    
    # Use ThreadPoolExecutor for concurrent downloads
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                _download_single_month,
                latitude, longitude, year, month, era5_vars, retry_attempts
            )
            for month in range(1, 13)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter successful downloads
    month_dataframes = []
    failed_months = []
    
    for month, result in enumerate(results, 1):
        if isinstance(result, Exception):
            print(f"  Month {month:02d}: Failed - {type(result).__name__}")
            failed_months.append(month)
        elif result is not None:
            month_dataframes.append(result)
            print(f"  Month {month:02d}: ✓ ({len(result)} records)")
        else:
            print(f"  Month {month:02d}: Failed")
            failed_months.append(month)
    
    if not month_dataframes:
        raise RuntimeError(f"Failed to download any data for {year}")
    
    if failed_months:
        print(f"  ⚠ Warning: {len(failed_months)} months failed: {failed_months}")
    
    # Concatenate all months
    df_year = pd.concat(month_dataframes, axis=0, ignore_index=True)
    print(f"  Downloaded {len(month_dataframes)}/12 months successfully")
    
    return df_year


def download_multi_year(
    latitude: float,
    longitude: float,
    years: Union[List[int], range],
    variables: Optional[List[str]] = None,
    delay_between_months: float = 0.0,
    retry_attempts: int = 3,
    max_workers: int = 4,
    sequential_years: bool = False
) -> pd.DataFrame:
    """
    Download weather data for multiple years from ERA5.
    
    By default, downloads all months concurrently within each year. Set
    sequential_years=True to download years one at a time (slower but more reliable).
    
    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees (-90 to 90)
    longitude : float
        Longitude in decimal degrees (-180 to 180)
    years : list of int or range
        Years to download
    variables : list of str, optional
        Variables to download. If None, downloads all variables.
    delay_between_months : float, default 0.0
        Seconds to wait between month downloads (only used if sequential_years=True).
        Set to 2.0+ if hitting rate limits.
    retry_attempts : int, default 3
        Number of retry attempts for failed downloads
    max_workers : int, default 4
        Maximum number of concurrent downloads per year
    sequential_years : bool, default False
        If True, download years sequentially with delays. If False, use concurrent
        downloads (faster but may hit rate limits for many years).
    
    Returns
    -------
    pandas.DataFrame
        Weather data for all years combined
    
    Examples
    --------
    >>> # Fast concurrent download (default)
    >>> df = download_multi_year(40.7, -74.0, range(2018, 2021))
    >>> print(df['Year'].unique())
    [2018 2019 2020]
    
    >>> # Conservative sequential download if hitting rate limits
    >>> df = download_multi_year(40.7, -74.0, [2018, 2020], 
    ...                          sequential_years=True, delay_between_months=2.0)
    
    >>> # Aggressive concurrent download
    >>> df = download_multi_year(40.7, -74.0, range(2018, 2021), max_workers=6)
    """
    years_list = list(years)
    print(f"Downloading {len(years_list)} years: {years_list[0]}-{years_list[-1]}")
    print(f"Location: ({latitude:.2f}, {longitude:.2f})")
    if sequential_years:
        print(f"Mode: Sequential (delay={delay_between_months}s between months)")
    else:
        print(f"Mode: Concurrent ({max_workers} workers per year)")
    
    # Convert variable names
    era5_vars = get_era5_variables(variables)
    
    if sequential_years:
        # Sequential download with delays (old reliable method)
        all_dataframes = _download_multi_year_sequential(
            latitude, longitude, years_list, era5_vars, 
            delay_between_months, retry_attempts
        )
    else:
        # Concurrent download (faster)
        try:
            all_dataframes = asyncio.run(_download_multi_year_async(
                latitude, longitude, years_list, era5_vars, 
                retry_attempts, max_workers
            ))
        except RuntimeError as e:
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                loop = asyncio.get_event_loop()
                all_dataframes = loop.run_until_complete(_download_multi_year_async(
                    latitude, longitude, years_list, era5_vars, 
                    retry_attempts, max_workers
                ))
            else:
                raise
    
    if not all_dataframes:
        raise RuntimeError("Failed to download any data")
    
    # Combine all years
    df_all = pd.concat(all_dataframes, axis=0, ignore_index=True)
    print(f"\n✓ Total: {len(df_all)} records across {len(years_list)} years")
    
    return df_all


async def _download_multi_year_async(
    latitude: float,
    longitude: float,
    years_list: List[int],
    era5_vars: List[str],
    retry_attempts: int,
    max_workers: int
) -> List[pd.DataFrame]:
    """
    Async function to download multiple years concurrently.
    """
    all_dataframes = []
    
    for year in years_list:
        print(f"\nYear {year}:")
        try:
            df_year = await _download_year_async(
                latitude, longitude, year, era5_vars, retry_attempts, max_workers
            )
            all_dataframes.append(df_year)
            print(f"  ✓ Year {year}: {len(df_year)} records")
        except Exception as e:
            print(f"  ✗ Year {year}: Failed - {e}")
    
    return all_dataframes


def _download_multi_year_sequential(
    latitude: float,
    longitude: float,
    years_list: List[int],
    era5_vars: List[str],
    delay_between_months: float,
    retry_attempts: int
) -> List[pd.DataFrame]:
    """
    Sequential download with delays (for when hitting rate limits).
    """
    all_dataframes = []
    
    for year in years_list:
        print(f"\nYear {year}:")
        
        year_dataframes = []
        for month in range(1, 13):
            print(f"  Month {month:02d}...", end=" ", flush=True)
            
            df_month = _download_single_month(
                latitude, longitude, year, month, era5_vars, retry_attempts
            )
            
            if df_month is not None:
                year_dataframes.append(df_month)
                print("✓")
            else:
                print("✗ Failed")
            
            # Add delay between requests
            if month < 12 and delay_between_months > 0:
                time.sleep(delay_between_months)
        
        if year_dataframes:
            df_year = pd.concat(year_dataframes, axis=0, ignore_index=True)
            all_dataframes.append(df_year)
            print(f"  ✓ Year {year}: {len(df_year)} records")
        else:
            print(f"  ✗ Year {year}: No data downloaded")
    
    return all_dataframes


def _download_single_month(
    latitude: float,
    longitude: float,
    year: int,
    month: int,
    era5_variables: List[str],
    retry_attempts: int = 3
) -> Optional[pd.DataFrame]:
    """
    Download ERA5 data for a single month with retry logic.
    
    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees
    longitude : float
        Longitude in decimal degrees
    year : int
        Year
    month : int
        Month (1-12)
    era5_variables : list of str
        ERA5 variable names for API request
    retry_attempts : int
        Number of retry attempts
    
    Returns
    -------
    pandas.DataFrame or None
        Weather data for the month, or None if download failed
    """
    # Convert longitude to ERA5 format (0-360)
    era5_lon = longitude + 360 if longitude < 0 else longitude
    
    # Initialize CDS client
    c = cdsapi.Client()
    
    for attempt in range(retry_attempts):
        temp_filename = None
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.nc', delete=False) as tmp_file:
                temp_filename = tmp_file.name
            
            # Download from CDS API
            c.retrieve(
                'reanalysis-era5-single-levels',
                {
                    'product_type': 'reanalysis',
                    'variable': era5_variables,
                    'year': str(year),
                    'month': f'{month:02d}',
                    'day': [f'{d:02d}' for d in range(1, 32)],
                    'time': [f'{h:02d}:00' for h in range(24)],
                    'area': [
                        latitude + 0.05,
                        era5_lon - 0.05,
                        latitude - 0.05,
                        era5_lon + 0.05
                    ],
                    'format': 'netcdf',
                },
                temp_filename
            )
            
            # Load NetCDF file
            ds = xr.open_dataset(temp_filename, engine='netcdf4')
            
            # Extract data for closest grid point
            ds_point = ds.sel(latitude=latitude, longitude=era5_lon, method='nearest')
            
            # Convert to DataFrame
            df = era5_to_dataframe(ds_point, year)
            
            return df
            
        except requests.exceptions.HTTPError as e:
            error_msg = str(e).lower()
            
            if "400" in str(e) and ("queued" in error_msg or "limit" in error_msg):
                # Rate limit - retry with backoff
                wait_time = (2 ** attempt) * 30  # 30s, 60s, 120s
                if attempt < retry_attempts - 1:
                    time.sleep(wait_time)
                    continue
            
            if attempt == retry_attempts - 1:
                return None
                
        except Exception as e:
            if attempt == retry_attempts - 1:
                return None
            time.sleep(10)
            
        finally:
            # Clean up temp file
            if temp_filename and os.path.exists(temp_filename):
                try:
                    os.unlink(temp_filename)
                except:
                    pass
    
    return None
