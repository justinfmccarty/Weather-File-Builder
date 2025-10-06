"""
Command-line interface for weather-file-builder.
"""

import argparse
import sys
import os
from typing import List, Optional

from . import download_weather_data, download_multi_year, download_time_series, create_epw, create_tmy, comprehensive_timeseries_workflow
from .utils import (
    setup_project_directory, 
    get_output_path,
    check_project_status,
    read_project_config,
    write_tmy_data
)


def parse_years(years_str: str) -> List[int]:
    """
    Parse year specification from command line.
    
    Examples: "2020", "2018,2019,2020", "2015-2020"
    """
    if '-' in years_str and ',' not in years_str:
        # Range: "2015-2020"
        start, end = years_str.split('-')
        return list(range(int(start), int(end) + 1))
    elif ',' in years_str:
        # List: "2018,2019,2020"
        return [int(y.strip()) for y in years_str.split(',')]
    else:
        # Single year: "2020"
        return [int(years_str)]


def cmd_download(args):
    """Handle download command."""
    # Parse variables if provided
    variables = args.variables.split(',') if args.variables else None
    
    # Parse years
    years = parse_years(args.years)
    
    if len(years) == 1:
        # Single year download
        print(f"Downloading {years[0]} data...")
        df = download_weather_data(
            latitude=args.lat,
            longitude=args.lon,
            year=years[0],
            variables=variables,
            max_workers=args.workers
        )
    else:
        # Multi-year download
        print(f"Downloading {len(years)} years: {years[0]}-{years[-1]}")
        df = download_multi_year(
            latitude=args.lat,
            longitude=args.lon,
            years=years,
            variables=variables,
            delay_between_months=args.delay,
            max_workers=args.workers,
            sequential_years=args.sequential
        )
    
    # Save output
    df.to_csv(args.output, index=False)
    print(f"\n✓ Saved to: {args.output}")
    print(f"  {len(df)} records")
    print(f"  {df['Year'].nunique()} year(s)")
    print(f"  {len(df.columns)} columns")


def cmd_timeseries(args):
    """Handle timeseries download command."""
    # Parse variables if provided
    variables = args.variables.split(',') if args.variables else None
    
    # Download timeseries data
    print(f"Downloading timeseries from {args.start_date} to {args.end_date}...")
    df = download_time_series(
        latitude=args.lat,
        longitude=args.lon,
        start_date=args.start_date,
        end_date=args.end_date,
        variables=variables,
        retry_attempts=args.retry
    )
    
    # Save output (feather format for timeseries)
    if args.output.endswith('.csv'):
        df.to_csv(args.output, index=False)
        print(f"\n✓ Saved to: {args.output}")
    else:
        # Default to feather format
        if not args.output.endswith('.feather'):
            args.output = args.output.rsplit('.', 1)[0] + '.feather'
        df.to_feather(args.output)
        print(f"\n✓ Saved to: {args.output} (feather format)")
    
    print(f"  {len(df)} records")
    print(f"  {df['Year'].nunique()} year(s)")
    print(f"  {len(df.columns)} columns")


def cmd_tmy(args):
    """Handle TMY generation command."""
    # Parse years
    years = parse_years(args.years)
    
    if len(years) < 3:
        print("Warning: TMY typically requires 10+ years of data for best results")
        print(f"         You specified only {len(years)} years")
    
    # Download multi-year data
    print(f"Downloading {len(years)} years for TMY: {years[0]}-{years[-1]}")
    df = download_multi_year(
        latitude=args.lat,
        longitude=args.lon,
        years=years,
        delay_between_months=args.delay,
        max_workers=args.workers,
        sequential_years=args.sequential
    )
    
    # Create TMY
    print("\nGenerating TMY...")
    tmy_data, selected_years = create_tmy(df)
    
    # Generate EPW or CSV
    if args.output.endswith('.epw'):
        print(f"\nCreating EPW file: {args.output}")
        create_epw(
            data=tmy_data,
            output_path=args.output,
            location_name=args.location or f"{args.lat}, {args.lon}",
            latitude=args.lat,
            longitude=args.lon,
            timezone=args.timezone or 0,
            elevation=args.elevation or 0
        )
    else:
        # Save as CSV
        write_tmy_data(tmy_data, args.output, latitude=args.lat, longitude=args.lon, elevation=args.elevation or 0)
        print(f"\n✓ Saved TMY to: {args.output}")


