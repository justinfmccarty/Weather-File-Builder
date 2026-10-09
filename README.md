# Weather File Builder

Build weather files (EPW, TMY) from ERA5 global reanalysis data for building energy simulation.

## Features

- 🌍 **Global Coverage**: Download weather data for any location worldwide using ERA5 reanalysis
- 📊 **Multiple Formats**: Generate EPW (EnergyPlus Weather) and TMY (Typical Meteorological Year) files
- 🔄 **Robust Downloads**: Automatic retry logic with concurrent/async support and rate limit handling
- 🎨 **TMY Visualization**: Multi-panel plots showing month selection and final TMY construction
- 🐍 **Python API**: Clean, programmatic interface for integration into other projects
- 💻 **Dual Interface**: Interactive menu-driven mode or traditional command-line interface
- 📝 **Configuration & Logging**: Automatic project configuration files and comprehensive logging
- 🔁 **Resume Capability**: Interrupted workflows can be safely resumed without re-downloading data
- 📊 **Project Status**: Check completion status of timeseries, TMY, and visualization outputs

## Installation

```bash
pip install weather-file-builder
```

From source:
```bash
git clone https://github.com/justinfmccarty/weather_file_builder.git
cd weather_file_builder
pip install -e .
```

## CDS API Setup

Required before first use:

1. **Register** at https://cds.climate.copernicus.eu/
2. **Get your API key** from your profile page
3. **Create `~/.cdsapirc`**:
   ```
   url: https://cds.climate.copernicus.eu/api
   key: YOUR_UID:YOUR_API_KEY
   ```
4. **Accept the ERA5 license** terms on the CDS website

## Quick Start

### Interactive Mode (Recommended)

Launch the guided menu interface with no arguments:

```bash
weather-file-builder
```

