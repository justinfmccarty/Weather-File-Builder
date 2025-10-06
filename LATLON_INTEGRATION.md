# Latitude/Longitude Column Integration

## Overview

This document describes the implementation of automatic latitude and longitude storage in weather data files, which eliminates the need for manual location input when generating TMY visualizations from existing CSV files.

## Problem

Previously, when users downloaded weather data and saved it to CSV (options 1-3), the location information was not stored in the file. Later, when generating TMY visualizations from that CSV (options 6-7), users had to manually re-enter the latitude and longitude coordinates, which was redundant and error-prone.

## Solution

The location information is now automatically stored as columns in the downloaded weather data files. When generating TMY visualizations from these files, the tool can extract the location directly from the CSV, making manual input optional.

## Implementation Details

### 1. Converter Enhancement (`converters.py`)

The `era5_to_dataframe()` function was updated to accept optional latitude and longitude parameters:

```python
def era5_to_dataframe(ds, latitude: float = None, longitude: float = None) -> pd.DataFrame:
```

When provided, these values are added as columns to the output DataFrame:

```python
# Add location information if provided
if latitude is not None:
    output['Latitude'] = latitude
if longitude is not None:
    output['Longitude'] = longitude
```

**Positioning**: The Latitude and Longitude columns are inserted after the time components (Year, Month, Day, Hour, Minute) and before the weather variables (Temperature, Wind Speed, etc.).

### 2. Download Functions (`core.py`)

Both download helper functions were updated to pass location to the converter:

#### `_download_single_month()`
Used by standard monthly downloads (options 1-2):
```python
df = era5_to_dataframe(ds_point, latitude=latitude, longitude=longitude)
```

#### `_download_time_series()`
Used by fast timeseries downloads (option 3):
```python
df_renamed = era5_to_dataframe(df, latitude=latitude, longitude=longitude)
```

### 3. Interactive Mode Enhancement (`interactive.py`)

The `generate_tmy_from_csv_with_viz()` function was updated to:

1. **Check for location in CSV**:
   ```python
   if 'Latitude' in df.columns and 'Longitude' in df.columns:
       csv_lat = df['Latitude'].iloc[0]
       csv_lon = df['Longitude'].iloc[0]
   ```

2. **Offer as default with option to override**:
   ```python
   if pd.notna(csv_lat) and pd.notna(csv_lon):
       print(f"  Found location in CSV: {csv_lat:.4f}, {csv_lon:.4f}")
       use_csv_loc = get_choice("Use this location? (y/n): ", ['y', 'n', 'Y', 'N'])
   ```

3. **Fall back to manual input if needed**:
   ```python
   if lat is None:
       lat = get_float("Enter latitude (-90 to 90): ", min_val=-90, max_val=90)
   ```

### 4. Visualization Enhancement (`visualization.py`)

The `create_tmy_plot()` function parameters were updated to make latitude and longitude optional:

```python
def create_tmy_plot(
    multi_year_data: pd.DataFrame,
    tmy_data: pd.DataFrame,
    selected_years: Dict[int, int],
    latitude: float = None,  # Now optional
    longitude: float = None,  # Now optional
    ...
)
```

If not provided, the function attempts to extract from the DataFrame:

```python
# Extract latitude/longitude from dataframe if not provided
if latitude is None and 'Latitude' in multi_year_data.columns:
    latitude = multi_year_data['Latitude'].iloc[0]
    if pd.notna(latitude):
        print(f"Using latitude from data: {latitude:.4f}")
```

## Usage Examples

### Workflow with Automatic Location

1. **Download data** (option 2):
   ```
   Enter latitude: 40.7
   Enter longitude: -74.0
   ...
   ```
   → CSV saved with Latitude and Longitude columns

2. **Generate TMY with visualization from CSV** (option 7):
   ```
   Enter path to CSV: weather_data.csv
   Found location in CSV: 40.7000, -74.0000
   Use this location? (y/n): y
   ```
   → No manual re-entry needed!

### Backward Compatibility

The changes are fully backward compatible:

- **Old CSVs without location**: Users will be prompted to enter lat/lon as before
- **Programmatic use**: Existing code that provides lat/lon explicitly will continue to work
- **Optional parameters**: Functions can be called with or without location parameters

## Benefits

1. **Reduced redundancy**: No need to remember or look up coordinates again
2. **Fewer errors**: No risk of typos when re-entering coordinates
3. **Better workflow**: Seamless transition from download to analysis
4. **Data completeness**: Location metadata stored with the data itself

## File Structure

Modified files:
- `src/weather_file_builder/converters.py` - Added lat/lon parameters and column insertion
- `src/weather_file_builder/core.py` - Updated download functions to pass location
- `src/weather_file_builder/interactive.py` - Enhanced interactive mode to read from CSV
- `src/weather_file_builder/visualization.py` - Made lat/lon optional with auto-extraction

## Testing

A test script (`test_latlon_integration.py`) was created to verify:
1. Columns are added when lat/lon provided
2. Columns are omitted when lat/lon not provided (backward compatibility)
3. Values are correctly propagated to all rows

All tests passed successfully.
