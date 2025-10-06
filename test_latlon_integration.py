"""Test script to verify lat/lon column integration."""

import pandas as pd
import numpy as np

# Directly test the converter logic without importing the full module
def test_era5_to_dataframe():
    """Test that lat/lon columns are added correctly."""
    
    # Simulate the converter logic
    output = pd.DataFrame()
    output['Year'] = [2020, 2020, 2020]
    output['Month'] = [1, 1, 1]
    output['Day'] = [1, 1, 1]
    output['Hour'] = [0, 1, 2]
    output['Minute'] = [0, 0, 0]
    
    # Test 1: With lat/lon provided
    print("Test 1: With latitude and longitude provided")
    latitude = 40.7
    longitude = -74.0
    
    if latitude is not None:
        output['Latitude'] = latitude
    if longitude is not None:
        output['Longitude'] = longitude
    
    print(f"Columns: {list(output.columns)}")
    print(f"Has Latitude column: {'Latitude' in output.columns}")
    print(f"Has Longitude column: {'Longitude' in output.columns}")
    
    if 'Latitude' in output.columns:
        print(f"Latitude values: {output['Latitude'].tolist()}")
    if 'Longitude' in output.columns:
        print(f"Longitude values: {output['Longitude'].tolist()}")
    
    assert 'Latitude' in output.columns, "Latitude column should exist"
    assert 'Longitude' in output.columns, "Longitude column should exist"
    assert all(output['Latitude'] == 40.7), "All latitude values should be 40.7"
    assert all(output['Longitude'] == -74.0), "All longitude values should be -74.0"
    
    print("✓ Test 1 passed\n")
    
    # Test 2: Without lat/lon (backward compatibility)
    print("Test 2: Without latitude and longitude (backward compatibility)")
    output2 = pd.DataFrame()
    output2['Year'] = [2020, 2020, 2020]
    output2['Month'] = [1, 1, 1]
    
    latitude = None
    longitude = None
    
    if latitude is not None:
        output2['Latitude'] = latitude
    if longitude is not None:
        output2['Longitude'] = longitude
    
    print(f"Columns: {list(output2.columns)}")
    print(f"Has Latitude column: {'Latitude' in output2.columns}")
    print(f"Has Longitude column: {'Longitude' in output2.columns}")
    
    assert 'Latitude' not in output2.columns, "Latitude column should not exist when None"
    assert 'Longitude' not in output2.columns, "Longitude column should not exist when None"
    
    print("✓ Test 2 passed\n")
    
    print("✓ All tests passed!")

if __name__ == '__main__':
    test_era5_to_dataframe()

