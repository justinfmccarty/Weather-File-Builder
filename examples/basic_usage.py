"""
Example usage of weather-file-builder v2.0.0.

All examples require a configured ECMWF Data Stores API key.
See: https://ecmwf.github.io/ecmwf-datastores-client/
"""

import logging

from weather_file_builder import (
    comprehensive_workflow,
    create_epw,
    create_tmy,
    create_tmy_plot,
    download_multi_year,
    download_single_year,
)

logging.basicConfig(level=logging.INFO)


def example_single_year():
    """Download a single year of data."""
    df = download_single_year(
        latitude=40.7128,
        longitude=-74.0060,
        year=2023,
    )
    print(f"Downloaded {len(df)} records, {len(df.columns)} columns")
    df.to_csv("nyc_2023.csv", index=False)


def example_multi_year():
    """Download multiple years."""
    df = download_multi_year(
        latitude=51.5074,
        longitude=-0.1278,
        start_year=2020,
        end_year=2022,
    )
    print(f"Downloaded {len(df)} records across {df['Year'].nunique()} years")
    df.to_csv("london_2020-2022.csv", index=False)


def example_tmy_and_epw():
    """Generate TMY and EPW from multi-year data."""
    df = download_multi_year(
        latitude=40.7128,
        longitude=-74.0060,
        start_year=2010,
        end_year=2020,
    )

    tmy_data, selected_years = create_tmy(df, variable="Temperature")
    print(f"TMY: {len(tmy_data)} records, selected years: {selected_years}")

    fig = create_tmy_plot(
        multi_year_data=df,
        tmy_data=tmy_data,
        selected_years=selected_years,
        latitude=40.7128,
        longitude=-74.0060,
        variable="Temperature",
        output_path="tmy_construction.png",
    )

    create_epw(
        data=tmy_data,
        output_path="nyc_tmy.epw",
        location_name="New York City, NY, US",
        latitude=40.7128,
        longitude=-74.0060,
        timezone=-5,
        elevation=10,
    )


def example_comprehensive_workflow():
    """Run the full end-to-end pipeline."""
    results = comprehensive_workflow(
        latitude=40.7128,
        longitude=-74.0060,
        start_date="2010-01-01",
        end_date="2020-12-31",
        project_dir="./nyc_project",
    )
    print(f"Outputs: {list(results.keys())}")


if __name__ == "__main__":
    print("Weather File Builder v2.0.0 - Examples")
    print()
    print("Configure your API key in ~/.ecmwfdatastoresrc")
    print("Then uncomment the example you want to run.")
    print()

    # example_single_year()
    # example_multi_year()
    example_tmy_and_epw()
    # example_comprehensive_workflow()
