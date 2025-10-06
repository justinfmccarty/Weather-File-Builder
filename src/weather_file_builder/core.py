"""
Core ERA5 data download functionality.
"""

import cdsapi
import pandas as pd
import numpy as np
import tempfile
import os
import time
import requests
import asyncio
import zipfile
import xarray as xr
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Union

from .utils import unpack_date
from .variables import get_era5_variables
from .converters import era5_to_dataframe
from .utils import (
    era5_timeseries_col_map, 
    setup_project_directory, 
    get_output_path,
    write_project_config,
    log_message,
    check_project_status,
    write_tmy_data
)

def download_time_series(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variables: Optional[List[str]] = None,
    retry_attempts: int = 3
) -> pd.DataFrame:  
    """Download ERA5 time series data for a specific location and time range.
    
    This function uses the ERA5-Land timeseries API, which is faster than the
    standard monthly downloads but has a more limited variable set. It's the
    recommended method for downloading continuous time series data.

    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees (-90 to 90)
    longitude : float
        Longitude in decimal degrees (-180 to 180)
    start_date : str
        Start date in 'YYYY-MM-DD' format
    end_date : str
        End date in 'YYYY-MM-DD' format
    variables : list of str, optional
        Variables to download. If None, downloads all available variables.
        Note: ERA5-Land timeseries has a limited variable set compared to
        the full ERA5 reanalysis.
    retry_attempts : int, default 3
        Number of retry attempts for failed downloads

    Returns
    -------
    pandas.DataFrame
        Downloaded time series data with standardized columns
        
    Examples
    --------
    >>> df = download_time_series(40.7, -74.0, '2020-01-01', '2020-12-31')
    >>> print(df.shape)
    (8784, 15)
    
    >>> df = download_time_series(40.7, -74.0, '2020-06-01', '2020-06-30',
    ...                          variables=['temperature', 'wind'])
    """
    start_year, start_month, start_day = unpack_date(start_date)
    end_year, end_month, end_day = unpack_date(end_date)
    
    print(f"Downloading ERA5 timeseries data for {start_year}-{start_month:02d}-{start_day:02d} to {end_year}-{end_month:02d}-{end_day:02d} at ({latitude:.2f}, {longitude:.2f})")
    
    # Convert variable names to ERA5 format
    era5_vars = get_era5_variables(variables)
    
    df_timeseries = _download_time_series(
        latitude, longitude, start_year, end_year, start_month, end_month, 
        start_day, end_day, era5_vars, retry_attempts
    )
    
    print(f"✓ Timeseries download complete: {len(df_timeseries)} records")
    
    return df_timeseries
    


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

# async def _download_timeseries_async(
#     latitude: float,
#     longitude: float,
#     start_year: int,
#     end_year: int,
#     era5_vars: List[str],
#     retry_attempts: int,
#     max_workers: int
# ) -> List[pd.DataFrame]:
#     """
#     Async function to download 
#     """
#     df_timeseries = None    
#     try:
#         df_timeseries = await _download_timeseries_async(
#             latitude, longitude, start_year, end_year, era5_vars, retry_attempts, max_workers
#         )
#     except Exception as e:
#         print(f"  ✗ Timeseries failed - {e}")
    
#     return df_timeseries


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
    # era5_lon = longitude + 360 if longitude < 0 else longitude
    
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
                        longitude - 0.05,
                        latitude - 0.05,
                        longitude + 0.05
                    ],
                    'format': 'netcdf',
                },
                temp_filename
            )
            
            # Load NetCDF file
            ds = xr.open_dataset(temp_filename, engine='netcdf4')
            
            # Extract data for closest grid point
            ds_point = ds.sel(latitude=latitude, longitude=longitude, method='nearest')
            
            # Convert to DataFrame
            df = era5_to_dataframe(ds_point, latitude=latitude, longitude=longitude)
            
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

