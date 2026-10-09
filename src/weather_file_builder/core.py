"""
Core ERA5 data download functionality.

Uses the ecmwf-datastores-client to retrieve ERA5-Land timeseries data
from the Copernicus Climate Data Store.
"""

import logging
import os
import tempfile
import zipfile
from typing import Dict, List, Optional

import pandas as pd

from .converters import era5_to_dataframe
from .utils import (
    check_project_status,
    get_output_path,
    log_message,
    setup_project_directory,
    write_project_config,
    write_tmy_data,
)
from .variables import get_era5_variables

logger = logging.getLogger(__name__)


def download_single_year(
    latitude: float,
    longitude: float,
    year: int,
    variables: Optional[List[str]] = None,
    retry_attempts: int = 3,
) -> pd.DataFrame:
    """Download ERA5 data for a single calendar year.

    Convenience wrapper around the timeseries endpoint that fetches
    Jan 1 through Dec 31 of the given year.

    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees (-90 to 90).
    longitude : float
        Longitude in decimal degrees (-180 to 180).
    year : int
        Year to download (1950 to present).
    variables : list of str, optional
        Variables to download. If None, downloads all available variables.
    retry_attempts : int, default 3
        Number of retry attempts for failed downloads.

    Returns
    -------
    pandas.DataFrame
        Weather data with standardized columns.
    """
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    return download_time_series(
        latitude, longitude, start_date, end_date,
        variables=variables, retry_attempts=retry_attempts,
    )


def download_multi_year(
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
    variables: Optional[List[str]] = None,
    retry_attempts: int = 3,
) -> pd.DataFrame:
    """Download ERA5 data spanning multiple years.

    Convenience wrapper around the timeseries endpoint that fetches
    the full date range from Jan 1 of *start_year* through Dec 31
    of *end_year*.

    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees (-90 to 90).
    longitude : float
        Longitude in decimal degrees (-180 to 180).
    start_year : int
        First year of the range.
    end_year : int
        Last year of the range (inclusive).
    variables : list of str, optional
        Variables to download. If None, downloads all available variables.
    retry_attempts : int, default 3
        Number of retry attempts for failed downloads.

    Returns
    -------
    pandas.DataFrame
        Weather data for all years combined with standardized columns.
    """
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"
    return download_time_series(
        latitude, longitude, start_date, end_date,
        variables=variables, retry_attempts=retry_attempts,
    )


def download_time_series(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variables: Optional[List[str]] = None,
    retry_attempts: int = 3,
) -> pd.DataFrame:
    """Download ERA5-Land timeseries data for a location and date range.

    This is the primary download function. It uses the
    ``reanalysis-era5-land-timeseries`` collection via the
    ``ecmwf-datastores-client``, which returns point-level CSV data
    in a single API call.

    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees (-90 to 90).
    longitude : float
        Longitude in decimal degrees (-180 to 180).
    start_date : str
        Start date in ``YYYY-MM-DD`` format.
    end_date : str
        End date in ``YYYY-MM-DD`` format.
    variables : list of str, optional
        Variables to download. Can be group names (``'temperature'``,
        ``'wind'``, etc.) or ERA5 variable names. If None, downloads
        all available variables.
    retry_attempts : int, default 3
        Number of retry attempts for failed downloads.

    Returns
    -------
    pandas.DataFrame
        Downloaded time series data with standardized columns.
    """
    era5_vars = get_era5_variables(variables)
    logger.info(
        "Downloading ERA5-Land timeseries %s to %s at (%.2f, %.2f)",
        start_date, end_date, latitude, longitude,
    )

    df = _download_time_series(
        latitude, longitude, start_date, end_date, era5_vars, retry_attempts,
    )

    logger.info("Timeseries download complete: %d records", len(df))
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _download_time_series(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    era5_variables: List[str],
    retry_attempts: int = 3,
) -> pd.DataFrame:
    """Execute the CDS API call with retry logic.

    Uses ``ecmwf.datastores.Client`` (ecmwf-datastores-client package).
    """
    from ecmwf.datastores import Client

    client = Client()

    for attempt in range(retry_attempts):
        temp_filename = None

        try:
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                temp_filename = tmp.name

            client.retrieve(
                "reanalysis-era5-land-timeseries",
                {
                    "variable": era5_variables,
                    "location": {"longitude": longitude, "latitude": latitude},
                    "date": [f"{start_date}/{end_date}"],
                    "data_format": "csv",
                },
                temp_filename,
            )

            with zipfile.ZipFile(temp_filename) as z:
                dfs = []
                for csv_name in z.namelist():
                    with z.open(csv_name) as f:
                        df = pd.read_csv(f)
                        df = df.drop(["latitude", "longitude"], axis=1, errors="ignore")
                        dfs.append(df)

            df = dfs[0]
            for other_df in dfs[1:]:
                df = pd.merge(df, other_df, on="valid_time", how="outer")

            df["valid_time"] = pd.to_datetime(df["valid_time"])

            df_renamed = era5_to_dataframe(df, latitude=latitude, longitude=longitude)
            return df_renamed

        except Exception as e:
            logger.warning(
                "Download attempt %d/%d failed: %s", attempt + 1, retry_attempts, e,
            )
            if attempt == retry_attempts - 1:
                raise

        finally:
            if temp_filename and os.path.exists(temp_filename):
                try:
                    os.unlink(temp_filename)
                except OSError:
                    pass

    raise RuntimeError("Download failed after all retry attempts")


