"""
ERA5 variable definitions and groupings.
"""

from typing import List, Dict

# ERA5 variable names mapped to friendly names
TEMPERATURE = {
    '2m_temperature': 'Temperature',
    '2m_dewpoint_temperature': 'Dew Point',
    'skin_temperature': 'Skin Temperature',
}

PRESSURE = {
    'surface_pressure': 'Pressure',
    'mean_sea_level_pressure': 'Sea Level Pressure',
    
}

WIND = {
    '10m_u_component_of_wind': 'Wind U',
    '10m_v_component_of_wind': 'Wind V',
}

SOLAR = {
    'surface_solar_radiation_downwards': 'Solar Radiation',
    'surface_thermal_radiation_downwards': 'Thermal Radiation',
    # 'total_cloud_cover': 'Cloud Cover',
}

PRECIPITATION = {
    'total_precipitation': 'Precipitation',
}

# Complete variable set
ALL_VARIABLES = {
    **TEMPERATURE,
    **PRESSURE,
    **WIND,
    **SOLAR,
    **PRECIPITATION,
}

# Variable groups for easy selection
VARIABLE_GROUPS = {
    'temperature': TEMPERATURE,
    'pressure': PRESSURE,
    'wind': WIND,
    'solar': SOLAR,
    'precipitation': PRECIPITATION,
    'all': ALL_VARIABLES,
}


def get_era5_variables(variables: List[str] = None) -> List[str]:
    """
    Convert variable group names to ERA5 variable names.
    reanalysis_timeseries_variables = [
        "2m_dewpoint_temperature",
        "mean_sea_level_pressure",
        "skin_temperature",
        "surface_pressure",
        "surface_solar_radiation_downwards",
        "surface_thermal_radiation_downwards",
        "2m_temperature",
        "total_precipitation",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind"
    ]
    Parameters
    ----------
    variables : list of str, optional
        Variable groups or ERA5 variable names. If None, returns all variables.
        Can be: 'temperature', 'pressure', 'wind', 'solar', 'precipitation', 'all'
        Or specific ERA5 variable names like '2m_temperature'
    
    Returns
    -------
    list of str
        ERA5 variable names for CDS API request
    
    Examples
    --------
    >>> get_era5_variables(['temperature', 'pressure'])
    ['2m_temperature', '2m_dewpoint_temperature', 'surface_pressure']
    
    >>> get_era5_variables()  # All variables
    ['2m_temperature', '2m_dewpoint_temperature', 'surface_pressure', ...]
    """
    if variables is None or 'all' in variables:
        return list(ALL_VARIABLES.keys())
    
    era5_vars = []
    for var in variables:
        if var in VARIABLE_GROUPS:
            # It's a group name
            era5_vars.extend(VARIABLE_GROUPS[var].keys())
        elif var in ALL_VARIABLES:
            # It's already an ERA5 variable name
            era5_vars.append(var)
        else:
            raise ValueError(f"Unknown variable or group: {var}")
    
    # Remove duplicates while preserving order
    seen = set()
    return [x for x in era5_vars if not (x in seen or seen.add(x))]


def get_friendly_names() -> Dict[str, str]:
    """
    Get mapping of ERA5 variable names to friendly display names.
    
    Returns
    -------
    dict
        Mapping of ERA5 names to friendly names
    """
    return ALL_VARIABLES.copy()
