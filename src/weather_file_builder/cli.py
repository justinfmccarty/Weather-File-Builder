"""
Command-line interface for weather-file-builder.
"""

import argparse
import sys
from typing import List, Optional

from . import download_weather_data, download_multi_year, create_epw, create_tmy


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
        tmy_data.to_csv(args.output, index=False)
        print(f"\n✓ Saved TMY to: {args.output}")


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
  # Interactive mode (guided prompts)
  %(prog)s
  %(prog)s --interactive
  
  # Download single year
  %(prog)s download --lat 40.7 --lon -74.0 --years 2020 --output weather_2020.csv
  
  # Download multiple years
  %(prog)s download --lat 40.7 --lon -74.0 --years 2018-2020 --output weather.csv
  
  # Download specific variables only
  %(prog)s download --lat 51.5 --lon -0.1 --years 2023 --variables temperature,wind \\
      --output london_2023.csv
  
  # Create TMY from 10 years of data
  %(prog)s tmy --lat 40.7 --lon -74.0 --years 2010-2020 --output tmy_nyc.epw \\
      --location "New York City, NY" --timezone -5 --elevation 10

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
    
    # TMY command
    tmy_parser = subparsers.add_parser(
        'tmy',
        help='Generate Typical Meteorological Year'
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
