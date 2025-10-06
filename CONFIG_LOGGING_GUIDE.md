# Configuration and Logging System

## Overview

The weather-file-builder now includes a comprehensive configuration and logging system that:
- **Tracks all project parameters** in a `config.json` file
- **Logs all operations** to a `project.log` file
- **Enables resuming failed workflows** without re-downloading data
- **Provides project status checks** to see what's been completed

## Project Directory Structure

When you create a project, the following structure is automatically created:

```
my_project/
├── config.json          # Configuration file (parameters, metadata)
├── project.log          # Log file (all operations, timestamps)
├── timeseries/          # Downloaded raw data
│   └── timeseries_*.csv
├── tmy/                 # Generated TMY files
│   └── tmy_*.csv
└── plots/               # Visualization plots
    ├── tmy_temperature_*.png
    ├── tmy_wind_speed_*.png
    └── ...
```

## Configuration File (config.json)

The `config.json` file contains all parameters used for the project:

```json
{
  "created": "2025-10-05T11:30:00",
  "workflow_type": "comprehensive_timeseries",
  "location": {
    "latitude": 40.7,
    "longitude": -74.0
  },
  "start_date": "2010-01-01",
  "end_date": "2020-12-31",
  "variables": ["temperature", "wind", "solar"],
  "tmy_type": "typical",
  "method": "zscore",
  "retry_attempts": 3
}
```

## Log File (project.log)

The `project.log` file tracks all operations with timestamps:

```
Project created: 2025-10-05T11:30:00
======================================================================
[2025-10-05 11:30:15] [INFO] Starting comprehensive workflow for (40.7, -74.0)
[2025-10-05 11:30:15] [INFO] Configuration saved to /path/to/config.json
[2025-10-05 11:30:16] [INFO] Step 1/5: Downloading timeseries data
[2025-10-05 11:32:45] [SUCCESS] Successfully downloaded 96360 records
[2025-10-05 11:32:46] [INFO] Step 2/5: Saving timeseries data
[2025-10-05 11:32:50] [SUCCESS] Timeseries saved: /path/to/timeseries.csv
[2025-10-05 11:32:50] [INFO] Step 3/5: Creating TMY
[2025-10-05 11:33:05] [SUCCESS] TMY created using zscore method, type: typical
[2025-10-05 11:33:05] [INFO] Step 4/5: Saving TMY data
[2025-10-05 11:33:06] [SUCCESS] TMY saved: /path/to/tmy.csv
[2025-10-05 11:33:06] [INFO] Step 5/5: Generating visualization plots
[2025-10-05 11:33:45] [SUCCESS] Workflow complete! Generated 7 plots
```

## Resume Capability

If a workflow fails or is interrupted, you can resume it by simply running the same command again. The system will:

1. **Detect the existing project** directory
2. **Read the configuration** file
3. **Check what's already completed**
4. **Skip completed steps** automatically
5. **Resume from where it left off**

### Example: Resuming a Failed Workflow

**Initial run (fails during plot generation):**
```bash
weather-file-builder workflow \
  --lat 40.7 --lon -74.0 \
  --start-date 2010-01-01 --end-date 2020-12-31 \
  --project-dir ./my_project
  
# Downloads data... ✓
# Creates TMY... ✓
# Starts plotting... ✗ (fails)
```

**Resume (skips completed steps):**
```bash
weather-file-builder workflow \
  --lat 40.7 --lon -74.0 \
  --start-date 2010-01-01 --end-date 2020-12-31 \
  --project-dir ./my_project

# Output:
# ⚠ EXISTING PROJECT FOUND
# Location: 40.7, -74.0
# Status:
#   Timeseries data: ✓
#   TMY data: ✓
#   Plots: ✗
# 
# The workflow will skip already completed steps.
# 
# [1/5] Downloading timeseries data...
#   ⚠ Timeseries data already exists, skipping download...
# [2/5] Saving timeseries data...
#   ✓ Already saved
# [3/5] Creating TMY...
#   (continues with TMY creation)
# [4/5] Saving TMY data...
#   (continues with saving)
# [5/5] Generating visualization plots...
#   (generates only missing plots)
```

## Interactive Mode with Existing Projects

When using interactive mode, the system will:

1. **Detect existing projects** when you enter a directory
2. **Display project information** from config.json
3. **Show recent log entries**
4. **Display completion status**
5. **Offer to use existing configuration**

### Example Interactive Session