Features: step-by-step guidance, input validation, visual menus, smart defaults, and pre-configured presets. See [Interactive Mode](#interactive-mode) section below for details.

### Command Line Interface

```bash
# Comprehensive workflow (downloads data, creates TMY, generates plots)
weather-file-builder workflow \
    --lat 40.7 --lon -74.0 \
    --start-date 2010-01-01 --end-date 2020-12-31 \
    --project-dir ./my_weather_project

# Download single year of data
weather-file-builder download --lat 40.7 --lon -74.0 --years 2020 --output weather_2020.csv

# Download time series (fastest method for continuous date ranges)
weather-file-builder timeseries --lat 40.7 --lon -74.0 \
    --start-date 2020-01-01 --end-date 2020-12-31 --output weather_2020.csv

# Download multiple years and create TMY
weather-file-builder tmy --lat 40.7 --lon -74.0 --years 2010-2020 --output tmy_nyc.csv

# Download with specific variables
weather-file-builder download --lat 51.5 --lon -0.1 --years 2023 \
    --variables temperature,pressure,wind --output london_2023.csv

# Adjust concurrency (faster downloads)
weather-file-builder download --lat 40.7 --lon -74.0 --years 2020 \
    --workers 6 --output weather.csv

# Use sequential mode if hitting rate limits
weather-file-builder download --lat 40.7 --lon -74.0 --years 2018-2020 \
    --sequential --delay 2.0 --output weather.csv

# Resume an interrupted workflow (automatically skips completed steps)
weather-file-builder workflow \
    --lat 40.7 --lon -74.0 \
    --start-date 2010-01-01 --end-date 2020-12-31 \
    --project-dir ./my_weather_project
```

### Configuration & Logging

All workflows automatically create:
- **`config.json`**: Stores all project parameters (location, dates, variables, etc.)
- **`project.log`**: Timestamped log of all operations with INFO, SUCCESS, WARNING, and ERROR levels

**Resume interrupted workflows**: Simply re-run the same command. The system detects existing data and skips completed steps automatically.

**Check project status**:
```python
from weather_file_builder.utils import check_project_status

status = check_project_status('./my_weather_project')
print(f"Timeseries: {'✓' if status['has_timeseries'] else '✗'}")
print(f"TMY: {'✓' if status['has_tmy'] else '✗'}")
print(f"Plots: {'✓' if status['has_plots'] else '✗'}")
```

### Python API

#### Comprehensive Workflow (Recommended)

```python
from weather_file_builder.core import comprehensive_timeseries_workflow

# Complete workflow: download data, create TMY, generate visualizations
result = comprehensive_timeseries_workflow(
    latitude=40.7128,
    longitude=-74.0060,
    start_date='2010-01-01',
    end_date='2020-12-31',
    project_dir='./nyc_weather',
    tmy_type='typical',
    create_plots=True
)

# Result includes paths to all generated files
print(f"Config: {result['config_path']}")
print(f"Log: {result['log_path']}")
print(f"Timeseries: {result['timeseries_path']}")
print(f"TMY: {result['tmy_path']}")
print(f"Plots: {result['plots']}")

# Resume capability: re-run the same code to resume if interrupted
# The workflow automatically detects and skips completed steps
```

#### Basic Download (Single Year, All Variables)

```python
from weather_file_builder import download_weather_data

# Download one year of all weather variables
df = download_weather_data(
    latitude=40.7128,
    longitude=-74.0060,
    year=2020
)

print(df.head())
```

#### Time Series Download (Fastest Method)

```python
from weather_file_builder import download_time_series

# Download continuous date range (fastest method)
df = download_time_series(
    latitude=40.7128,
    longitude=-74.0060,
    start_date='2020-01-01',
    end_date='2020-12-31'
)

# Single API call, much faster than monthly downloads
# Note: ERA5-Land timeseries has more limited variable set
print(f"Downloaded {len(df)} records in single request")
```

#### Multi-Year Download for TMY

```python
from weather_file_builder import download_multi_year

# Download multiple years
df = download_multi_year(
    latitude=40.7128,
    longitude=-74.0060,
    years=range(2010, 2021),  # 2010-2020
    variables=['temperature', 'pressure', 'wind', 'solar']
)

# Data includes all years for TMY analysis
print(f"Downloaded {len(df)} records")
```

#### Custom Variable Selection

```python
from weather_file_builder import download_weather_data
from weather_file_builder.variables import TEMPERATURE, PRESSURE, WIND

# Download specific variables only
df = download_weather_data(
    latitude=51.5074,
    longitude=-0.1278,
    year=2023,
    variables=[TEMPERATURE, PRESSURE, WIND]
)
```

#### Generate EPW File

```python
from weather_file_builder import download_weather_data, create_epw

# Download data
df = download_weather_data(40.7128, -74.0060, 2020)

# Create EPW file
create_epw(
    data=df,
    output_path="weather.epw",
    location_name="New York City, NY, USA",
    latitude=40.7128,
    longitude=-74.0060,
    timezone=-5,
    elevation=10
)
```

#### Generate TMY File

```python
from weather_file_builder import download_multi_year, create_tmy

# Download 10 years of data
df = download_multi_year(
    latitude=40.7128,
    longitude=-74.0060,
    years=range(2010, 2021)
)

# Create TMY (selects representative months from each year)
tmy_data = create_tmy(df)

# Save as EPW
create_epw(
    data=tmy_data,
    output_path="tmy.epw",
    location_name="New York City TMY",
    latitude=40.7128,
    longitude=-74.0060,
    timezone=-5,
    elevation=10
)
```

## Project Directory Structure

When using the comprehensive workflow or interactive mode with project directories, the following structure is created:

```
my_weather_project/
├── config.json              # Project configuration (location, dates, variables)
├── project.log              # Timestamped log of all operations
├── timeseries/              # Downloaded weather data
│   └── timeseries_YYYY-MM-DD_to_YYYY-MM-DD.csv
├── tmy/                     # Generated TMY files
│   └── tmy_YYYY-MM-DD_to_YYYY-MM-DD.csv
└── plots/                   # Visualization outputs
    └── tmy_visualization_*.png
```

**Benefits:**
- **Reproducibility**: `config.json` documents exactly what was done
- **Debugging**: `project.log` shows all operations with timestamps
- **Resume capability**: Re-run workflows without re-downloading existing data
- **Organization**: All project files in one place

## Data Output Format

All functions return pandas DataFrames with standardized columns.

**Note**: Timeseries data is saved in Apache Arrow Feather format (`.feather`) by default for faster I/O and better compression. TMY files remain in CSV format for broader compatibility.

| Column | Unit | Description |
|--------|------|-------------|
| Year | - | Year |
| Month | 1-12 | Month |
| Day | 1-31 | Day of month |
| Hour | 0-23 | Hour of day |
| Minute | 0-59 | Minute (usually 0 for hourly data) |
| Temperature | °C | Air temperature at 2m |
| Dew Point | °C | Dew point temperature |
| Pressure | hPa | Surface pressure |
| Relative Humidity | % | Relative humidity |
| Wind Speed | m/s | Wind speed at 10m |
| Wind Direction | degrees | Wind direction (0-360°) |
| GHI | W/m² | Global horizontal irradiance |
| DNI | W/m² | Direct normal irradiance |
| DHI | W/m² | Diffuse horizontal irradiance |
| Cloud Cover | 0-1 | Total cloud cover fraction |
| Precipitation | mm | Total precipitation |

## Available Variables

The package supports the following variable groups:

- **TEMPERATURE**: 2m temperature, dew point
- **PRESSURE**: Surface pressure, relative humidity  
- **WIND**: U/V wind components at 10m, calculated speed/direction
- **SOLAR**: Surface solar radiation, cloud cover
- **PRECIPITATION**: Total precipitation
- **ALL**: All available variables (default)

## Advanced Usage

### Async Downloads with Rate Limiting

```python
from weather_file_builder import download_multi_year_async

# Download faster with concurrent requests
df = download_multi_year_async(
    latitude=40.7128,
    longitude=-74.0060,
    years=range(2015, 2021),
    max_workers=4,  # Number of concurrent downloads
    retry_attempts=3
)
```

### Sequential Downloads (More Reliable)

```python
from weather_file_builder import download_multi_year

# Slower but more reliable for rate-limited API
df = download_multi_year(
    latitude=40.7128,
    longitude=-74.0060,
    years=range(2010, 2021),
    delay_between_requests=5  # Wait 5 seconds between requests
)
```

## Troubleshooting

### Rate Limiting Errors

If you encounter "400 queued requests" errors:
- Reduce `max_workers` in async mode (try 3-4 instead of 6+)
- Use sequential mode with `delay_between_requests=5`
- Download during off-peak hours (late night UTC)

### Large Request Errors

If you get "403 cost limits exceeded":
- Request smaller time ranges (single years instead of decades)
- Reduce the number of variables
- Check your CDS API quota at https://cds.climate.copernicus.eu/

### Missing netCDF Support

If you get "Unknown file format" errors:
```bash
pip install netcdf4 h5py
# or with conda:
conda install netcdf4 h5py
```

## Development

```bash
# Clone repository
git clone https://github.com/justinfmccarty/weather_file_builder.git
cd weather_file_builder

# Run tests and lint (uv creates the environment from uv.lock)
uv run --extra dev pytest
uv run --extra dev ruff check src tests

# Release (maintainer, on main with a clean tree)
./release.sh patch|minor|major
```

## API Reference

See the [full API documentation](docs/api.md) for detailed information on all functions and classes.

## Roadmap

- [x] ERA5 data download with rate limiting and async/concurrent support
- [x] Interactive and command-line interfaces
- [x] Standardized weather data format
- [x] TMY construction (ISO 15927-4 typical year; z-score/KS extreme years)
- [x] TMY visualization (multi-panel plots)
- [x] Configuration and logging system
- [x] Resume capability for interrupted workflows
- [x] Project status checking
- [x] EPW file generation
- [ ] Data quality validation
- [ ] Solar radiation models (DISC, Perez)
- [ ] Psychrometric calculations
- [ ] Progress bars for long downloads

---

## Interactive Mode

Launch without arguments for a guided, menu-driven interface:

```bash
weather-file-builder
# or explicitly: weather-file-builder --interactive
```

### Main Menu Options

1. **Comprehensive workflow** - Complete end-to-end workflow with project directory, configuration, and logging
2. **Download weather data (single year)** - Quick single-year downloads
3. **Download weather data (multiple years)** - Multi-year data collection
4. **Download time series (fast, continuous date range)** - Fastest method using ERA5-Land timeseries API
5. **Generate TMY** - Create Typical Meteorological Year files (downloads data first)
6. **Generate TMY with visualization** - TMY + multi-panel plot showing month selection (downloads data first)
7. **Generate TMY from existing CSV** - Create TMY from previously downloaded multi-year CSV files (no download required)
8. **Generate TMY with visualization from existing CSV** - TMY + visualization from existing CSV (no download required)
9. **Help & Documentation** - Built-in comprehensive help
10. **Exit**

### Key Features

- **Input validation**: Latitude/longitude bounds, year ranges (1940-2024), type checking
- **Smart defaults**: Auto-generated filenames and project directories based on location/dates
- **Project detection**: Automatically detects existing projects and offers to resume
- **Configuration reuse**: Use saved configuration from previous runs
- **Pre-configured presets**:
  - Variable groups: All, Temperature only, Temp+Wind, Temp+Solar, Temp+Wind+Solar, Custom
  - Concurrency modes: Balanced (4 workers), Aggressive (6), Conservative (2), Sequential
  - TMY types: Typical, Extreme warm, Extreme cold
  - Statistical methods: ISO 15927-4 (typical), Z-score or Kolmogorov-Smirnov (extremes)
- **Error recovery**: Clear messages, returns to menu on failure
- **Progress feedback**: Step indicators, summaries before execution, confirmation prompts

### Example Workflow

```bash
$ weather-file-builder
# 1. Select option 1 (Comprehensive workflow)
# 2. Enter location: 40.7, -74.0
# 3. Enter date range: 2010-01-01 to 2020-12-31
# 4. Choose TMY type: Typical
# 5. Accept default project directory or customize
# 6. Confirm and wait
# 7. Get complete project with config, logs, data, TMY, and plots!

# If interrupted, run again - it will detect the existing project
# and offer to resume from where it left off
```

### Tips

- **New users**: Start with option 1 (Comprehensive workflow) for best experience
- **Use project directories**: Automatic configuration, logging, and resume capability
- **TMY generation**: Use 10+ years for best results
- **Save time**: Use options 7 & 8 to generate TMY from previously downloaded CSV files (no re-download needed)
- **Resume interrupted downloads**: Simply re-run the same command - completed steps are automatically skipped
- **Rate limits**: Try Conservative (2 workers) or Sequential mode with 2s delay
- **Large downloads**: Multi-year takes 2-5 min/year; can cancel with Ctrl+C and resume later

### Workflow Example: Resuming and Reusing Data

```bash
$ weather-file-builder
# Scenario 1: Interrupted workflow
#   → Run comprehensive workflow (option 1)
#   → Download interrupted by network issue
#   → Re-run same command
#   → System detects existing data and resumes automatically

# Scenario 2: Reusing downloaded data
#   → First run: Download multi-year data (option 3)
#   → Save as "weather_2010-2020.csv"
#   → Later: Generate TMY variants without re-downloading
#   → Options 7 & 8: Create TMY from saved CSV
#   → Much faster - no API calls needed!

# Scenario 3: Existing project detection
#   → Enter existing project directory
#   → System shows project status and recent log entries
#   → Offers to use existing configuration
#   → Automatically skips completed steps
```

---

## Project Structure

```
weather_file_builder/
├── src/weather_file_builder/
│   ├── core.py          # ERA5 downloads (async/concurrent support)
│   ├── variables.py     # Variable definitions & groups
│   ├── converters.py    # ERA5 to DataFrame conversion & unit conversions
│   ├── tmy.py           # TMY generation (Sandia method)
│   ├── visualization.py # TMY multi-panel plots
│   ├── interactive.py   # Interactive menu-driven CLI
│   ├── cli.py           # Traditional command-line interface
│   └── epw.py           # EPW file generation (TODO)
├── tests/               # Test suite
├── examples/            # Usage examples
└── pyproject.toml       # Package configuration
```

### Core Components

**Download & Data** (`core.py`, `converters.py`)
- Async/concurrent downloads with ThreadPoolExecutor (2-8 configurable workers)
- Sequential fallback with rate limiting and retry logic (exponential backoff: 30s, 60s, 120s)
- Comprehensive workflow with automatic configuration and logging
- Resume capability for interrupted downloads (checks for existing data)
- Unit conversions: K→°C, Pa→hPa, J/m²→Wh/m²
- Derived variables: wind speed/direction from U/V components, relative humidity from temp/dewpoint
- Solar radiation estimates from cloud cover

**Configuration & Logging** (`utils.py`)
- Automatic creation of config.json for all workflows
- Timestamped logging to project.log (INFO, SUCCESS, WARNING, ERROR levels)
- Project status checking (timeseries, TMY, plots, config, log)
- Configuration read/write with JSON format
- Resume detection for fault-tolerant workflows

**TMY Construction** (`tmy.py`)
- Typical year per ISO 15927-4 (`iso15927.py`): Finkelstein-Schafer on daily means, wind tiebreak, blended joins
- Extreme years: Z-score or Kolmogorov-Smirnov on one variable
- Supports typical, extreme_warm, and extreme_cold modes

**Station data** (`amy.py`, `amy_meteoswiss.py`, `station_tmy.py`)
- Station tables (hourly or 10-minute) to an ISO 15927-4 typical year or an actual year
- Returns (DataFrame, dict of selected years)

**Visualization** (`visualization.py`)
- Multi-panel plots: one panel per year + final TMY panel
- Highlights selected months with color
- Arrows connecting selected months to final TMY
- Daily mean curves with monthly grid lines
- Customizable figure size and DPI

**Interactive CLI** (`interactive.py`)
- Menu-driven workflows with input validation
- Pre-configured presets for common use cases
- Smart filename and project directory generation with location/date info
- Existing project detection with status display
- Configuration reuse from previous runs
- Built-in help system

**Command-line Interface** (`cli.py`)
- Traditional CLI for scripting and automation
- Project status checking and resume capability
- Compatible with all core functionality
- Displays configuration and log paths in results

---

## TMY Method Documentation

### Typical year: ISO 15927-4 (default)

`create_tmy(data)` and the station builder choose one real month for each
calendar month (`weather_file_builder/iso15927.py`):

1. Daily means of dry-bulb temperature, global horizontal irradiance and
   relative humidity for every candidate month.
2. For each variable, the Finkelstein-Schafer statistic between the
   candidate's daily means and all candidates' daily means for that calendar
   month: `FS = sum_i |F(i) - Phi(i)|`, with `F(i) = J(i)/(n+1)` and
   `Phi(i) = K(i)/(N+1)` (ranks within the month and within the pooled set).
3. Rank per variable, sum the ranks; of the three lowest sums, take the month
   whose mean wind speed is closest to the multi-year monthly mean.
4. Stitch the months. The 8 h either side of each join (and of December to
   January) are blended between the two source years' own records, which
   removes the jump at midnight without flattening the night. Temperature,
   humidity, pressure and longwave are smoothed; wind and irradiance are not.

A candidate month with a gap longer than `max_gap_hours` (default 6) in any
selection variable is skipped. The standard asks for at least 10 years.

### Extreme years

`file_type="extreme_warm"` / `"extreme_cold"` pick, for each calendar month,
the month whose temperature distribution lies furthest above / below the
long-term one: `test_method="zscore"` (signed difference of means over the
pooled spread, default) or `"ks"` (one-sided Kolmogorov-Smirnov statistic).
These are not a standard method; stitching each month's extreme gives a year
more extreme than any real one.

### Output

`create_tmy()` returns `(tmy_dataframe, {month: source_year})`. Pass the
selection window and the dictionary to `create_epw(..., period_of_record=(start,
end), selected_years=selected)` so COMMENTS 1 reads
`Period of Record=YYYY-YYYY; Jan=YYYY; ...`, which pyepwmorph uses to check the
baseline period.

## Station data: typical and actual years

Measured station tables (hourly or 10-minute) can be turned into an ISO
15927-4 typical year or a single actual year (AMY), for example for model
calibration. Column names, units and the timestamp convention are in
`weather_file_builder/amy.py`; `amy_meteoswiss.py` reads MeteoSwiss open data.

```python
import pandas as pd
from weather_file_builder import amy, amy_meteoswiss, station_tmy

table = pd.concat(amy_meteoswiss.read_meteoswiss_ogd(f) for f in files)  # UTC, hour ending
location = dict(site="Zurich-Fluntern", country_code="CHE", latitude=47.381, longitude=8.567,
                elevation=604.0, utc_offset=1.0)

station_tmy.station_table_to_tmy_epw(table, location, (1991, 2020), "fluntern_tmy.epw",
                                     attribution=amy_meteoswiss.ATTRIBUTION)
amy.station_table_to_epw(table, location, 2025, "fluntern_2025.epw")
```

What is derived rather than measured, and how, is written into COMMENTS 2:
- **Direct/diffuse:** from global irradiance, using a lookup table fitted on
  Swiss Plateau stations with sunshine duration. Outside that climate, use
  `decomposition="dirint"`.
- **Sky cover:** from the clear-sky index in daylight, interpolated at night.
- **Pressure:** where not measured, the station's monthly mean, otherwise
  the standard atmosphere.

See `examples/station_tmy_meteoswiss.py`.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

To contribute:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Citation

If you use this package in your research, please cite:

```bibtex
@software{weather_file_builder,
  author = {McCarty, Justin},
  title = {Weather File Builder: ERA5 to EPW/TMY Converter},
  year = {2025},
  url = {https://github.com/justinfmccarty/weather_file_builder}
}
```

## References

- **ERA5 Documentation**: https://confluence.ecmwf.int/display/CKB/ERA5
- **CDS API**: https://cds.climate.copernicus.eu/
- **EPW Format**: https://designbuilder.co.uk/cahelp/Content/EnergyPlusWeatherFileFormat.htm
- **TMY Methods**: ISO 15927-4:2005, Hygrothermal performance of buildings, Part 4: Hourly data for assessing the annual energy use for heating and cooling
- **EnergyPlus**: https://energyplus.net/

## Acknowledgments

- ERA5 data provided by the Copernicus Climate Change Service (C3S)
- Built with support from the building energy modeling community

---

**Author**: Justin McCarty  
**Version**: 0.1.0  
**Status**: Core functionality complete, EPW generation pending

