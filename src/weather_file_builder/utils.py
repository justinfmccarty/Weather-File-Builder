import os
import json
from typing import Optional, List
from datetime import datetime, date
from pvlib.location import lookup_altitude

era5_timeseries_col_map = {
        "d2m": "2m_dewpoint_temperature",
        "t2m": "2m_temperature",
        "sp": "surface_pressure",
        "tp": "total_precipitation",
        "ssrd": "surface_solar_radiation_downwards",
        "strd": "surface_thermal_radiation_downwards",
        "skt": "skin_temperature",
        "snowc": "snow_cover",
        "stl1": "soil_temperature_level_1",
        "stl2": "soil_temperature_level_2",
        "stl3": "soil_temperature_level_3",
        "stl4": "soil_temperature_level_4",
        "swvl1": "volumetric_soil_water_level_1",
        "swvl2": "volumetric_soil_water_level_2",
        "swvl3": "volumetric_soil_water_level_3",
        "swvl4": "volumetric_soil_water_level_4",
        "u10": "10m_u_component_of_wind",
        "v10": "10m_v_component_of_wind"
}


def setup_project_directory(project_dir: str) -> str:
    """Create project directory structure if it doesn't exist.
    
    Parameters
    ----------
    project_dir : str
        Path to the project directory
        
    Returns
    -------
    str
        Absolute path to the project directory
    """
    # Convert to absolute path
    project_dir = os.path.abspath(project_dir)
    
    # Create main directory
    os.makedirs(project_dir, exist_ok=True)
    
    # Create subdirectories
    os.makedirs(os.path.join(project_dir, 'timeseries'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'tmy'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'plots'), exist_ok=True)
    
    # Initialize log file if it doesn't exist
    log_path = os.path.join(project_dir, 'project.log')
    if not os.path.exists(log_path):
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Project created: {datetime.now().isoformat()}\n")
            f.write("="*70 + "\n")
    
    return project_dir


def generate_filename(
    data_type: str,
    latitude: float,
    longitude: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[List[int]] = None,
    variables: Optional[List[str]] = None,
    extension: str = 'csv'
) -> str:
    """Generate standardized filename for weather data files.
    
    Parameters
    ----------
    data_type : str
        Type of data: 'timeseries', 'tmy', 'single_year', 'multi_year'
    latitude : float
        Latitude
    longitude : float
        Longitude
    start_date : str, optional
        Start date in YYYY-MM-DD format (for timeseries)
    end_date : str, optional
        End date in YYYY-MM-DD format (for timeseries)
    year : int, optional
        Single year (for single_year)
    years : list of int, optional
        Multiple years (for multi_year or tmy)
    variables : list of str, optional
        Variables included (e.g., ['temperature', 'wind'])
    extension : str, default 'csv'
        File extension without dot. Auto-set to 'feather' for timeseries.
        
    Returns
    -------
    str
        Generated filename
        
    Examples
    --------
    >>> generate_filename('timeseries', 40.7, -74.0, '2020-01-01', '2020-12-31')
    'timeseries_2020-01-01_2020-12-31_40.70_-74.00.feather'
    
    >>> generate_filename('tmy', 40.7, -74.0, years=[2010, 2020])
    'tmy_2010-2020_40.70_-74.00.csv'
    """
    # Auto-select feather format for timeseries
    if data_type == 'timeseries' and extension == 'csv':
        extension = 'feather'
    
    parts = [data_type]
    
    # Add date/year information
    if data_type == 'timeseries' and start_date and end_date:
        parts.append(start_date)
        parts.append(end_date)
    elif data_type == 'single_year' and year:
        parts.append(str(year))
    elif data_type in ['multi_year', 'tmy'] and years:
        if len(years) > 1:
            parts.append(f"{min(years)}-{max(years)}")
        else:
            parts.append(str(years[0]))
    
    # Add location
    parts.append(f"{latitude:.2f}")
    parts.append(f"{longitude:.2f}")
    
    # Add variables if specified
    if variables and len(variables) < 5:  # Only add if not "all"
        var_str = '_'.join(sorted(variables))
        parts.append(var_str)
    
    return '_'.join(parts) + f'.{extension}'


