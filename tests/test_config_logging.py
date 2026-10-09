"""Test config and logging functionality."""

import os
import shutil
import tempfile

from weather_file_builder.utils import (
    check_project_status,
    log_message,
    read_project_config,
    read_project_log,
    setup_project_directory,
    write_project_config,
)


def test_config_write_read():
    """Test configuration file writing and reading."""
    temp_dir = tempfile.mkdtemp()

    try:
        project_dir = setup_project_directory(os.path.join(temp_dir, "test_project"))

        config_path = write_project_config(
            project_dir=project_dir,
            latitude=40.7,
            longitude=-74.0,
            start_date="2010-01-01",
            end_date="2020-12-31",
            variables=["temperature", "wind"],
            tmy_type="typical",
            method="zscore",
            workflow_type="comprehensive_timeseries",
        )

        assert os.path.exists(config_path)

        config = read_project_config(project_dir)

        assert config is not None
        assert config["location"]["latitude"] == 40.7
        assert config["location"]["longitude"] == -74.0
        assert config["start_date"] == "2010-01-01"
        assert config["end_date"] == "2020-12-31"
        assert config["variables"] == ["temperature", "wind"]
        assert config["tmy_type"] == "typical"
        assert config["method"] == "zscore"
        assert config["workflow_type"] == "comprehensive_timeseries"

    finally:
        shutil.rmtree(temp_dir)


def test_logging():
    """Test logging functionality."""
    temp_dir = tempfile.mkdtemp()

    try:
        project_dir = setup_project_directory(os.path.join(temp_dir, "test_project"))

        log_message(project_dir, "Starting workflow")
        log_message(project_dir, "Download complete", level="SUCCESS")
        log_message(project_dir, "Warning: low memory", level="WARNING")
        log_message(project_dir, "Error occurred", level="ERROR")

        log_content = read_project_log(project_dir)

        assert log_content is not None
        assert "Starting workflow" in log_content
        assert "Download complete" in log_content
        assert "[SUCCESS]" in log_content
        assert "[WARNING]" in log_content
        assert "[ERROR]" in log_content

    finally:
        shutil.rmtree(temp_dir)


def test_project_status():
    """Test project status checking."""
    temp_dir = tempfile.mkdtemp()

    try:
        project_dir = setup_project_directory(os.path.join(temp_dir, "test_project"))

        status = check_project_status(project_dir)

        assert status["exists"] is True
        assert status["has_config"] is False
        assert status["has_log"] is True
        assert status["has_timeseries"] is False
        assert status["has_tmy"] is False
        assert status["has_plots"] is False

        write_project_config(
            project_dir=project_dir,
            latitude=40.7,
            longitude=-74.0,
            workflow_type="test",
        )

        status = check_project_status(project_dir)
        assert status["has_config"] is True
        assert status["config"] is not None

        timeseries_dir = os.path.join(project_dir, "timeseries")
        with open(os.path.join(timeseries_dir, "test.feather"), "w") as f:
            f.write("dummy")

        status = check_project_status(project_dir)
        assert status["has_timeseries"] is True

        tmy_dir = os.path.join(project_dir, "tmy")
        with open(os.path.join(tmy_dir, "tmy.csv"), "w") as f:
            f.write("dummy,tmy\n1,2\n")

        status = check_project_status(project_dir)
        assert status["has_tmy"] is True

        plots_dir = os.path.join(project_dir, "plots")
        with open(os.path.join(plots_dir, "plot.png"), "w") as f:
            f.write("dummy plot\n")

        status = check_project_status(project_dir)
        assert status["has_plots"] is True

    finally:
        shutil.rmtree(temp_dir)


def test_nonexistent_project():
    """Test status checking for non-existent project."""
    status = check_project_status("/path/that/does/not/exist")

    assert status["exists"] is False
    assert status["has_config"] is False
    assert status["has_log"] is False
    assert status["has_timeseries"] is False
    assert status["has_tmy"] is False
    assert status["has_plots"] is False
    assert status["config"] is None
