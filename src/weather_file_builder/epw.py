"""
EnergyPlus Weather (EPW) file generation.
"""

import pandas as pd
from typing import Optional


def create_epw(
    data: pd.DataFrame,
    output_path: str,
    location_name: str,
    latitude: float,
    longitude: float,
    timezone: float,
    elevation: float = 0
) -> None:
    """
    Create an EPW (EnergyPlus Weather) file from weather data.
    
    Parameters
    ----------
    data : pandas.DataFrame
        Weather data DataFrame with standardized columns
    output_path : str
        Path to output EPW file
    location_name : str
        Location name (e.g., "New York City, NY, USA")
    latitude : float
        Latitude in decimal degrees
    longitude : float
        Longitude in decimal degrees
    timezone : float
        Timezone offset from UTC (e.g., -5 for EST)
    elevation : float, default 0
        Elevation in meters above sea level
    
    Examples
    --------
    >>> create_epw(df, "weather.epw", "New York, NY", 40.7, -74.0, -5, 10)
    """
    # TODO: Implement EPW file generation
    # For now, save as CSV
    print(f"EPW generation not yet implemented. Saving as CSV: {output_path}.csv")
    data.to_csv(f"{output_path}.csv", index=False)
    
    # EPW format specification:
    # https://designbuilder.co.uk/cahelp/Content/EnergyPlusWeatherFileFormat.htm
    # 
    # Header lines (8 lines):
    # 1. LOCATION
    # 2. DESIGN CONDITIONS
    # 3. TYPICAL/EXTREME PERIODS
    # 4. GROUND TEMPERATURES
    # 5. HOLIDAYS/DAYLIGHT SAVING
    # 6. COMMENTS 1
    # 7. COMMENTS 2
    # 8. DATA PERIODS
    # 
    # Data lines: Year,Month,Day,Hour,Minute,DataSourceandUncertaintyFlags,
    #             DryBulbTemperature,DewPointTemperature,RelativeHumidity,
    #             AtmosphericStationPressure,ExtraterrestrialHorizontalRadiation,
    #             ExtraterrestrialDirectNormalRadiation,HorizontalInfraredRadiationIntensity,
    #             GlobalHorizontalRadiation,DirectNormalRadiation,DiffuseHorizontalRadiation,
    #             GlobalHorizontalIlluminance,DirectNormalIlluminance,DiffuseHorizontalIlluminance,
    #             ZenithLuminance,WindDirection,WindSpeed,TotalSkyCover,OpaqueSkyCover,
    #             Visibility,CeilingHeight,PresentWeatherObservation,PresentWeatherCodes,
    #             PrecipitableWater,AerosolOpticalDepth,SnowDepth,DaysSinceLastSnowfall,
    #             Albedo,LiquidPrecipitationDepth,LiquidPrecipitationQuantity
    
    raise NotImplementedError("EPW file generation is not yet implemented")