def get_output_path(
    project_dir: str,
    data_type: str,
    latitude: float,
    longitude: float,
    filename: Optional[str] = None,
    **kwargs
) -> str:
    """Get full output path for a file in the project directory.
    
    Parameters
    ----------
    project_dir : str
        Project directory path
    data_type : str
        Type of data: 'timeseries', 'tmy', 'plot'
    latitude : float
        Latitude
    longitude : float
        Longitude
    filename : str, optional
        Custom filename. If None, auto-generates using generate_filename()
    **kwargs
        Additional arguments passed to generate_filename()
        
    Returns
    -------
    str
        Full path to output file
    """
    # Determine subdirectory
    if data_type == 'timeseries':
        subdir = 'timeseries'
    elif data_type == 'tmy':
        subdir = 'tmy'
    elif data_type == 'plot':
        subdir = 'plots'
    else:
        subdir = ''
    
    # Generate filename if not provided
    if filename is None:
        filename = generate_filename(data_type, latitude, longitude, **kwargs)
    
    # Build full path
    if subdir:
        return os.path.join(project_dir, subdir, filename)
    else:
        return os.path.join(project_dir, filename)

def extract_selected_years(tmy_df):
    """Extract the selected years from the TMY DataFrame.

    Args:
        tmy_df (pd.DataFrame): The TMY DataFrame.

    Returns:
        dict: A dictionary mapping each month to its corresponding year.
    """
    selected_years = {}

    for month in tmy_df['Month'].unique():
        tmy_month_data = tmy_df[tmy_df['Month'] == month]
        year = tmy_month_data['Year'].iloc[0]
        selected_years[month] = year

    return selected_years


def unit_conversion(value, source_unit):
    """Basic unit conversion utility.

    Args:
        value (float): The value to convert.
        source_unit (str): The unit of the input value.

    Returns:
        float: The converted value.
    """
    if source_unit == 'K':  # Kelvin to Celsius
        return value - 273.15
    if source_unit == 'Pa':  # Pascals to millibars
        return value / 100.0
    if source_unit == 'J m-2':  # Joules per square meter to Watts per square meter
        # documentation says to deivide by length of time of measuring period in seconds (3600 for hourly)
        return value / 3600.0


def unpack_date(date_str):
    """Unpack a date string in 'YYYY-MM-DD' format into year, month, day integers."""
    year, month, day = map(int, date_str.split('-'))
    return year, month, day


def write_project_config(
    project_dir: str,
    latitude: float,
    longitude: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[List[int]] = None,
    variables: Optional[List[str]] = None,
    tmy_type: Optional[str] = None,
    method: Optional[str] = None,
    workflow_type: str = 'unknown',
    **kwargs
) -> str:
    """Write project configuration file.
    
    Creates a config.json file in the project directory containing all
    parameters used for this project. This allows users to review what
    was done and enables resuming failed workflows.
    
    Parameters
    ----------
    project_dir : str
        Project directory path
    latitude : float
        Latitude
    longitude : float
        Longitude
    start_date : str, optional
        Start date (YYYY-MM-DD)
    end_date : str, optional
        End date (YYYY-MM-DD)
    year : int, optional
        Single year
    years : list of int, optional
        Multiple years
    variables : list of str, optional
        Variables downloaded
    tmy_type : str, optional
        TMY type (typical, extreme_warm, extreme_cold)
    method : str, optional
        Statistical method (zscore, ks)
    workflow_type : str
        Type of workflow: 'single_year', 'timeseries', 'workflow', 'tmy'
    **kwargs
        Additional parameters to save
        
    Returns
    -------
    str
        Path to the config file
        
    Examples
    --------
    >>> write_project_config('./my_project', 40.7, -74.0, 
    ...                      start_date='2010-01-01', end_date='2020-12-31',
    ...                      variables=['temperature', 'wind'])
    './my_project/config.json'
    """
    config_path = os.path.join(project_dir, 'config.json')
    
    config = {
        'created': datetime.now().isoformat(),
        'workflow_type': workflow_type,
        'location': {
            'latitude': latitude,
            'longitude': longitude
        }
    }
    
    # Add date/year information
    if start_date:
        config['start_date'] = start_date
    if end_date:
        config['end_date'] = end_date
    if year:
        config['year'] = year
    if years:
        config['years'] = years
    
    # Add variables
    if variables:
        config['variables'] = variables
    else:
        config['variables'] = 'all'
    
    # Add TMY settings
    if tmy_type:
        config['tmy_type'] = tmy_type
    if method:
        config['method'] = method
    
    # Add any additional parameters
    for key, value in kwargs.items():
        if key not in config:
            config[key] = value
    
    # Write config file
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    return config_path


