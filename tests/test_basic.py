"""
Basic tests for weather-file-builder.
"""

import pytest
import pandas as pd
from weather_file_builder.variables import get_era5_variables, TEMPERATURE, WIND
from weather_file_builder.converters import calculate_relative_humidity


def test_get_era5_variables_all():
    """Test getting all variables."""
    variables = get_era5_variables()
    assert isinstance(variables, list)
    assert len(variables) > 0
    assert '2m_temperature' in variables


def test_get_era5_variables_groups():
    """Test variable group selection."""
    temp_vars = get_era5_variables(['temperature'])
    assert '2m_temperature' in temp_vars
    assert '2m_dewpoint_temperature' in temp_vars
    
    wind_vars = get_era5_variables(['wind'])
    assert '10m_u_component_of_wind' in wind_vars
    assert '10m_v_component_of_wind' in wind_vars


def test_get_era5_variables_mixed():
    """Test mixed groups and specific variables."""
    variables = get_era5_variables(['temperature', 'surface_pressure'])
    assert '2m_temperature' in variables
    assert 'surface_pressure' in variables


def test_calculate_relative_humidity():
    """Test relative humidity calculation."""
    temp = pd.Series([20.0, 25.0, 30.0])
    dewpoint = pd.Series([15.0, 20.0, 25.0])
    
    rh = calculate_relative_humidity(temp, dewpoint)
    
    assert isinstance(rh, pd.Series)
    assert len(rh) == 3
    assert all(rh >= 0)
    assert all(rh <= 100)
    # RH should be close to 73%, 79%, 84% for these values
    assert 70 < rh.iloc[0] < 76
    assert 76 < rh.iloc[1] < 82
    assert 81 < rh.iloc[2] < 87


def test_variables_constants():
    """Test that variable constants are properly defined."""
    assert isinstance(TEMPERATURE, dict)
    assert isinstance(WIND, dict)
    assert '2m_temperature' in TEMPERATURE
    assert '10m_u_component_of_wind' in WIND


# Integration tests (these require CDS API access and are slow)
# Mark them to be skipped by default

@pytest.mark.slow
@pytest.mark.integration
def test_download_weather_data():
    """Test actual data download (requires CDS API)."""
    from weather_file_builder import download_weather_data
    
    # Download a small amount of data
    df = download_weather_data(
        latitude=40.7,
        longitude=-74.0,
        year=2023,
        variables=['temperature']
    )
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert 'Year' in df.columns
    assert 'Temperature' in df.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
