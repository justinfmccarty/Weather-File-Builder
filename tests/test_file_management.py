"""Test file management utilities."""

import os
import tempfile
import shutil

from weather_file_builder.utils import generate_filename, get_output_path, setup_project_directory


def test_generate_filename():
    """Test filename generation."""
    fn1 = generate_filename(
        "timeseries",
        40.7,
        -74.0,
        start_date="2020-01-01",
        end_date="2020-12-31",
    )
    assert fn1 == "timeseries_2020-01-01_2020-12-31_40.70_-74.00.feather"

    fn2 = generate_filename(
        "tmy",
        40.7,
        -74.0,
        years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020],
    )
    assert fn2 == "tmy_2010-2020_40.70_-74.00.csv"

    fn3 = generate_filename(
        "timeseries",
        40.7,
        -74.0,
        start_date="2020-01-01",
        end_date="2020-12-31",
        variables=["temperature", "wind"],
    )
    assert "temperature" in fn3 and "wind" in fn3


def test_project_directory():
    """Test project directory setup."""
    temp_dir = tempfile.mkdtemp()

    try:
        project_dir = setup_project_directory(os.path.join(temp_dir, "test_project"))

        assert os.path.exists(project_dir)
        assert os.path.exists(os.path.join(project_dir, "timeseries"))
        assert os.path.exists(os.path.join(project_dir, "tmy"))
        assert os.path.exists(os.path.join(project_dir, "plots"))

    finally:
        shutil.rmtree(temp_dir)


def test_output_paths():
    """Test output path generation."""
    project_dir = "/path/to/project"

    path1 = get_output_path(
        project_dir=project_dir,
        data_type="timeseries",
        latitude=40.7,
        longitude=-74.0,
        start_date="2020-01-01",
        end_date="2020-12-31",
    )
    assert path1.startswith("/path/to/project/timeseries/")
    assert path1.endswith(".feather")

    path2 = get_output_path(
        project_dir=project_dir,
        data_type="tmy",
        latitude=40.7,
        longitude=-74.0,
        years=[2010, 2020],
    )
    assert path2.startswith("/path/to/project/tmy/")
    assert "tmy" in path2

    path3 = get_output_path(
        project_dir=project_dir,
        data_type="plot",
        latitude=40.7,
        longitude=-74.0,
        filename="custom_plot.png",
    )
    assert path3.startswith("/path/to/project/plots/")
    assert path3.endswith("custom_plot.png")