def read_project_config(project_dir: str) -> Optional[dict]:
    """Read project configuration file.
    
    Parameters
    ----------
    project_dir : str
        Project directory path
        
    Returns
    -------
    dict or None
        Configuration dictionary, or None if file doesn't exist
        
    Examples
    --------
    >>> config = read_project_config('./my_project')
    >>> print(config['location']['latitude'])
    40.7
    """
    config_path = os.path.join(project_dir, 'config.json')
    
    if not os.path.exists(config_path):
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Warning: Could not read config file: {e}")
        return None


def log_message(project_dir: str, message: str, level: str = 'INFO'):
    """Append a message to the project log file.
    
    Parameters
    ----------
    project_dir : str
        Project directory path
    message : str
        Log message
    level : str, default 'INFO'
        Log level: 'INFO', 'WARNING', 'ERROR', 'SUCCESS'
        
    Examples
    --------
    >>> log_message('./my_project', 'Starting download...')
    >>> log_message('./my_project', 'Download failed', level='ERROR')
    """
    log_path = os.path.join(project_dir, 'project.log')
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    
    with open(log_path, 'a') as f:
        f.write(log_entry)


def read_project_log(project_dir: str) -> Optional[str]:
    """Read the project log file.
    
    Parameters
    ----------
    project_dir : str
        Project directory path
        
    Returns
    -------
    str or None
        Log contents, or None if file doesn't exist
    """
    log_path = os.path.join(project_dir, 'project.log')
    
    if not os.path.exists(log_path):
        return None
    
    try:
        with open(log_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not read log file: {e}")
        return None


def check_project_status(project_dir: str) -> dict:
    """Check the status of a project directory.
    
    Examines the project directory to determine what has been completed.
    
    Parameters
    ----------
    project_dir : str
        Project directory path
        
    Returns
    -------
    dict
        Status dictionary with keys:
        - exists: bool - project directory exists
        - has_config: bool - config file exists
        - has_log: bool - log file exists
        - has_timeseries: bool - timeseries data exists
        - has_tmy: bool - TMY data exists
        - has_plots: bool - plots exist
        - config: dict - configuration if available
        
    Examples
    --------
    >>> status = check_project_status('./my_project')
    >>> if status['has_tmy']:
    ...     print("TMY already created!")
    """
    status = {
        'exists': os.path.exists(project_dir),
        'has_config': False,
        'has_log': False,
        'has_timeseries': False,
        'has_tmy': False,
        'has_plots': False,
        'config': None
    }
    
    if not status['exists']:
        return status
    
    # Check for config file
    config_path = os.path.join(project_dir, 'config.json')
    status['has_config'] = os.path.exists(config_path)
    if status['has_config']:
        status['config'] = read_project_config(project_dir)
    
    # Check for log file
    log_path = os.path.join(project_dir, 'project.log')
    status['has_log'] = os.path.exists(log_path)
    
    # Check for timeseries data
    timeseries_dir = os.path.join(project_dir, 'timeseries')
    if os.path.exists(timeseries_dir):
        feather_files = [f for f in os.listdir(timeseries_dir) if f.endswith('.feather')]
        status['has_timeseries'] = len(feather_files) > 0
    
    # Check for TMY data
    tmy_dir = os.path.join(project_dir, 'tmy')
    if os.path.exists(tmy_dir):
        csv_files = [f for f in os.listdir(tmy_dir) if f.endswith('.csv')]
        status['has_tmy'] = len(csv_files) > 0
    
    # Check for plots
    plots_dir = os.path.join(project_dir, 'plots')
    if os.path.exists(plots_dir):
        plot_files = [f for f in os.listdir(plots_dir) if f.endswith('.png')]
        status['has_plots'] = len(plot_files) > 0
    
    return status

def write_tmy_data(tmy_df, output_path: str, latitude: float = None, longitude: float = None, elevation: float = None):
    """Write TMY DataFrame to CSV file with proper TMY format header.
    
    The TMY file format includes:
    - First 4 lines: Project metadata (latitude, longitude, elevation, irradiance offset)
    - Next 13 lines: Month-year selection table showing which year was selected for each month
    - Remaining lines: Weather data with columns: time(UTC), T2m, RH, G(h), Gb(n), Gd(h), IR(h), WS10m, WD10m, SP

    Args:
        tmy_df (pd.DataFrame): The TMY DataFrame with standardized column names.
        output_path (str): Path to save the CSV file.
        latitude (float, optional): Project latitude in decimal degrees. Extracted from DataFrame if not provided.
        longitude (float, optional): Project longitude in decimal degrees. Extracted from DataFrame if not provided.
        elevation (float, optional): Project elevation in meters. Defaults to 0 if not provided.
    """
    import pandas as pd
    
    # Extract location info from DataFrame if not provided
    if latitude is None and 'Latitude' in tmy_df.columns:
        latitude = tmy_df['Latitude'].iloc[0]
    if longitude is None and 'Longitude' in tmy_df.columns:
        longitude = tmy_df['Longitude'].iloc[0]
    # if elevation is None:
    elevation = lookup_altitude(latitude, longitude)
    current_year = str(int(date.today().year))
    # Set default values if still None
    if latitude is None:
        latitude = 0.0
    if longitude is None:
        longitude = 0.0
    
    # Irradiance time offset - 0.500 for ERA5 (not location-dependent)
    # https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-tools/pvgis-typical-meteorological-year-tmy-generator_en
    irradiance_time_offset = 0.500
    
    # Extract selected years for each month
    selected_years = extract_selected_years(tmy_df)
    
    # Create the TMY format output file
    with open(output_path, 'w', encoding='utf-8') as f:
        # Write header (first 4 lines)
        f.write(f"Latitude (decimal degrees): {latitude}\n")
        f.write(f"Longitude (decimal degrees): {longitude}\n")
        f.write(f"Elevation (m): {elevation}\n")
        f.write(f"Irradiance Time Offset (h): {irradiance_time_offset}\n")
        
        # Write month-year selection table (13 lines: header + 12 months)
        f.write("month,year\n")
        for month in range(1, 13):
            year = selected_years.get(month, 'N/A')
            f.write(f"{month},{year}\n")
        
        # Prepare data columns in TMY format
        # Map standardized column names to TMY format
        tmy_output = pd.DataFrame()
        
        # Create time column in YYYYMMDD:HHMM format
        if all(col in tmy_df.columns for col in ['Year', 'Month', 'Day', 'Hour']):
            minute = tmy_df['Minute'] if 'Minute' in tmy_df.columns else 0
            tmy_output['time(UTC)'] = (
                current_year +
                tmy_df['Month'].astype(str).str.zfill(2) +
                tmy_df['Day'].astype(str).str.zfill(2) + ':' +
                tmy_df['Hour'].astype(str).str.zfill(2) +
                minute.astype(str).str.zfill(2)
            )
        
        # T2m - 2-meter temperature (°C)
        if 'Temperature' in tmy_df.columns:
            tmy_output['T2m'] = tmy_df['Temperature']
        
        # RH - Relative Humidity (%)
        if 'Relative Humidity' in tmy_df.columns:
            tmy_output['RH'] = tmy_df['Relative Humidity']
        
        # G(h) - Global Horizontal Irradiance (W/m²)
        if 'GHI' in tmy_df.columns:
            tmy_output['G(h)'] = tmy_df['GHI']
        
        # Gb(n) - Direct Normal Irradiance (W/m²)
        if 'DNI' in tmy_df.columns:
            tmy_output['Gb(n)'] = tmy_df['DNI']
        
        # Gd(h) - Diffuse Horizontal Irradiance (W/m²)
        if 'DHI' in tmy_df.columns:
            tmy_output['Gd(h)'] = tmy_df['DHI']
        
        # IR(h) - Infrared Radiation Horizontal (W/m²)
        # Use thermal radiation if available
        if 'Thermal Radiation' in tmy_df.columns:
            tmy_output['IR(h)'] = tmy_df['Thermal Radiation']
        elif 'strd' in tmy_df.columns:
            tmy_output['IR(h)'] = tmy_df['strd'] / 3600.0
        
        # WS10m - Wind Speed at 10m (m/s)
        if 'Wind Speed' in tmy_df.columns:
            tmy_output['WS10m'] = tmy_df['Wind Speed']
        
        # WD10m - Wind Direction at 10m (degrees)
        if 'Wind Direction' in tmy_df.columns:
            tmy_output['WD10m'] = tmy_df['Wind Direction']
        
        # SP - Surface Pressure (hPa or mbar)
        if 'Pressure' in tmy_df.columns:
            tmy_output['SP'] = tmy_df['Pressure'] * 100  # Convert hPa to Pa
        
        # Write the data to CSV (append to existing file)
        tmy_output.fillna(0, inplace=True)  # Replace NaNs with 0
        tmy_output.to_csv(f, index=False, mode='a')