def cmd_workflow(args):
    """Handle comprehensive workflow command."""
    # Parse variables if provided
    variables = args.variables.split(',') if args.variables else None
    
    print(f"Starting comprehensive TMY workflow...")
    print(f"Location: ({args.lat}, {args.lon})")
    print(f"Date range: {args.start_date} to {args.end_date}")
    print(f"Project directory: {args.project_dir}")
    
    # Check if project already exists
    if os.path.exists(args.project_dir):
        status = check_project_status(args.project_dir)
        
        if status['has_config']:
            config = status['config']
            print("\n" + "="*70)
            print("⚠ EXISTING PROJECT FOUND")
            print("="*70)
            print(f"Location: {config['location']['latitude']}, {config['location']['longitude']}")
            print(f"Created: {config.get('created', 'Unknown')}")
            print(f"Workflow: {config.get('workflow_type', 'Unknown')}")
            print(f"\nStatus:")
            print(f"  Timeseries data: {'✓' if status['has_timeseries'] else '✗'}")
            print(f"  TMY data: {'✓' if status['has_tmy'] else '✗'}")
            print(f"  Plots: {'✓' if status['has_plots'] else '✗'}")
            print("="*70)
            print("The workflow will skip already completed steps.")
    
    # Execute workflow
    results = comprehensive_timeseries_workflow(
        latitude=args.lat,
        longitude=args.lon,
        start_date=args.start_date,
        end_date=args.end_date,
        project_dir=args.project_dir,
        variables=variables,
        tmy_type=args.tmy_type,
        method=args.method,
        retry_attempts=args.retry
    )
    
    # Print summary
    print("\n" + "="*70)
    print("✓ Workflow Complete!")
    print("="*70)
    print(f"\nProject directory: {results['project_dir']}")
    print(f"Configuration: {results['config_path']}")
    print(f"Log file: {os.path.join(results['project_dir'], 'project.log')}")
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


