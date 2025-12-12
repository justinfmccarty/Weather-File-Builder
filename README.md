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
git clone https://github.com/jmccarty/weather_file_builder.git
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
git clone https://github.com/jmccarty/weather_file_builder.git
cd weather_file_builder

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/

# Lint code
ruff src/ tests/
```

## API Reference

See the [full API documentation](docs/api.md) for detailed information on all functions and classes.

## Roadmap

- [x] ERA5 data download with rate limiting and async/concurrent support
- [x] Interactive and command-line interfaces
- [x] Standardized weather data format
- [x] TMY construction (Sandia method with z-score/KS tests)
- [x] TMY visualization (multi-panel plots)
- [x] Configuration and logging system
- [x] Resume capability for interrupted workflows
- [x] Project status checking
- [ ] EPW file generation
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
  - Statistical methods: Z-score (recommended), Kolmogorov-Smirnov
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
- Sandia method with Finkelstein-Schafer statistics
- Statistical tests: Z-score (compares means/std) or Kolmogorov-Smirnov (compares distributions)
- Quantile-based month selection from multi-year data
- Supports typical, extreme_warm, and extreme_cold modes
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

### Algorithm Overview

The package implements the Sandia National Laboratories TMY method for constructing Typical Meteorological Years:

1. **Calculate long-term statistics**: For each calendar month across all years, compute quantiles (5%, 25%, 50%, 75%, 95%) and cumulative distribution functions for key weather variables
2. **Score candidate months**: For each month in each year, calculate Finkelstein-Schafer (FS) statistics comparing the candidate month to long-term statistics
3. **Select representative months**: Choose the month with the lowest weighted FS statistic (best match to long-term patterns)
4. **Construct TMY**: Concatenate selected months to form a single representative year

### Statistical Methods

**Z-score test** (default, recommended):
```
FS = (1/n) * Σ|((x_i - μ) / σ)|
```
Compares sample mean and standard deviation to long-term values. Good for typical TMY generation.

**Kolmogorov-Smirnov test**:
```
FS = max|F_candidate(x) - F_longterm(x)|
```
Compares full cumulative distributions. More sophisticated but typically produces similar results to z-score.

### TMY Types

- **Typical**: Selects months most representative of long-term average conditions
- **Extreme warm**: Biases selection toward warmer months for worst-case cooling analysis
- **Extreme cold**: Biases selection toward colder months for worst-case heating analysis

### Variables Considered

Primary variables for month selection (in order of importance):
1. Temperature (2m air temperature)
2. Dew point temperature
3. Wind speed
4. Global horizontal irradiance (GHI)

Additional variables included in output but not used for selection:
- Pressure, relative humidity, cloud cover, precipitation, DNI, DHI

### Usage Notes

- **Minimum data**: 3 years required; 10+ years recommended for robust statistics
- **Missing data**: Gaps should be <10% per month; larger gaps may affect selection quality
- **Output tuple**: `create_tmy()` returns `(tmy_dataframe, selected_years_dict)` where dict maps month number (1-12) to source year

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
  url = {https://github.com/jmccarty/weather_file_builder}
}
```

## References

- **ERA5 Documentation**: https://confluence.ecmwf.int/display/CKB/ERA5
- **CDS API**: https://cds.climate.copernicus.eu/
- **EPW Format**: https://designbuilder.co.uk/cahelp/Content/EnergyPlusWeatherFileFormat.htm
- **TMY Methods**: NREL Technical Report on TMY3
- **EnergyPlus**: https://energyplus.net/

## Acknowledgments

- ERA5 data provided by the Copernicus Climate Change Service (C3S)
- Built with support from the building energy modeling community

---

**Author**: Justin McCarty  
**Version**: 0.1.0  
**Status**: Core functionality complete, EPW generation pending

