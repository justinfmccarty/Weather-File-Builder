"""
Convert ERA5 xarray datasets to standardized pandas DataFrames.
"""

import numpy as np
import pandas as pd
import xarray as xr
from pvlib import irradiance, solarposition


def era5_to_dataframe(ds, latitude: float = None, longitude: float = None, remove_leap_days: bool = True) -> pd.DataFrame:
    """
    Convert ERA5 DataFrame or xarray dataset to standardized DataFrame.
    
    Parameters
    ----------
    ds : pandas.DataFrame or xarray.Dataset
        ERA5 dataset for a single point
    latitude : float, optional
        Latitude of the location (will be added as a column if provided)
    longitude : float, optional
        Longitude of the location (will be added as a column if provided)
    
    Returns
    -------
    pandas.DataFrame
        Standardized weather data with columns:
        Year, Month, Day, Hour, Minute, Latitude, Longitude, Temperature, 
        Dew Point, Pressure, Relative Humidity, Wind Speed, Wind Direction, 
        GHI, DHI, DNI, Cloud Cover, Precipitation
    """
    # If input is xarray Dataset, convert to DataFrame
    if isinstance(ds, xr.Dataset):
        df = ds.to_dataframe().reset_index()
    else:
        df = ds.copy()
    df['valid_time'] = pd.to_datetime(df['valid_time'])
    
    # Extract time components
    df['Year'] = df['valid_time'].dt.year
    df['Month'] = df['valid_time'].dt.month
    df['Day'] = df['valid_time'].dt.day
    df['Hour'] = df['valid_time'].dt.hour
    df['Minute'] = 0  # ERA5 is hourly
    
    # Remove leap days if specified
    if remove_leap_days:
        df = df[~((df['Month'] == 2) & (df['Day'] == 29))].reset_index(drop=True)
    
    # Initialize output columns
    output = pd.DataFrame()
    output['Year'] = df['Year']
    output['Month'] = df['Month']
    output['Day'] = df['Day']
    output['Hour'] = df['Hour']
    output['Minute'] = df['Minute']
    
    # Add location information if provided
    if latitude is not None:
        output['Latitude'] = latitude
    if longitude is not None:
        output['Longitude'] = longitude
    
    # Temperature (K to °C)
    if 't2m' in df.columns:
        output['Temperature'] = df['t2m'] - 273.15
    
    if 'd2m' in df.columns:
        output['Dew Point'] = df['d2m'] - 273.15
    
    # Pressure (Pa to hPa)
    if 'sp' in df.columns:
        output['Pressure'] = df['sp'] / 100.0
    
    # Relative Humidity (calculate from temperature and dew point)
    if 'Temperature' in output.columns and 'Dew Point' in output.columns:
        output['Relative Humidity'] = calculate_relative_humidity(
            output['Temperature'], output['Dew Point']
        )
    
    # Wind (calculate speed and direction from U/V components)
    if 'u10' in df.columns and 'v10' in df.columns:
        output['Wind Speed'] = np.sqrt(df['u10']**2 + df['v10']**2)
        # u10/v10 are the eastward/northward components of the air's motion; the
        # meteorological direction is where the wind comes FROM, hence the minus signs.
        output['Wind Direction'] = wind_direction_from_uv(df['u10'], df['v10'])
    
    # Solar radiation - surface solar downward (J/m² to W/m² - divide by 3600 for hourly accumulation)
    if 'ssrd' in df.columns:
        # ERA5 provides accumulated radiation, need hourly average
        output['GHI'] = df['ssrd'] / 3600.0
        
        # Calculate DNI and DHI using DIRINT method from pvlib
        if latitude is not None and longitude is not None and 'Pressure' in output.columns and 'Dew Point' in output.columns:
            # Reconstruct datetime index from output DataFrame (after leap day removal)
            times = pd.DatetimeIndex(pd.to_datetime(output[['Year', 'Month', 'Day', 'Hour', 'Minute']]))
            
            # Calculate solar position
            solpos = solarposition.get_solarposition(times, latitude, longitude)
            
            # Calculate DNI using DIRINT method
            # Pressure needs to be in Pa (convert from hPa)
            # Use day of year instead of datetime to avoid pandas version issues
            
            
            # Reset index to ensure proper Series alignment
            ghi_series = pd.Series(output['GHI'].values, index=times)
            pressure_series = pd.Series(output['Pressure'].values * 100, index=times)
            temp_dew_series = pd.Series(output['Dew Point'].values, index=times)
            
            dni_dirint = irradiance.dirint(
                ghi_series, 
                solpos['zenith'], 
                times,
                pressure_series,
                temp_dew=temp_dew_series
            )
            
            # Calculate DHI using complete irradiance (closure equation)
            df_complete = irradiance.complete_irradiance(
                solar_zenith=solpos['apparent_zenith'],
                ghi=ghi_series,
                dni=dni_dirint,
                dhi=None
            )
            
            output['DNI'] = dni_dirint.values
            output['DHI'] = df_complete['dhi'].values
        else:
            # Fallback to simplified model if required inputs are missing
            output['DNI'] = output['GHI'] * 0.7
            output['DHI'] = output['GHI'] * 0.3
    
    # Solar radiation - surface thermal downward (J/m² to W/m² - divide by 3600 for hourly accumulation)
    if 'strd' in df.columns:
        output['IR'] = df['strd'] / 3600.0
    
    
    # Cloud cover (0-1 fraction)
    if 'tcc' in df.columns:
        output['Cloud Cover'] = df['tcc']
    
    # Precipitation (m to mm)
    if 'tp' in df.columns:
        output['Precipitation'] = df['tp'] * 1000.0
    
    return output.fillna(0)


