"""
Interactive CLI for weather-file-builder.

Provides a menu-driven interface for easier use without memorizing command syntax.
"""

import sys
from typing import Optional, List
from . import download_weather_data, download_multi_year, create_tmy, create_epw, create_tmy_plot


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
    print("  2. Download weather data (multiple years)")
    print("  3. Generate TMY (Typical Meteorological Year)")
    print("  4. Generate TMY with visualization")
    print("  5. Help & Documentation")
    print("  6. Exit")
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
            print("Invalid number. Please try again.")


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
            print("Invalid integer. Please try again.")


def get_years() -> List[int]:
    """Get year(s) from user."""
    print("\nYear Selection:")
    print("  1. Single year")
    print("  2. Year range (e.g., 2010-2020)")
    print("  3. Custom list")
    
    choice = get_choice("Select option (1-3): ", ['1', '2', '3'])
    
    if choice == '1':
        year = get_int("Enter year (1940-2024): ", min_val=1940, max_val=2024)
        return [year]
    elif choice == '2':
        start = get_int("Enter start year (1940-2024): ", min_val=1940, max_val=2024)
        end = get_int("Enter end year: ", min_val=start, max_val=2024)
        return list(range(start, end + 1))
    else:
        years_str = input("Enter years separated by commas (e.g., 2018,2019,2020): ").strip()
        return [int(y.strip()) for y in years_str.split(',')]


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
        print("\nAvailable variable groups:")
        print("  - temperature")
        print("  - pressure")
        print("  - wind")
        print("  - solar")
        print("  - precipitation")
        vars_str = input("Enter variables separated by commas: ").strip()
        return [v.strip() for v in vars_str.split(',')]


def get_concurrency_settings() -> tuple:
    """Get concurrency settings."""
    print("\nConcurrency Settings:")
    print("  1. Concurrent (fast, default) - 4 workers")
    print("  2. Concurrent aggressive - 6 workers")
    print("  3. Concurrent conservative - 2 workers")
    print("  4. Maximum (fastest, rate-limit risk) - 12 workers")
    print("  5. Sequential (slow, rate-limit safe)")
    
    choice = get_choice("Select mode (1-4): ", ['1', '2', '3', '4'])
    
    if choice == '1':
        return False, 4, 0.0
    elif choice == '2':
        return False, 6, 0.0
    elif choice == '3':
        return False, 2, 0.0
    elif choice == '4':
        return False, 12, 0.0
    else:
        delay = get_float("Enter delay between requests (seconds, 2.0 recommended): ", min_val=0.0)
        return True, 2, delay


def download_single_year():
    """Interactive single year download."""
    print("\n" + "="*70)
    print("Download Single Year")
    print("="*70)
    
    # Get location
    print("\nLocation:")
    lat = get_float("Enter latitude (-90 to 90): ", min_val=-90, max_val=90)
    lon = get_float("Enter longitude (-180 to 180): ", min_val=-180, max_val=180)
    
    # Get year
    years = get_years()
    if len(years) != 1:
        print("Error: Please select only one year for single year download")
        return
    year = years[0]
    
    # Get variables
    variables = get_variables()
    
    # Get concurrency
    _, workers, _ = get_concurrency_settings()
    
    # Get output
    default_name = f"weather_{year}_{lat:.2f}_{lon:.2f}.csv"
    output = input(f"\nOutput file [{default_name}]: ").strip()
    if not output:
        output = default_name
    
    # Confirm
    print("\n" + "-"*70)
    print("Summary:")
    print(f"  Location: {lat}, {lon}")
    print(f"  Year: {year}")
    print(f"  Variables: {variables or 'all'}")
    print(f"  Workers: {workers}")
    print(f"  Output: {output}")
    print("-"*70)
    
    confirm = get_choice("\nProceed with download? (y/n): ", ['y', 'n', 'Y', 'N'])
    if confirm.lower() != 'y':
        print("Download cancelled.")
        return
    
    # Download
    print("\nDownloading...")
    try:
        df = download_weather_data(
            latitude=lat,
            longitude=lon,
            year=year,
            variables=variables,
            max_workers=workers
        )
        
        df.to_csv(output, index=False)
        print(f"\n✓ Success! Saved to: {output}")
        print(f"  {len(df)} records")
        print(f"  {len(df.columns)} columns")
    except Exception as e:
        print(f"\n✗ Error: {e}")