```
Project Directory:
All outputs will be organized in subdirectories within this location.
Enter project directory path [./weather_data_project]: ./my_existing_project

======================================================================
⚠ EXISTING PROJECT FOUND
======================================================================
Location: 40.7, -74.0
Created: 2025-10-05T11:30:00
Workflow: comprehensive_timeseries

Recent log entries:
  [2025-10-05 11:30:15] [INFO] Starting comprehensive workflow
  [2025-10-05 11:32:45] [SUCCESS] Successfully downloaded 96360 records
  [2025-10-05 11:32:50] [SUCCESS] Timeseries saved
  [2025-10-05 11:33:05] [SUCCESS] TMY created using zscore method
  [2025-10-05 11:33:45] [SUCCESS] Workflow complete!

Status:
  Timeseries data: ✓
  TMY data: ✓
  Plots: ✓
======================================================================

Use this existing project? (y/n): y
Use existing configuration settings? (y/n): y

Using existing: 40.7, -74.0
...
```

## API Usage

You can also use the config and logging functions programmatically:

```python
from weather_file_builder.utils import (
    write_project_config,
    read_project_config,
    log_message,
    read_project_log,
    check_project_status
)

# Write configuration
config_path = write_project_config(
    project_dir='./my_project',
    latitude=40.7,
    longitude=-74.0,
    start_date='2010-01-01',
    end_date='2020-12-31',
    workflow_type='custom'
)

# Read configuration
config = read_project_config('./my_project')
print(config['location']['latitude'])  # 40.7

# Log messages
log_message('./my_project', 'Starting custom workflow')
log_message('./my_project', 'Download complete', level='SUCCESS')
log_message('./my_project', 'Warning message', level='WARNING')
log_message('./my_project', 'Error occurred', level='ERROR')

# Check project status
status = check_project_status('./my_project')
if status['has_tmy']:
    print("TMY already created!")
if not status['has_plots']:
    print("Need to generate plots")

# Read log
log_content = read_project_log('./my_project')
print(log_content)
```

## Benefits

### 1. **Traceability**
- Every operation is logged with timestamps
- You can always see what was done and when
- Configuration is saved for reproducibility

### 2. **Fault Tolerance**
- Workflows can be interrupted and resumed
- No need to re-download data if it already exists
- Smart detection of completed steps

### 3. **Debugging**
- Log file helps identify where failures occurred
- Configuration file shows exact parameters used
- Status checking shows what's missing

### 4. **Reproducibility**
- Configuration file can be shared with others
- Exact parameters are preserved
- Others can recreate your workflow

### 5. **User-Friendly**
- Automatic detection of existing projects
- Clear status messages
- Helpful warnings and errors

## Log Levels

The logging system supports four levels:

- **INFO**: General information messages
- **SUCCESS**: Successful operations
- **WARNING**: Warning messages (non-fatal)
- **ERROR**: Error messages (fatal)

## Configuration Parameters

The configuration file can store any parameters, but standard fields include:

- `created`: ISO timestamp of project creation
- `workflow_type`: Type of workflow ('comprehensive_timeseries', 'single_year', 'tmy')
- `location`: Object with `latitude` and `longitude`
- `start_date`: Start date (YYYY-MM-DD)
- `end_date`: End date (YYYY-MM-DD)
- `year`: Single year (for single_year workflows)
- `years`: Array of years (for multi_year workflows)
- `variables`: Array of variable names or "all"
- `tmy_type`: TMY type ('typical', 'extreme_warm', 'extreme_cold')
- `method`: Statistical method ('zscore', 'ks')
- Custom fields: Any additional parameters you want to track

## Best Practices

1. **Always use project directories** instead of standalone files
2. **Check the log file** if something goes wrong
3. **Keep the config.json** for reproducibility
4. **Use meaningful project directory names** (e.g., `nyc_2010-2020_tmy`)
5. **Don't manually edit config.json** unless you know what you're doing
6. **Review the log file** after successful workflows to understand what happened

## Troubleshooting

### Config file is corrupted
```bash
# Delete and recreate
rm my_project/config.json
# Run workflow again - it will recreate config
```

### Want to start fresh but keep the directory
```bash
# Delete specific files
rm my_project/config.json
rm my_project/project.log
rm -rf my_project/timeseries/*
# Workflow will start fresh
```

### Want to see full log
```bash
cat my_project/project.log
# Or in Python:
from weather_file_builder.utils import read_project_log
print(read_project_log('./my_project'))
```

## Future Enhancements

Potential future additions:
- Progress tracking (% complete)
- Performance metrics (download speeds, processing times)
- Data quality metrics
- Automatic retry with exponential backoff
- Email notifications on completion/failure
- Web dashboard for project management
