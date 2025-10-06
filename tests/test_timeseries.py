# import unittest
from weather_file_builder.core import download_time_series

# class TestTimeSeries(unittest.TestCase):
def test_download_time_series():
    # Example parameters
    location = (40.7128, -74.0060)  # New York City coordinates
    # location = (47.43378045514501, 8.546530045004372)  # Zurich coordinates
    start_date = "1993-01-01"
    end_date = "1994-12-31"
    variables = [
        "2m_dewpoint_temperature",
        "2m_temperature",
        "surface_pressure",
        "total_precipitation",
        "surface_solar_radiation_downwards",
        "surface_thermal_radiation_downwards",
        "skin_temperature",
        "snow_cover",
        "soil_temperature_level_1",
        "soil_temperature_level_2",
        "soil_temperature_level_3",
        "soil_temperature_level_4",
        "volumetric_soil_water_level_1",
        "volumetric_soil_water_level_2",
        "volumetric_soil_water_level_3",
        "volumetric_soil_water_level_4",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind"
    ]
    # Call the function
    result = download_time_series(location[0], location[1], start_date, end_date, variables=variables)
    print(result.head())
    result.to_csv("/Users/jmccarty/Desktop/test_tmy_builder/test_timeseries_output.csv", index=False)
if __name__ == '__main__':
    test_download_time_series()