# ---------------------------------------------------------------------------
# High-level workflow
# ---------------------------------------------------------------------------

def comprehensive_workflow(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    project_dir: str,
    variables: Optional[List[str]] = None,
    tmy_type: str = "typical",
    method: Optional[str] = None,
    retry_attempts: int = 3,
) -> Dict:
    """Complete workflow: download timeseries, create TMY, generate plots.

    Steps:
    1. Download timeseries data (or load existing).
    2. Save timeseries as feather.
    3. Create TMY from the data.
    4. Save TMY CSV.
    5. Generate visualisation plots for all available variables.
    6. Save all files to an organised project directory.

    Parameters
    ----------
    latitude : float
        Latitude in decimal degrees (-90 to 90).
    longitude : float
        Longitude in decimal degrees (-180 to 180).
    start_date : str
        Start date in ``YYYY-MM-DD`` format.
    end_date : str
        End date in ``YYYY-MM-DD`` format.
    project_dir : str
        Project directory path for all outputs.
    variables : list of str, optional
        Variables to download. If None, downloads all available.
    tmy_type : str, default ``'typical'``
        Type of TMY: ``'typical'``, ``'extreme_warm'``, or ``'extreme_cold'``.
    method : str, optional
        Month selection: ``'iso'`` (ISO 15927-4, default for a typical year),
        ``'zscore'`` (default for the extremes) or ``'ks'``.
    retry_attempts : int, default 3
        Number of retry attempts for failed downloads.

    Returns
    -------
    dict
        Paths to all created files::

            {
                'timeseries_feather': str,
                'tmy_csv': str,
                'plots': dict,
                'selected_years': dict,
                'config_path': str,
                'project_dir': str,
            }
    """
    from . import create_tmy
    from .visualization import create_tmy_plot

    if method is None:
        method = "iso" if tmy_type == "typical" else "zscore"

    project_dir = setup_project_directory(project_dir)
    logger.info("Project directory: %s", project_dir)
    log_message(project_dir, f"Starting comprehensive workflow for ({latitude}, {longitude})")

    config_path = write_project_config(
        project_dir=project_dir,
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        variables=variables,
        tmy_type=tmy_type,
        method=method,
        workflow_type="comprehensive_timeseries",
        retry_attempts=retry_attempts,
    )
    log_message(project_dir, f"Configuration saved to {config_path}")

    status = check_project_status(project_dir)

    # Step 1: Download timeseries data
    logger.info("[1/5] Downloading timeseries data...")
    log_message(project_dir, "Step 1/5: Downloading timeseries data")

    if status["has_timeseries"]:
        logger.info("Timeseries data already exists, skipping download")
        log_message(project_dir, "Timeseries data already exists, skipping download", level="WARNING")
        timeseries_dir = os.path.join(project_dir, "timeseries")
        feather_files = [f for f in os.listdir(timeseries_dir) if f.endswith(".feather")]
        if feather_files:
            timeseries_path = os.path.join(timeseries_dir, feather_files[0])
            df_timeseries = pd.read_feather(timeseries_path)
            logger.info("Loaded existing data: %s", timeseries_path)
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
                retry_attempts=retry_attempts,
            )
            log_message(project_dir, f"Successfully downloaded {len(df_timeseries)} records", level="SUCCESS")
        except Exception as e:
            log_message(project_dir, f"Download failed: {e}", level="ERROR")
            raise

    # Step 2: Save timeseries data
    logger.info("[2/5] Saving timeseries data...")
    log_message(project_dir, "Step 2/5: Saving timeseries data")

    if not status["has_timeseries"]:
        timeseries_path = get_output_path(
            project_dir=project_dir,
            data_type="timeseries",
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            variables=variables,
        )
        df_timeseries.to_feather(timeseries_path)
        logger.info("Saved timeseries: %s (%d records)", timeseries_path, len(df_timeseries))
        log_message(project_dir, f"Timeseries saved: {timeseries_path}", level="SUCCESS")

    # Step 3: Create TMY
    logger.info("[3/5] Creating TMY...")
    log_message(project_dir, "Step 3/5: Creating TMY")

    try:
        tmy_data, selected_years = create_tmy(
            df_timeseries,
            file_type=tmy_type,
            test_method=method,
        )
        log_message(project_dir, f"TMY created using {method} method, type: {tmy_type}", level="SUCCESS")
        log_message(project_dir, f"Selected years: {selected_years}")
    except Exception as e:
        log_message(project_dir, f"TMY creation failed: {e}", level="ERROR")
        raise

    # Step 4: Save TMY CSV
    logger.info("[4/5] Saving TMY data...")
    log_message(project_dir, "Step 4/5: Saving TMY data")

    years = sorted(df_timeseries["Year"].unique())
    tmy_path = get_output_path(
        project_dir=project_dir,
        data_type="tmy",
        latitude=latitude,
        longitude=longitude,
        years=years,
        variables=variables,
    )
    write_tmy_data(tmy_data, tmy_path, latitude=latitude, longitude=longitude, elevation=0)
    logger.info("Saved TMY: %s (%d records)", tmy_path, len(tmy_data))
    log_message(project_dir, f"TMY saved: {tmy_path}", level="SUCCESS")

    # Step 5: Generate plots
    logger.info("[5/5] Generating visualisation plots...")
    log_message(project_dir, "Step 5/5: Generating visualisation plots")
    plot_paths: Dict[str, str] = {}

    import matplotlib.pyplot as plt

    plot_variables = [
        "Temperature", "Dew Point", "Pressure",
        "Relative Humidity", "Wind Speed", "Wind Direction",
        "GHI", "DNI", "DHI", "Precipitation",
    ]

    available_vars = [v for v in plot_variables if v in df_timeseries.columns]
    logger.info("Creating plots for %d variables", len(available_vars))
    log_message(project_dir, f"Creating plots for {len(available_vars)} variables")

    for variable in available_vars:
        try:
            plot_filename = get_output_path(
                project_dir=project_dir,
                data_type="plot",
                latitude=latitude,
                longitude=longitude,
                filename=f"tmy_{variable.lower()}_{min(years)}-{max(years)}_{latitude:.2f}_{longitude:.2f}.png",
            )

            fig = create_tmy_plot(
                multi_year_data=df_timeseries,
                tmy_data=tmy_data,
                selected_years=selected_years,
                latitude=latitude,
                longitude=longitude,
                variable=variable,
                output_path=plot_filename,
                dpi=150,
            )

            plt.close(fig)
            plot_paths[variable] = plot_filename
            log_message(project_dir, f"Created plot for {variable}: {plot_filename}")

        except Exception as e:
            logger.warning("Failed to create plot for %s: %s", variable, e)
            log_message(project_dir, f"Failed to create plot for {variable}: {e}", level="ERROR")
            continue

    logger.info("Workflow complete -- generated %d plots", len(plot_paths))
    log_message(project_dir, f"Workflow complete! Generated {len(plot_paths)} plots", level="SUCCESS")
    log_message(project_dir, "=" * 70)

    return {
        "timeseries_feather": timeseries_path,
        "tmy_csv": tmy_path,
        "plots": plot_paths,
        "selected_years": selected_years,
        "config_path": config_path,
        "project_dir": project_dir,
    }