def _download_time_series(
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
    start_month: int,
    end_month: int,
    start_day: int,
    end_day: int,
    era5_variables: List[str],
    retry_attempts: int = 3
) -> Optional[pd.DataFrame]:
    """
    Download ERA5 timeseries data with retry logic.
    
    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees
    longitude : float
        Longitude in decimal degrees
    start_year : int
        Start Year
    end_year : int
        End Year
    start_month : int
        Start Month (1-12)
    end_month : int 
        End Month (1-12)
    start_day : int
        Start Day (1-31)
    end_day : int
        End Day (1-31)
    era5_variables : list of str
        ERA5 variable names for API request
    retry_attempts : int
        Number of retry attempts
    
    Returns
    -------
    pandas.DataFrame or None
        Weather data for the requested time series
    """
    # Initialize CDS client
    c = cdsapi.Client()
    
    for attempt in range(retry_attempts):
        temp_filename = None
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
                temp_filename = tmp_file.name
            
            # Download from CDS API
            c.retrieve(
                'reanalysis-era5-land-timeseries',
                {
                    'variable': era5_variables,
                    'location': {"longitude": longitude, "latitude": latitude},
                    "date": [f"{start_year}-{start_month:02d}-{start_day:02d}/{end_year}-{end_month:02d}-{end_day:02d}"],
                    'data_format': 'csv',
                },
                temp_filename
            )
            
            # Read the zip file containing CSVs
            with zipfile.ZipFile(temp_filename) as z:
                dfs = []
                for csv_name in z.namelist():
                    # Read each CSV into a dataframe
                    with z.open(csv_name) as f:
                        df = pd.read_csv(f)
                        # Drop lat/lon columns as they are constant for point data
                        df = df.drop(['latitude', 'longitude'], axis=1, errors='ignore')
                        dfs.append(df)
            
            # Merge all dataframes on valid_time
            df = dfs[0]
            for other_df in dfs[1:]:
                df = pd.merge(df, other_df, on='valid_time', how='outer')
            
            # Convert time column to datetime
            df['valid_time'] = pd.to_datetime(df['valid_time'])
            
            # Convert to standardized format
            df_renamed = era5_to_dataframe(df, latitude=latitude, longitude=longitude)
            
            return df_renamed
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"  Rate limit hit. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                print(f"  HTTP error: {e}")
                if attempt == retry_attempts - 1:
                    raise
                    
        except Exception as e:
            print(f"  Error on attempt {attempt + 1}/{retry_attempts}: {e}")
            if attempt == retry_attempts - 1:
                raise
                
        finally:
            # Clean up temporary file
            if temp_filename and os.path.exists(temp_filename):
                try:
                    os.unlink(temp_filename)
                except:
                    pass
    
    return None