def download_multi_year():
    """Interactive multi-year download."""
    print("\n" + "="*70)
    print("Download Multiple Years")
    print("="*70)
    
    # Get location
    print("\nLocation:")
    lat = get_float("Enter latitude (-90 to 90): ", min_val=-90, max_val=90)
    lon = get_float("Enter longitude (-180 to 180): ", min_val=-180, max_val=180)
    
    # Get years
    years = get_years()
    if len(years) < 2:
        print("Error: Please select at least 2 years for multi-year download")
        return
    
    # Get variables
    variables = get_variables()
    
    # Get concurrency
    sequential, workers, delay = get_concurrency_settings()
    
    # Get output
    default_name = f"weather_{years[0]}-{years[-1]}_{lat:.2f}_{lon:.2f}.csv"
    output = input(f"\nOutput file [{default_name}]: ").strip()
    if not output:
        output = default_name
    
    # Confirm
    print("\n" + "-"*70)
    print("Summary:")
    print(f"  Location: {lat}, {lon}")
    print(f"  Years: {years[0]}-{years[-1]} ({len(years)} years)")
    print(f"  Variables: {variables or 'all'}")
    print(f"  Mode: {'Sequential' if sequential else 'Concurrent'}")
    print(f"  Workers: {workers}")
    if sequential:
        print(f"  Delay: {delay}s")
    print(f"  Output: {output}")
    print(f"  Estimated time: {len(years) * 2}-{len(years) * 5} minutes")
    print("-"*70)
    
    confirm = get_choice("\nProceed with download? (y/n): ", ['y', 'n', 'Y', 'N'])
    if confirm.lower() != 'y':
        print("Download cancelled.")
        return
    
    # Download
    print("\nDownloading...")
    try:
        df = download_multi_year(
            latitude=lat,
            longitude=lon,
            years=years,
            variables=variables,
            delay_between_months=delay,
            max_workers=workers,
            sequential_years=sequential
        )
        
        df.to_csv(output, index=False)
        print(f"\n✓ Success! Saved to: {output}")
        print(f"  {len(df)} records")
        print(f"  {df['Year'].nunique()} years")
        print(f"  {len(df.columns)} columns")
    except Exception as e:
        print(f"\n✗ Error: {e}")


def generate_tmy_basic():
    """Interactive TMY generation (CSV only)."""
    print("\n" + "="*70)
    print("Generate TMY (Typical Meteorological Year)")
    print("="*70)
    
    # Get location
    print("\nLocation:")
    lat = get_float("Enter latitude (-90 to 90): ", min_val=-90, max_val=90)
    lon = get_float("Enter longitude (-180 to 180): ", min_val=-180, max_val=180)
    
    # Get years
    print("\nNote: TMY typically requires 10+ years for best results")
    years = get_years()
    if len(years) < 3:
        print(f"Warning: You selected only {len(years)} years. Recommend 10+.")
        confirm = get_choice("Continue anyway? (y/n): ", ['y', 'n', 'Y', 'N'])
        if confirm.lower() != 'y':
            return
    
    # TMY settings
    print("\nTMY Type:")
    print("  1. Typical (most representative)")
    print("  2. Extreme warm")
    print("  3. Extreme cold")
    tmy_choice = get_choice("Select type (1-3): ", ['1', '2', '3'])
    tmy_type = {'1': 'typical', '2': 'extreme_warm', '3': 'extreme_cold'}[tmy_choice]
    
    print("\nStatistical Method:")
    print("  1. Z-score (recommended)")
    print("  2. Kolmogorov-Smirnov")
    method_choice = get_choice("Select method (1-2): ", ['1', '2'])
    method = {'1': 'zscore', '2': 'ks'}[method_choice]
    
    # Get concurrency
    sequential, workers, delay = get_concurrency_settings()
    
    # Get output
    default_name = f"tmy_{years[0]}-{years[-1]}_{lat:.2f}_{lon:.2f}.csv"
    output = input(f"\nOutput file [{default_name}]: ").strip()
    if not output:
        output = default_name
    
    # Confirm
    print("\n" + "-"*70)
    print("Summary:")
    print(f"  Location: {lat}, {lon}")
    print(f"  Years: {years[0]}-{years[-1]} ({len(years)} years)")
    print(f"  TMY Type: {tmy_type}")
    print(f"  Method: {method}")
    print(f"  Mode: {'Sequential' if sequential else 'Concurrent'}")
    print(f"  Workers: {workers}")
    print(f"  Output: {output}")
    print(f"  Estimated time: {len(years) * 2}-{len(years) * 5} minutes")
    print("-"*70)
    
    confirm = get_choice("\nProceed? (y/n): ", ['y', 'n', 'Y', 'N'])
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    
    # Download and generate
    print("\n[1/2] Downloading multi-year data...")
    try:
        df = download_multi_year(
            latitude=lat,
            longitude=lon,
            years=years,
            delay_between_months=delay,
            max_workers=workers,
            sequential_years=sequential
        )
        
        print("\n[2/2] Generating TMY...")
        tmy_data, selected_years = create_tmy(
            df,
            variable='Temperature',
            file_type=tmy_type,
            test_method=method
        )
        
        tmy_data.to_csv(output, index=False)
        print(f"\n✓ Success! TMY saved to: {output}")
        print(f"  {len(tmy_data)} records")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