def main():
    """Main CLI entry point."""
    # Check if running in interactive mode
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ['-i', '--interactive', 'interactive']):
        # No arguments or -i flag: launch interactive mode
        from .interactive import main as interactive_main
        interactive_main()
        return
    
    parser = argparse.ArgumentParser(
        prog='weather-file-builder',
        description='Build weather files (EPW, TMY) from ERA5 reanalysis data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (guided prompts) - RECOMMENDED FOR BEGINNERS
  %(prog)s
  %(prog)s --interactive
  
  # Complete TMY workflow (download → TMY → visualizations) - RECOMMENDED
  %(prog)s workflow --lat 40.7 --lon -74.0 \\
      --start-date 2010-01-01 --end-date 2020-12-31 \\
      --project-dir ./my_project
  
  # Download single year
  %(prog)s download --lat 40.7 --lon -74.0 --years 2020 --output weather_2020.csv
  
  # Download multiple years
  %(prog)s download --lat 40.7 --lon -74.0 --years 2018-2020 --output weather.csv
  
  # Download timeseries (fast, for continuous date ranges)
  %(prog)s timeseries --lat 40.7 --lon -74.0 \\
      --start-date 2020-01-01 --end-date 2020-12-31 --output weather_2020.feather

For more information, visit: https://github.com/jmccarty/weather_file_builder
        """
    )
    
    # Add interactive flag
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Launch interactive mode with guided prompts'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Download command
    download_parser = subparsers.add_parser(
        'download',
        help='Download weather data'
    )
    download_parser.add_argument(
        '--lat', type=float, required=True,
        help='Latitude in decimal degrees (-90 to 90)'
    )
    download_parser.add_argument(
        '--lon', type=float, required=True,
        help='Longitude in decimal degrees (-180 to 180)'
    )
    download_parser.add_argument(
        '--years', type=str, required=True,
        help='Year(s) to download. Examples: "2020", "2018,2019,2020", "2015-2020"'
    )
    download_parser.add_argument(
        '--variables', type=str,
        help='Variables to download (comma-separated). Options: temperature, pressure, '
             'wind, solar, precipitation, all. Default: all'
    )
    download_parser.add_argument(
        '--output', type=str, required=True,
        help='Output file path (CSV format)'
    )
    download_parser.add_argument(
        '--project-dir', type=str,
        help='Project directory for organized outputs (optional, will use output path if not specified)'
    )
    download_parser.add_argument(
        '--delay', type=float, default=0.0,
        help='Delay between requests in seconds (only for sequential mode, default: 0)'
    )
    download_parser.add_argument(
        '--workers', type=int, default=4,
        help='Max concurrent downloads (default: 4). Conservative: 2-3, Balanced: 4-5, Aggressive: 6-8'
    )
    download_parser.add_argument(
        '--sequential', action='store_true',
        help='Use sequential download mode (slower but more reliable if hitting rate limits)'
    )
    
    # Timeseries command (fast download for continuous time periods)
    timeseries_parser = subparsers.add_parser(
        'timeseries',
        help='Download time series data (fast, limited variables)'
    )
    timeseries_parser.add_argument(
        '--lat', type=float, required=True,
        help='Latitude in decimal degrees (-90 to 90)'
    )
    timeseries_parser.add_argument(
        '--lon', type=float, required=True,
        help='Longitude in decimal degrees (-180 to 180)'
    )
    timeseries_parser.add_argument(
        '--start-date', type=str, required=True,
        help='Start date in YYYY-MM-DD format (e.g., "2020-01-01")'
    )
    timeseries_parser.add_argument(
        '--end-date', type=str, required=True,
        help='End date in YYYY-MM-DD format (e.g., "2020-12-31")'
    )
    timeseries_parser.add_argument(
        '--variables', type=str,
        help='Variables to download (comma-separated). Options: temperature, pressure, '
             'wind, solar, precipitation, all. Default: all. Note: ERA5-Land timeseries '
             'has a more limited variable set than standard downloads.'
    )
    timeseries_parser.add_argument(
        '--output', type=str, required=True,
        help='Output file path (feather format by default, or .csv if extension specified)'
    )
    timeseries_parser.add_argument(
        '--project-dir', type=str,
        help='Project directory for organized outputs (optional, will use output path if not specified)'
    )
    timeseries_parser.add_argument(
        '--retry', type=int, default=3,
        help='Number of retry attempts (default: 3)'
    )
    
    # Comprehensive TMY workflow command (new)
    workflow_parser = subparsers.add_parser(
        'workflow',
        help='Complete TMY workflow: download → TMY → visualizations'
    )
    workflow_parser.add_argument(
        '--lat', type=float, required=True,
        help='Latitude in decimal degrees (-90 to 90)'
    )
    workflow_parser.add_argument(
        '--lon', type=float, required=True,
        help='Longitude in decimal degrees (-180 to 180)'
    )
    workflow_parser.add_argument(
        '--start-date', type=str, required=True,
        help='Start date in YYYY-MM-DD format (e.g., "2010-01-01")'
    )
    workflow_parser.add_argument(
        '--end-date', type=str, required=True,
        help='End date in YYYY-MM-DD format (e.g., "2020-12-31")'
    )
    workflow_parser.add_argument(
        '--project-dir', type=str, required=True,
        help='Project directory for all outputs (will be created if needed)'
    )
    workflow_parser.add_argument(
        '--variables', type=str,
        help='Variables to download (comma-separated). Default: all'
    )
    workflow_parser.add_argument(
        '--tmy-type', type=str, default='typical',
        choices=['typical', 'extreme_warm', 'extreme_cold'],
        help='Type of TMY to generate (default: typical)'
    )
    workflow_parser.add_argument(
        '--method', type=str, default='zscore',
        choices=['zscore', 'ks'],
        help='Statistical method for TMY selection (default: zscore)'
    )
    workflow_parser.add_argument(
        '--retry', type=int, default=3,
        help='Number of retry attempts (default: 3)'
    )
    
    # TMY command (legacy, kept for backwards compatibility)
    tmy_parser = subparsers.add_parser(
        'tmy',
        help='Generate Typical Meteorological Year (legacy)'
    )
    tmy_parser.add_argument(
        '--lat', type=float, required=True,
        help='Latitude in decimal degrees'
    )
    tmy_parser.add_argument(
        '--lon', type=float, required=True,
        help='Longitude in decimal degrees'
    )
    tmy_parser.add_argument(
        '--years', type=str, required=True,
        help='Years for TMY (10+ recommended). Examples: "2010-2020", "2010,2012,2015"'
    )
    tmy_parser.add_argument(
        '--output', type=str, required=True,
        help='Output file path (.epw or .csv)'
    )
    tmy_parser.add_argument(
        '--location', type=str,
        help='Location name for EPW header (e.g., "New York City, NY, USA")'
    )
    tmy_parser.add_argument(
        '--timezone', type=float,
        help='Timezone offset from UTC (e.g., -5 for EST)'
    )
    tmy_parser.add_argument(
        '--elevation', type=float,
        help='Elevation in meters'
    )
    tmy_parser.add_argument(
        '--delay', type=float, default=0.0,
        help='Delay between requests in seconds (only for sequential mode, default: 0)'
    )
    tmy_parser.add_argument(
        '--workers', type=int, default=4,
        help='Max concurrent downloads (default: 4). Conservative: 2-3, Balanced: 4-5, Aggressive: 6-8, Maximum 12'
    )
    tmy_parser.add_argument(
        '--sequential', action='store_true',
        help='Use sequential download mode (slower but more reliable if hitting rate limits)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    try:
        if args.command == 'download':
            cmd_download(args)
        elif args.command == 'timeseries':
            cmd_timeseries(args)
        elif args.command == 'workflow':
            cmd_workflow(args)
        elif args.command == 'tmy':
            cmd_tmy(args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