def comprehensive_timeseries_workflow(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    project_dir: str,
    variables: Optional[List[str]] = None,
    tmy_type: str = 'typical',
    method: str = 'zscore',
    retry_attempts: int = 3
) -> dict:
    """Complete workflow: download timeseries, create TMY, generate all visualizations.
    
    This is a comprehensive function that:
    1. Downloads timeseries data
    2. Saves timeseries CSV
    3. Creates TMY from the data
    4. Saves TMY CSV
    5. Generates visualization plots for all available variables
    6. Saves all files to organized project directory
    
    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees (-90 to 90)
    longitude : float
        Longitude in decimal degrees (-180 to 180)
    start_date : str
        Start date in 'YYYY-MM-DD' format
    end_date : str
        End date in 'YYYY-MM-DD' format
    project_dir : str
        Project directory path for all outputs
    variables : list of str, optional
        Variables to download. If None, downloads all available.
    tmy_type : str, default 'typical'
        Type of TMY: 'typical', 'extreme_warm', or 'extreme_cold'
    method : str, default 'zscore'
        Statistical method: 'zscore' or 'ks'
    retry_attempts : int, default 3
        Number of retry attempts for failed downloads
        
    Returns
    -------
    dict
        Dictionary with paths to all created files:
        {
            'timeseries_feather': str,
            'tmy_csv': str,
            'plots': dict with variable names as keys and plot paths as values,
            'selected_years': dict,
            'config_path': str,
            'project_dir': str
        }
        
    Examples
    --------
    >>> results = comprehensive_timeseries_workflow(
    ...     40.7, -74.0, '2010-01-01', '2020-12-31', './my_project'
    ... )
    >>> print(results['tmy_csv'])
    './my_project/tmy/tmy_2010-2020_40.70_-74.00.csv'
    """
    from . import create_tmy
    from .visualization import create_tmy_plot
    
    # Setup project directory
    project_dir = setup_project_directory(project_dir)
    print(f"Project directory: {project_dir}")
    log_message(project_dir, f"Starting comprehensive workflow for ({latitude}, {longitude})")
    
    # Write configuration file
    config_path = write_project_config(
        project_dir=project_dir,
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        variables=variables,
        tmy_type=tmy_type,
        method=method,
        workflow_type='comprehensive_timeseries',
        retry_attempts=retry_attempts
    )
    log_message(project_dir, f"Configuration saved to {config_path}")
    print(f"Configuration saved: {config_path}")
    
    # Check if we can resume
    status = check_project_status(project_dir)
    
    # Step 1: Download timeseries data
    print("\n[1/5] Downloading timeseries data...")
    log_message(project_dir, "Step 1/5: Downloading timeseries data")
    
    if status['has_timeseries']:
        print("  ⚠ Timeseries data already exists, skipping download...")
        log_message(project_dir, "Timeseries data already exists, skipping download", level='WARNING')
        # Try to load existing data
        timeseries_dir = os.path.join(project_dir, 'timeseries')
        feather_files = [f for f in os.listdir(timeseries_dir) if f.endswith('.feather')]
        if feather_files:
            import pandas as pd
            timeseries_path = os.path.join(timeseries_dir, feather_files[0])
            df_timeseries = pd.read_feather(timeseries_path)
            print(f"  Loaded existing data: {timeseries_path}")
            log_message(project_dir, f"Loaded existing timeseries: {timeseries_path}")
        else:
            raise FileNotFoundError("Timeseries directory exists but no feather files found")
    else:
        try:
            df_timeseries = download_time_series(
                latitude=latitude,
                longitude=longitude,
                start_date=start_date,
                end_date=end_date,
                variables=variables,
                retry_attempts=retry_attempts
            )
            log_message(project_dir, f"Successfully downloaded {len(df_timeseries)} records", level='SUCCESS')
        except Exception as e:
            log_message(project_dir, f"Download failed: {e}", level='ERROR')
            raise
    
    # Step 2: Save timeseries data (feather format)
    print("\n[2/5] Saving timeseries data...")
    log_message(project_dir, "Step 2/5: Saving timeseries data")
    
    if not status['has_timeseries']:
        timeseries_path = get_output_path(
            project_dir=project_dir,
            data_type='timeseries',
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            variables=variables
        )
        df_timeseries.to_feather(timeseries_path)
        print(f"✓ Saved: {timeseries_path}")
        print(f"  {len(df_timeseries)} records, {len(df_timeseries.columns)} columns")
        print(f"  Format: Feather (fast, compressed)")
        log_message(project_dir, f"Timeseries saved: {timeseries_path}", level='SUCCESS')
    else:
        print("  ✓ Already saved")
    
    # Step 3: Create TMY
    print("\n[3/5] Creating TMY...")
    log_message(project_dir, "Step 3/5: Creating TMY")
    
    try:
        tmy_data, selected_years = create_tmy(
            df_timeseries,
            file_type=tmy_type,
            test_method=method
        )
        log_message(project_dir, f"TMY created using {method} method, type: {tmy_type}", level='SUCCESS')
        log_message(project_dir, f"Selected years: {selected_years}")
    except Exception as e:
        log_message(project_dir, f"TMY creation failed: {e}", level='ERROR')
        raise
    
    # Step 4: Save TMY CSV
    print("\n[4/5] Saving TMY data...")
    log_message(project_dir, "Step 4/5: Saving TMY data")
    years = sorted(df_timeseries['Year'].unique())
    tmy_path = get_output_path(
        project_dir=project_dir,
        data_type='tmy',
        latitude=latitude,
        longitude=longitude,
        years=years,
        variables=variables
    )
    write_tmy_data(tmy_data, tmy_path, latitude=latitude, longitude=longitude, elevation=0)
    print(f"✓ Saved: {tmy_path}")
    print(f"  {len(tmy_data)} records")
    print(f"  Selected years by month: {selected_years}")
    log_message(project_dir, f"TMY saved: {tmy_path}", level='SUCCESS')
    
    # Step 5: Generate plots for all variables
    print("\n[5/5] Generating visualization plots...")
    log_message(project_dir, "Step 5/5: Generating visualization plots")
    plot_paths = {}
    
    # Determine which variables to plot
    plot_variables = [
        'Temperature', 'Dew Point', 'Pressure',
        'Relative Humidity', 'Wind Speed', 'Wind Direction',
        'GHI', 'DNI', 'DHI', 'Precipitation',
    ]
    
    # Filter to only variables present in data
    available_vars = [v for v in plot_variables if v in df_timeseries.columns]
    
    print(f"Creating plots for {len(available_vars)} variables...")
    log_message(project_dir, f"Creating plots for {len(available_vars)} variables")
    
    for variable in available_vars:
        try:
            print(f"  Plotting {variable}...", end=" ", flush=True)
            
            # Generate plot filename
            plot_filename = get_output_path(
                project_dir=project_dir,
                data_type='plot',
                latitude=latitude,
                longitude=longitude,
                filename=f"tmy_{variable.lower()}_{min(years)}-{max(years)}_{latitude:.2f}_{longitude:.2f}.png"
            )
            
            # Create plot
            fig = create_tmy_plot(
                multi_year_data=df_timeseries,
                tmy_data=tmy_data,
                selected_years=selected_years,
                latitude=latitude,
                longitude=longitude,
                variable=variable,
                output_path=plot_filename,
                dpi=150
            )
            
            # Close figure to free memory
            import matplotlib.pyplot as plt
            plt.close(fig)
            
            plot_paths[variable] = plot_filename
            print("✓")
            log_message(project_dir, f"Created plot for {variable}: {plot_filename}")
            
        except Exception as e:
            print(f"✗ ({e})")
            log_message(project_dir, f"Failed to create plot for {variable}: {e}", level='ERROR')
            continue
    
    print(f"\n✓ Complete! Generated {len(plot_paths)} plots")
    log_message(project_dir, f"Workflow complete! Generated {len(plot_paths)} plots", level='SUCCESS')
    log_message(project_dir, "="*70)
    
    # Return all file paths
    return {
        'timeseries_feather': timeseries_path,
        'tmy_csv': tmy_path,
        'plots': plot_paths,
        'selected_years': selected_years,
        'config_path': config_path,
        'project_dir': project_dir
    }
