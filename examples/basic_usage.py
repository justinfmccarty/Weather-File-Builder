"""
Example usage of weather-file-builder package.
"""

from weather_file_builder import download_weather_data, download_multi_year
from weather_file_builder import create_tmy, create_epw, create_tmy_plot


def example_single_year():
    """Download a single year of data with concurrent downloads."""
    print("="*60)
    print("Example 1: Single Year Download (Concurrent)")
    print("="*60)
    
    # Download one year for New York City - concurrent by default
    df = download_weather_data(
        latitude=40.7128,
        longitude=-74.0060,
        year=2023,
        max_workers=4  # 4 concurrent downloads (balanced)
    )
    
    print(f"\nDownloaded {len(df)} records")
    print(f"Columns: {list(df.columns)}")
    print("\nFirst few rows:")
    print(df.head())
    
    # Save to CSV
    df.to_csv('nyc_2023.csv', index=False)
    print("\nSaved to: nyc_2023.csv")


def example_multi_year():
    """Download multiple years with concurrent downloads."""
    print("\n" + "="*60)
    print("Example 2: Multi-Year Download (Concurrent)")
    print("="*60)
    
    # Download 3 years for London - concurrent by default
    df = download_multi_year(
        latitude=51.5074,
        longitude=-0.1278,
        years=range(2020, 2023),  # 2020, 2021, 2022
        max_workers=4  # 4 concurrent downloads per year
    )
    
    print(f"\nDownloaded {len(df)} records across {df['Year'].nunique()} years")
    print(f"Years: {sorted(df['Year'].unique())}")
    
    # Save to CSV
    df.to_csv('london_2020-2022.csv', index=False)
    print("\nSaved to: london_2020-2022.csv")


def example_specific_variables():
    """Download only specific variables."""
    print("\n" + "="*60)
    print("Example 3: Specific Variables Only")
    print("="*60)
    
    # Download just temperature and wind data
    df = download_weather_data(
        latitude=37.7749,
        longitude=-122.4194,
        year=2023,
        variables=['temperature', 'wind'],
        max_workers=6  # More aggressive for faster download
    )
    
    print(f"\nDownloaded {len(df)} records")
    print(f"Columns: {list(df.columns)}")
    
    # Save to CSV
    df.to_csv('sf_temp_wind_2023.csv', index=False)
    print("\nSaved to: sf_temp_wind_2023.csv")


def example_sequential():
    """Use sequential mode if hitting rate limits."""
    print("\n" + "="*60)
    print("Example 4: Sequential Download (Rate-Limit Friendly)")
    print("="*60)
    
    # Use sequential mode with delays
    df = download_multi_year(
        latitude=40.7128,
        longitude=-74.0060,
        years=[2020, 2021],
        sequential_years=True,  # Sequential mode
        delay_between_months=2.0  # 2 second delay between months
    )
    
    print(f"\nDownloaded {len(df)} records")
    df.to_csv('nyc_sequential.csv', index=False)
    print("Saved to: nyc_sequential.csv")


def example_tmy():
    """Generate a Typical Meteorological Year with visualization."""
    print("\n" + "="*60)
    print("Example 5: TMY Generation with Visualization")
    print("="*60)
    
    # Download 5 years (normally you'd want 10+)
    print("Note: Using 5 years for demo. Typically 10+ years recommended.")
    df = download_multi_year(
        latitude=40.7128,
        longitude=-74.0060,
        years=range(2018, 2023),
        max_workers=4  # Balanced concurrency
    )
    
    # Create TMY - now returns both data and selected years
    print("\nGenerating TMY...")
    tmy_data, selected_years = create_tmy(df, variable='Temperature')
    
    print(f"\nTMY has {len(tmy_data)} records")
    print(f"Selected years by month: {selected_years}")
    
    # Save as CSV
    tmy_data.to_csv('nyc_tmy.csv', index=False)
    print("Saved TMY data to: nyc_tmy.csv")
    
    # Create visualization showing how TMY was constructed
    print("\nCreating TMY visualization...")
    fig = create_tmy_plot(
        multi_year_data=df,
        tmy_data=tmy_data,
        selected_years=selected_years,
        latitude=40.7128,
        longitude=-74.0060,
        variable='Temperature',
        output_path='tmy_construction.png'
    )
    print("Saved visualization to: tmy_construction.png")
    
    # Try to create EPW (will show it's not implemented yet)
    try:
        create_epw(
            data=tmy_data,
            output_path='nyc_tmy.epw',
            location_name='New York City, NY, USA',
            latitude=40.7128,
            longitude=-74.0060,
            timezone=-5,
            elevation=10
        )
    except NotImplementedError as e:
        print(f"\nNote: {e}")


if __name__ == '__main__':
    print("Weather File Builder - Examples")
    print("\nNote: These examples will make real API calls to CDS.")
    print("Make sure you have your ~/.cdsapirc file configured.")
    print("Each example may take several minutes to run.\n")
    print("\nConcurrency options:")
    print("  - Conservative (2-3 workers): Slower but more reliable")
    print("  - Balanced (4-5 workers): Recommended default")
    print("  - Aggressive (6-8 workers): Faster but may hit rate limits")
    print("  - Sequential mode: Use if consistently hitting rate limits\n")
    
    # Run examples (comment out the ones you don't want)
    # example_single_year()
    # example_multi_year()
    # example_specific_variables()
    # example_sequential()
    # example_tmy()
    
    print("\nTo run an example, uncomment it in the code.")