def wind_direction_from_uv(u, v):
    """Meteorological wind direction (degrees, 0 = from north, 90 = from east).

    ``u`` and ``v`` are the eastward and northward components of the air's
    motion (ERA5 ``u10``/``v10``). A westerly (u > 0, v = 0) gives 270.
    """
    return (np.degrees(np.arctan2(-np.asarray(u, dtype=float), -np.asarray(v, dtype=float))) + 360.0) % 360.0


#: ERA5-Land time-series CSV column -> station-table column, with the unit conversion.
_ERA5_STATION_COLUMNS = {
    "t2m": ("temp_C", lambda x: x - 273.15),
    "d2m": ("dewpoint_C", lambda x: x - 273.15),
    "sp": ("pressure_Pa", lambda x: x),
    # de-accumulated hourly sums (J/m2, m) labelled at the end of the hour
    "ssrd": ("ghi_Wm2", lambda x: (x / 3600.0).clip(lower=0.0)),
    "strd": ("lw_down_Wm2", lambda x: x / 3600.0),
    "tp": ("precip_mm", lambda x: (x * 1000.0).clip(lower=0.0)),
}


def era5_to_station_table(raw: pd.DataFrame) -> pd.DataFrame:
    """ERA5-Land time-series records as a station table in the upload contract.

    The result has a tz-aware UTC ``timestamp`` column and the column names and
    units of :data:`weather_file_builder.amy.COLUMN_SPEC`, so it can fill gaps
    in a user's station table directly. Unlike :func:`era5_to_dataframe`,
    missing values stay missing and 29 February is kept.

    Timing: the ERA5-Land time-series product de-accumulates radiation and
    precipitation to hourly sums labelled with the end of the hour, so each
    timestamp ends its interval, as the contract requires. Temperature,
    humidity, pressure and wind are instantaneous values at the timestamp.
    Small negative radiation and precipitation from the de-accumulation are
    set to zero. Relative humidity is computed from temperature and dew point.
    """
    if "valid_time" not in raw.columns:
        raise ValueError("ERA5 records need a 'valid_time' column")
    ts = pd.to_datetime(raw["valid_time"])
    ts = ts.dt.tz_localize("UTC") if ts.dt.tz is None else ts.dt.tz_convert("UTC")
    out = pd.DataFrame({"timestamp": ts})
    for src, (name, convert) in _ERA5_STATION_COLUMNS.items():
        if src in raw.columns:
            out[name] = convert(pd.to_numeric(raw[src], errors="coerce")).to_numpy()
    if "temp_C" in out.columns and "dewpoint_C" in out.columns:
        out["rh_pct"] = calculate_relative_humidity(out["temp_C"], out["dewpoint_C"]).clip(0.0, 100.0)
    if "u10" in raw.columns and "v10" in raw.columns:
        u = pd.to_numeric(raw["u10"], errors="coerce").to_numpy()
        v = pd.to_numeric(raw["v10"], errors="coerce").to_numpy()
        out["wind_speed_ms"] = np.hypot(u, v)
        out["wind_dir_deg"] = wind_direction_from_uv(u, v)
    out = out.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    order = ["timestamp", "temp_C", "dewpoint_C", "rh_pct", "pressure_Pa", "ghi_Wm2", "lw_down_Wm2",
             "wind_speed_ms", "wind_dir_deg", "precip_mm"]
    return out[[c for c in order if c in out.columns]]


def calculate_relative_humidity(temp_c: pd.Series, dewpoint_c: pd.Series) -> pd.Series:
    """
    Calculate relative humidity from temperature and dew point using Magnus formula.
    
    Parameters
    ----------
    temp_c : pandas.Series
        Air temperature in °C
    dewpoint_c : pandas.Series
        Dew point temperature in °C
    
    Returns
    -------
    pandas.Series
        Relative humidity in %
    """
    def saturation_vapor_pressure(t):
        """Magnus formula for saturation vapor pressure"""
        return 6.112 * np.exp(17.67 * t / (t + 243.5))
    
    es = saturation_vapor_pressure(temp_c)
    e = saturation_vapor_pressure(dewpoint_c)
    
    return (e / es) * 100.0


def calculate_solar_zenith(
    time_series: pd.Series,
    latitude: float,
    longitude: float
) -> pd.Series:
    """
    Calculate solar zenith angle (simplified calculation).
    
    For production use, consider using pvlib or pysolar for accurate
    solar position calculations.
    
    Parameters
    ----------
    time_series : pandas.Series
        DateTime series
    latitude : float
        Latitude in degrees
    longitude : float
        Longitude in degrees
    
    Returns
    -------
    pandas.Series
        Solar zenith angle in degrees
    """
    # Day of year and hour
    day_of_year = time_series.dt.dayofyear
    hour = time_series.dt.hour + time_series.dt.minute / 60.0
    
    # Solar declination (simplified)
    declination = 23.45 * np.sin(np.radians(360 * (284 + day_of_year) / 365))
    
    # Hour angle
    hour_angle = 15 * (hour - 12)
    
    # Solar zenith angle
    lat_rad = np.radians(latitude)
    dec_rad = np.radians(declination)
    hour_angle_rad = np.radians(hour_angle)
    
    cos_zenith = (
        np.sin(lat_rad) * np.sin(dec_rad) +
        np.cos(lat_rad) * np.cos(dec_rad) * np.cos(hour_angle_rad)
    )
    
    zenith = np.degrees(np.arccos(np.clip(cos_zenith, -1, 1)))
    
    return zenith