def generate_tmy_with_viz():
    """Interactive TMY generation with visualization."""
    print("\n" + "="*70)
    print("Generate TMY with Visualization")
    print("="*70)
    
    # Get location
    print("\nLocation:")
    lat = get_float("Enter latitude (-90 to 90): ", min_val=-90, max_val=90)
    lon = get_float("Enter longitude (-180 to 180): ", min_val=-180, max_val=180)
    
    # Get years
    print("\nNote: TMY typically requires 10+ years for best results")
    years = get_years()
    if len(years) < 3:
        print(f"Warning: You selected only {len(years)} years. Recommend 10+.")
        confirm = get_choice("Continue anyway? (y/n): ", ['y', 'n', 'Y', 'N'])
        if confirm.lower() != 'y':
            return
    
    # TMY settings
    print("\nTMY Type:")
    print("  1. Typical (most representative)")
    print("  2. Extreme warm")
    print("  3. Extreme cold")
    tmy_choice = get_choice("Select type (1-3): ", ['1', '2', '3'])
    tmy_type = {'1': 'typical', '2': 'extreme_warm', '3': 'extreme_cold'}[tmy_choice]
    
    print("\nStatistical Method:")
    print("  1. Z-score (recommended)")
    print("  2. Kolmogorov-Smirnov")
    method_choice = get_choice("Select method (1-2): ", ['1', '2'])
    method = {'1': 'zscore', '2': 'ks'}[method_choice]
    
    # Get concurrency
    sequential, workers, delay = get_concurrency_settings()
    
    # Get output
    default_csv = f"tmy_{years[0]}-{years[-1]}_{lat:.2f}_{lon:.2f}.csv"
    default_plot = f"tmy_viz_{years[0]}-{years[-1]}_{lat:.2f}_{lon:.2f}.png"
    
    output_csv = input(f"\nCSV output file [{default_csv}]: ").strip() or default_csv
    output_plot = input(f"Plot output file [{default_plot}]: ").strip() or default_plot
    
    # Confirm
    print("\n" + "-"*70)
    print("Summary:")
    print(f"  Location: {lat}, {lon}")
    print(f"  Years: {years[0]}-{years[-1]} ({len(years)} years)")
    print(f"  TMY Type: {tmy_type}")
    print(f"  Method: {method}")
    print(f"  Mode: {'Sequential' if sequential else 'Concurrent'}")
    print(f"  Workers: {workers}")
    print(f"  CSV Output: {output_csv}")
    print(f"  Plot Output: {output_plot}")
    print(f"  Estimated time: {len(years) * 2}-{len(years) * 5} minutes")
    print("-"*70)
    
    confirm = get_choice("\nProceed? (y/n): ", ['y', 'n', 'Y', 'N'])
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    
    # Download and generate
    print("\n[1/3] Downloading multi-year data...")
    try:
        df = download_multi_year(
            latitude=lat,
            longitude=lon,
            years=years,
            delay_between_months=delay,
            max_workers=workers,
            sequential_years=sequential
        )
        
        print("\n[2/3] Generating TMY...")
        tmy_data, selected_years = create_tmy(
            df,
            variable='Temperature',
            file_type=tmy_type,
            test_method=method
        )
        
        tmy_data.to_csv(output_csv, index=False)
        print(f"✓ TMY data saved to: {output_csv}")
        
        print("\n[3/3] Creating visualization...")
        fig = create_tmy_plot(
            multi_year_data=df,
            tmy_data=tmy_data,
            selected_years=selected_years,
            latitude=lat,
            longitude=lon,
            variable='Temperature',
            output_path=output_plot
        )
        
        print(f"\n✓ Success!")
        print(f"  TMY CSV: {output_csv}")
        print(f"  Visualization: {output_plot}")
        print(f"  {len(tmy_data)} records")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


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

2. TMY (Typical Meteorological Year)
   - Single year constructed from multiple years of data
   - Each month selected from the year that best represents long-term average
   - Used in building energy simulation (EnergyPlus, etc.)

3. Concurrency Settings
   - Concurrent: Downloads multiple months in parallel (faster)
   - Sequential: Downloads one month at a time (safer for rate limits)
   - Workers: Number of parallel downloads (2-8 recommended)

4. CDS API Setup Required
   - You need a Climate Data Store (CDS) account
   - API key must be in ~/.cdsapirc
   - Register at: https://cds.climate.copernicus.eu/

TIPS:

- For TMY: Use 10+ years of data for best results
- Start with 4 workers (balanced), adjust if hitting rate limits
- Temperature is the primary variable for TMY month selection
- Sequential mode with 2s delay if you consistently hit rate limits

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
        
        choice = get_choice("Select option (1-6): ", ['1', '2', '3', '4', '5', '6'])
        
        try:
            if choice == '1':
                download_single_year()
            elif choice == '2':
                download_multi_year()
            elif choice == '3':
                generate_tmy_basic()
            elif choice == '4':
                generate_tmy_with_viz()
            elif choice == '5':
                show_help()
            elif choice == '6':
                print("\nThank you for using Weather File Builder!")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            continue
        except Exception as e:
            print(f"\n✗ Unexpected error: {e}")
            print("Returning to main menu...")
            continue


if __name__ == '__main__':
    main()
