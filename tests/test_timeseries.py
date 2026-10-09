"""Integration test for timeseries download (requires CDS API access)."""

import pandas as pd
import pytest

from weather_file_builder.core import download_time_series


@pytest.mark.slow
@pytest.mark.integration
def test_download_time_series():
    """Download a short timeseries and verify the result."""
    result = download_time_series(
        latitude=40.7128,
        longitude=-74.0060,
        start_date="1993-01-01",
        end_date="1993-03-31",
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0
    assert "Year" in result.columns
    assert "Temperature" in result.columns
