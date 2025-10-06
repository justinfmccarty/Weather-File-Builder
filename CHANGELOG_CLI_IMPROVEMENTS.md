# CLI and Interactive Mode Improvements

## Summary of Changes

This update significantly simplifies and improves the CLI and interactive mode with better file management.

## Key Changes

### 1. Simplified Interactive Menu
The interactive mode now has only **4 options**:
- **Option 1**: Download weather data (single year)
- **Option 2**: Complete TMY workflow (timeseries → TMY → visualizations)
- **Option 8**: Help & Documentation
- **Option 9**: Exit

### 2. New Comprehensive Workflow
The new **Option 2** provides a complete, streamlined workflow that:
1. Downloads timeseries data using the fast ERA5-Land API
2. Saves the raw timeseries CSV
3. Creates a Typical Meteorological Year (TMY)
4. Saves the TMY CSV
5. Generates visualization plots for ALL available variables
6. Organizes everything in a structured project directory

### 3. Improved File Management
All outputs are now automatically organized in a project directory structure:

```
project_dir/
├── timeseries/          # Downloaded raw data
│   └── timeseries_2010-01-01_2020-12-31_40.70_-74.00.csv
├── tmy/                 # Generated TMY files
│   └── tmy_2010-2020_40.70_-74.00.csv
└── plots/               # Visualization plots
    ├── tmy_temperature_2010-2020_40.70_-74.00.png
    ├── tmy_dewpoint_2010-2020_40.70_-74.00.png
    ├── tmy_pressure_2010-2020_40.70_-74.00.png
    ├── tmy_wind_speed_2010-2020_40.70_-74.00.png
    ├── tmy_wind_direction_2010-2020_40.70_-74.00.png
    ├── tmy_solar_radiation_2010-2020_40.70_-74.00.png
    └── tmy_thermal_radiation_2010-2020_40.70_-74.00.png
```

### 4. Automatic File Naming
Files are automatically named based on:
- Data type (timeseries, tmy)
- Date range or years
- Location (latitude, longitude)
- Variables (if subset selected)

**Examples**:
- `timeseries_2020-01-01_2020-12-31_40.70_-74.00.csv`
- `tmy_2010-2020_40.70_-74.00.csv`
- `tmy_temperature_2010-2020_40.70_-74.00.png`

### 5. New CLI Command: `workflow`

```bash
# Complete TMY workflow (RECOMMENDED)
weather-file-builder workflow \
  --lat 40.7 --lon -74.0 \
  --start-date 2010-01-01 --end-date 2020-12-31 \
  --project-dir ./my_project

# With custom settings
weather-file-builder workflow \
  --lat 40.7 --lon -74.0 \
  --start-date 2010-01-01 --end-date 2020-12-31 \
  --project-dir ./my_project \
  --tmy-type typical \
  --method zscore \
  --variables temperature,wind,solar
```

## Usage Examples

### Interactive Mode (Recommended for Beginners)

```bash
# Launch interactive mode
weather-file-builder

# Or explicitly
weather-file-builder --interactive
```

### Command Line - Complete Workflow

```bash
# Generate TMY with all visualizations
weather-file-builder workflow \
  --lat 41.88 --lon -87.63 \
  --start-date 2010-01-01 --end-date 2020-12-31 \
  --project-dir ./chicago_weather

# This will create:
# - chicago_weather/timeseries/timeseries_2010-01-01_2020-12-31_41.88_-87.63.csv
# - chicago_weather/tmy/tmy_2010-2020_41.88_-87.63.csv
# - chicago_weather/plots/tmy_temperature_2010-2020_41.88_-87.63.png
# - chicago_weather/plots/tmy_wind_speed_2010-2020_41.88_-87.63.png
# - ... (and more plots for each variable)
```

### Command Line - Single Year Download

```bash
# Download one year
weather-file-builder download \
  --lat 40.7 --lon -74.0 \
  --years 2020 \
  --output weather_2020.csv \
  --project-dir ./nyc_weather
```

## Benefits

1. **Simpler Interface**: Fewer options, clearer purpose
2. **One-Command Workflow**: Get everything you need with one command
3. **Organized Output**: No more scattered files, everything in its place
4. **Automatic Naming**: No need to think about file names
5. **Complete Visualization**: Automatically generates plots for all variables
6. **Faster**: Uses the fast timeseries API for multi-year downloads

## Migration from Old CLI

If you were using the old CLI commands:

### Old Way (Multiple Steps)
```bash
# Step 1: Download
weather-file-builder download --lat 40.7 --lon -74.0 --years 2010-2020 --output data.csv

# Step 2: Create TMY (separate process)
# ... manually create TMY from data.csv

# Step 3: Create plots (separate process)
# ... manually create plots
```

### New Way (Single Step)
```bash
weather-file-builder workflow \
  --lat 40.7 --lon -74.0 \
  --start-date 2010-01-01 --end-date 2020-12-31 \
  --project-dir ./my_project
```

## Backward Compatibility

All old CLI commands (`download`, `timeseries`, `tmy`) are still available and work as before. The new `workflow` command is an addition, not a replacement.

## Testing

Run the file management tests:
```bash
python test_file_management.py
```

## Implementation Details

### New Functions in `utils.py`
- `setup_project_directory()`: Creates organized directory structure
- `generate_filename()`: Auto-generates standardized filenames
- `get_output_path()`: Returns full path for files in project directory

### New Function in `core.py`
- `comprehensive_timeseries_workflow()`: Complete workflow orchestration

### Updated Files
- `interactive.py`: Simplified menu (only 4 options)
- `cli.py`: Added `workflow` command
- `__init__.py`: Exported new workflow function
