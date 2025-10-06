"""
Interactive CLI for weather-file-builder.

Provides a simplified menu-driven interface.
"""

import sys
import os
import pandas as pd
from typing import Optional, List
from . import download_weather_data, comprehensive_timeseries_workflow
from .utils import (
    setup_project_directory, 
    get_output_path,
    read_project_config,
    check_project_status,
    read_project_log
)


def print_header():
    """Print application header."""
    print("\n" + "="*70)
    print("  Weather File Builder - Interactive Mode")
    print("  ERA5 Data Download & TMY Generation")
    print("="*70 + "\n")


def print_menu():
    """Print main menu."""
    print("\nMain Menu:")
    print("  1. Download weather data (single year)")
    print("  2. Complete TMY workflow (timeseries → TMY → visualizations)")
    print("  8. Help & Documentation")
    print("  9. Exit")
    print()


def get_choice(prompt: str, valid_choices: List[str]) -> str:
    """Get user choice with validation."""
    while True:
        choice = input(prompt).strip()
        if choice in valid_choices:
            return choice
        print(f"Invalid choice. Please select from: {', '.join(valid_choices)}")


def get_float(prompt: str, min_val: Optional[float] = None, max_val: Optional[float] = None) -> float:
    """Get float input with validation."""
    while True:
        try:
            value = float(input(prompt).strip())
            if min_val is not None and value < min_val:
                print(f"Value must be >= {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"Value must be <= {max_val}")
                continue
            return value
        except ValueError:
            print("Please enter a valid number")


def get_int(prompt: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """Get integer input with validation."""
    while True:
        try:
            value = int(input(prompt).strip())
            if min_val is not None and value < min_val:
                print(f"Value must be >= {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"Value must be <= {max_val}")
                continue
            return value
        except ValueError:
            print("Please enter a valid integer")


def get_project_directory() -> str:
    """Get project directory from user."""
    print("\nProject Directory:")
    print("All outputs will be organized in subdirectories within this location.")
    
    default_dir = "./weather_data_project"
    dir_path = input(f"Enter project directory path [{default_dir}]: ").strip()
    
    if not dir_path:
        dir_path = default_dir
    
    # Check if project already exists
    if os.path.exists(dir_path):
        status = check_project_status(dir_path)
        
        if status['has_config']:
            config = status['config']
            print("\n" + "="*70)
            print("⚠ EXISTING PROJECT FOUND")
            print("="*70)
            print(f"Location: {config['location']['latitude']}, {config['location']['longitude']}")
            print(f"Date Range: {config['start_date']} to {config['end_date']}")
            print(f"Created: {config.get('created', 'Unknown')}")
            print(f"Workflow: {config.get('workflow_type', 'Unknown')}")
            
            if status['has_log']:
                print("\nRecent log entries:")
                log_content = read_project_log(dir_path)
                if log_content:
                    lines = log_content.strip().split('\n')
                    for line in lines[-5:]:  # Show last 5 lines
                        print(f"  {line}")
            
            print("\nStatus:")
            print(f"  Timeseries data: {'✓' if status['has_timeseries'] else '✗'}")
            print(f"  TMY data: {'✓' if status['has_tmy'] else '✗'}")
            print(f"  Plots: {'✓' if status['has_plots'] else '✗'}")
            print("="*70)
            
            choice = get_choice("\nUse this existing project? (y/n): ", ['y', 'n', 'Y', 'N'])
            if choice.lower() != 'y':
                print("Please choose a different directory.")
                return get_project_directory()
            
            # Offer to use existing config
            use_config = get_choice("Use existing configuration settings? (y/n): ", ['y', 'n', 'Y', 'N'])
            if use_config.lower() == 'y':
                return dir_path, config
    
    return dir_path, None


def get_variables() -> Optional[List[str]]:
    """Get variables to download."""
    print("\nVariable Selection:")
    print("  1. All variables (default)")
    print("  2. Temperature only")
    print("  3. Temperature + Wind")
    print("  4. Temperature + Solar")
    print("  5. Temperature + Wind + Solar")
    print("  6. Custom selection")
    
    choice = get_choice("Select option (1-6): ", ['1', '2', '3', '4', '5', '6'])
    
    if choice == '1':
        return None
    elif choice == '2':
        return ['temperature']
    elif choice == '3':
        return ['temperature', 'wind']
    elif choice == '4':
        return ['temperature', 'solar']
    elif choice == '5':
        return ['temperature', 'wind', 'solar']
    else:
        print("\nAvailable variables: temperature, pressure, wind, solar, precipitation")
        vars_str = input("Enter variables (comma-separated): ").strip()
        return [v.strip() for v in vars_str.split(',')]


def interactive_download_single_year():
    """Interactive single year download."""
    print("\n" + "="*70)
    print("Download Single Year")
    print("="*70)
    
    # Get project directory
    project_dir, existing_config = get_project_directory()
    
    # Get location (use existing config if available)
    print("\nLocation:")
    if existing_config:
        lat = existing_config['location']['latitude']
        lon = existing_config['location']['longitude']
        print(f"Using existing: {lat}, {lon}")
    else:
        lat = get_float("Enter latitude (-90 to 90): ", min_val=-90, max_val=90)
        lon = get_float("Enter longitude (-180 to 180): ", min_val=-180, max_val=180)
    
    # Get year
    print("\nYear:")
    year = get_int("Enter year (1940-2025): ", min_val=1940, max_val=2025)
    
    # Get variables
    variables = get_variables()
    
    # Get concurrency settings
    print("\nConcurrency Settings:")
    print("  1. Balanced (4 workers) - Recommended")
    print("  2. Conservative (2 workers)")
    print("  3. Aggressive (6 workers)")
    
    workers_choice = get_choice("Select mode (1-3): ", ['1', '2', '3'])
    workers = {'1': 4, '2': 2, '3': 6}[workers_choice]
    
    # Confirm
    print("\n" + "-"*70)
    print("Summary:")
    print(f"  Project directory: {project_dir}")
    print(f"  Location: {lat}, {lon}")
    print(f"  Year: {year}")
    print(f"  Variables: {variables or 'all'}")
    print(f"  Workers: {workers}")
    print("-"*70)
    
    confirm = get_choice("\nProceed with download? (y/n): ", ['y', 'n', 'Y', 'N'])
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    
    # Download
    print("\nDownloading...")
    try:
        # Setup project directory
        project_dir = setup_project_directory(project_dir)
        
        # Download data
        df = download_weather_data(
            latitude=lat,
            longitude=lon,
            year=year,
            variables=variables,
            max_workers=workers
        )
        
        # Save to project directory
        output_path = get_output_path(
            project_dir=project_dir,
            data_type='single_year',
            latitude=lat,
            longitude=lon,
            year=year,
            variables=variables
        )
        
        df.to_csv(output_path, index=False)
        
        print(f"\n✓ Download complete!")
        print(f"  Saved to: {output_path}")
        print(f"  Records: {len(df)}")
        print(f"  Columns: {len(df.columns)}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def interactive_comprehensive_tmy():
    """Interactive comprehensive TMY workflow."""
    print("\n" + "="*70)
    print("Complete TMY Workflow")
    print("="*70)
    print("\nThis will download timeseries data, create a TMY, and generate")
    print("visualization plots for all available variables.")
    
    # Get project directory
    project_dir, existing_config = get_project_directory()
    
    # Get location (use existing config if available)
    print("\nLocation:")
    if existing_config:
        lat = existing_config['location']['latitude']
        lon = existing_config['location']['longitude']
        print(f"Using existing: {lat}, {lon}")
    else:
        lat = get_float("Enter latitude (-90 to 90): ", min_val=-90, max_val=90)
        lon = get_float("Enter longitude (-180 to 180): ", min_val=-180, max_val=180)
    
    # Get date range (use existing config if available)
    print("\nDate Range:")
    if existing_config:
        start_date = existing_config['start_date']
        end_date = existing_config['end_date']
        print(f"Using existing: {start_date} to {end_date}")
    else:
        print("Note: TMY typically requires 10+ years for best results")
        start_date = input("Enter start date (YYYY-MM-DD, e.g., 2010-01-01): ").strip()
        end_date = input("Enter end date (YYYY-MM-DD, e.g., 2020-12-31): ").strip()
    
    # Validate dates
    try:
        from datetime import datetime
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        num_years = (end_dt.year - start_dt.year + 1)
        
        if num_years < 3:
            print(f"\nWarning: Only {num_years} year(s) specified.")
            print("TMY typically requires 10+ years for best results.")
            confirm = get_choice("Continue anyway? (y/n): ", ['y', 'n', 'Y', 'N'])
            if confirm.lower() != 'y':
                print("Cancelled.")
                return
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        return
    
    # Get variables (use existing config if available)
    if existing_config:
        variables = existing_config['variables']
        print(f"Using existing variables: {variables}")
    else:
        variables = get_variables()
    
    # TMY settings (use existing config if available)
    print("\nTMY Type:")
    if existing_config:
        tmy_type = existing_config['tmy_type']
        print(f"Using existing: {tmy_type}")
    else:
        print("  1. Typical (most representative)")
        print("  2. Extreme warm")
        print("  3. Extreme cold")
        tmy_choice = get_choice("Select type (1-3): ", ['1', '2', '3'])
        tmy_type = {'1': 'typical', '2': 'extreme_warm', '3': 'extreme_cold'}[tmy_choice]
    
    # Method settings (use existing config if available)
    print("\nStatistical Method:")
    if existing_config:
        method = existing_config['method']
        print(f"Using existing: {method}")
    else:
        print("  1. Z-score (recommended)")
        print("  2. Kolmogorov-Smirnov")
        method_choice = get_choice("Select method (1-2): ", ['1', '2'])
        method = {'1': 'zscore', '2': 'ks'}[method_choice]
    
    # Confirm
    print("\n" + "-"*70)
    print("Summary:")
    print(f"  Project directory: {project_dir}")
    print(f"  Location: {lat}, {lon}")
    print(f"  Date range: {start_date} to {end_date} ({num_years} years)")
    print(f"  Variables: {variables or 'all'}")
    print(f"  TMY Type: {tmy_type}")
    print(f"  Method: {method}")
    print(f"  Estimated time: 3-10 minutes")
    print("-"*70)
    print("\nThis will create:")
    print("  • Timeseries Feather (raw downloaded data)")
    print("  • TMY CSV (typical year)")
    print("  • Visualization plots for each variable")
    print("-"*70)
    
    confirm = get_choice("\nProceed? (y/n): ", ['y', 'n', 'Y', 'N'])
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    
    # Execute comprehensive workflow
    print("\nExecuting workflow...")
    try:
        results = comprehensive_timeseries_workflow(
            latitude=lat,
            longitude=lon,
            start_date=start_date,
            end_date=end_date,
            project_dir=project_dir,
            variables=variables,
            tmy_type=tmy_type,
            method=method
        )
        
        print("\n" + "="*70)
        print("✓ Workflow Complete!")
        print("="*70)
        print(f"\nTimeseries data: {results['timeseries_feather']} (feather format)")
        print(f"TMY data: {results['tmy_csv']} (CSV format)")
        print(f"\nGenerated {len(results['plots'])} visualization plots:")
        for var, path in results['plots'].items():
            print(f"  • {var}: {path}")
        print(f"\nSelected years by month:")
        for month, year in sorted(results['selected_years'].items()):
            month_name = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month-1]
            print(f"  {month_name}: {year}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def show_help():
    """Show help information."""
    print("\n" + "="*70)
    print("Help & Documentation")
    print("="*70)
    
    print("""
Weather File Builder helps you download ERA5 climate data and generate
Typical Meteorological Year (TMY) files for building energy simulation.

KEY CONCEPTS:

1. ERA5 Data
   - Global reanalysis data from European Centre for Medium-Range Weather
   - Hourly data from 1940 to present
   - Covers temperature, wind, solar radiation, precipitation, etc.

2. Single Year Download (Option 1)
   - Downloads one year of hourly weather data
   - Full variable set available
   - Saved to project_dir/timeseries/
   - Use for: Historical analysis, specific year studies

3. Complete TMY Workflow (Option 2) - RECOMMENDED
   - Downloads multi-year timeseries data (fast method)
   - Creates Typical Meteorological Year
   - Generates visualization plots for all variables
   - All files automatically organized in project directory
   - Use for: Building energy simulation, climate analysis

4. TMY (Typical Meteorological Year)
   - Single year constructed from multiple years of data
   - Each month selected from the year that best represents long-term average
   - Used in building energy simulation (EnergyPlus, etc.)
   - Requires 10+ years of data for best results

5. Project Directory Structure
   All outputs are organized automatically:
   
   project_dir/
   ├── timeseries/          # Downloaded raw data
   │   └── timeseries_2010-01-01_2020-12-31_40.70_-74.00.csv
   ├── tmy/                 # Generated TMY files
   │   └── tmy_2010-2020_40.70_-74.00.csv
   └── plots/               # Visualization plots
       ├── tmy_temperature_2010-2020_40.70_-74.00.png
       ├── tmy_wind_speed_2010-2020_40.70_-74.00.png
       └── ...

6. File Naming Convention
   Files are automatically named based on:
   - Data type (timeseries, tmy)
   - Date range or years
   - Location (latitude, longitude)
   - Variables (if subset selected)

7. CDS API Setup Required
   - You need a Climate Data Store (CDS) account
   - API key must be in ~/.cdsapirc
   - Register at: https://cds.climate.copernicus.eu/

TIPS:

- Use Option 2 (Complete TMY Workflow) for most use cases - it's comprehensive!
- Start with 10+ years of data for TMY
- Files are auto-named to avoid conflicts
- All outputs go to your specified project directory
- Conservative mode (2 workers) if you consistently hit rate limits
- Temperature is the primary variable for TMY month selection

WORKFLOW RECOMMENDATION:

For building energy simulation:
1. Choose Option 2 (Complete TMY Workflow)
2. Enter your building's location (lat/lon)
3. Use 10-15 years of recent data (e.g., 2010-2020)
4. Select all variables
5. Let it run - you'll get everything you need!

For more information:
  - GitHub: https://github.com/jmccarty/weather_file_builder
  - CDS: https://cds.climate.copernicus.eu/
    """)
    
    input("\nPress Enter to return to menu...")


def main():
    """Main interactive loop."""
    print_header()
    
    print("Welcome to the interactive interface!")
    print("This guided mode will help you download weather data and create TMY files.")
    print("\nMake sure you have:")
    print("  ✓ CDS API account (https://cds.climate.copernicus.eu/)")
    print("  ✓ API credentials in ~/.cdsapirc")
    
    while True:
        print_menu()
        choice = get_choice("Select option (1, 2, 8, or 9): ", ['1', '2', '8', '9'])
        
        if choice == '1':
            interactive_download_single_year()
        elif choice == '2':
            interactive_comprehensive_tmy()
        elif choice == '8':
            show_help()
        elif choice == '9':
            print("\nGoodbye!")
            sys.exit(0)


if __name__ == '__main__':
    main()
