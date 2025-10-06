#!/usr/bin/env python3
"""
Test config and logging functionality.
"""

import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from weather_file_builder.utils import (
    write_project_config,
    read_project_config,
    log_message,
    read_project_log,
    check_project_status,
    setup_project_directory
)


def test_config_write_read():
    """Test configuration file writing and reading."""
    print("Testing configuration file operations...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Setup project directory
        project_dir = setup_project_directory(os.path.join(temp_dir, 'test_project'))
        
        # Write config
        config_path = write_project_config(
            project_dir=project_dir,
            latitude=40.7,
            longitude=-74.0,
            start_date='2010-01-01',
            end_date='2020-12-31',
            variables=['temperature', 'wind'],
            tmy_type='typical',
            method='zscore',
            workflow_type='comprehensive_timeseries'
        )
        
        print(f"  Config written: {config_path}")
        assert os.path.exists(config_path)
        
        # Read config
        config = read_project_config(project_dir)
        
        assert config is not None
        assert config['location']['latitude'] == 40.7
        assert config['location']['longitude'] == -74.0
        assert config['start_date'] == '2010-01-01'
        assert config['end_date'] == '2020-12-31'
        assert config['variables'] == ['temperature', 'wind']
        assert config['tmy_type'] == 'typical'
        assert config['method'] == 'zscore'
        assert config['workflow_type'] == 'comprehensive_timeseries'
        
        print("  ✓ Config read successfully")
        print(f"  Location: {config['location']['latitude']}, {config['location']['longitude']}")
        print(f"  Workflow: {config['workflow_type']}")
        print("✓ Config tests passed!\n")
        
    finally:
        shutil.rmtree(temp_dir)


def test_logging():
    """Test logging functionality."""
    print("Testing logging functionality...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Setup project directory
        project_dir = setup_project_directory(os.path.join(temp_dir, 'test_project'))
        
        # Write log messages
        log_message(project_dir, "Starting workflow")
        log_message(project_dir, "Download complete", level='SUCCESS')
        log_message(project_dir, "Warning: low memory", level='WARNING')
        log_message(project_dir, "Error occurred", level='ERROR')
        
        # Read log
        log_content = read_project_log(project_dir)
        
        assert log_content is not None
        assert "Starting workflow" in log_content
        assert "Download complete" in log_content
        assert "[SUCCESS]" in log_content
        assert "[WARNING]" in log_content
        assert "[ERROR]" in log_content
        
        print("  ✓ Log messages written")
        print("  Log content preview:")
        for line in log_content.strip().split('\n')[-4:]:
            print(f"    {line}")
        print("✓ Logging tests passed!\n")
        
    finally:
        shutil.rmtree(temp_dir)


def test_project_status():
    """Test project status checking."""
    print("Testing project status checking...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Setup project directory
        project_dir = setup_project_directory(os.path.join(temp_dir, 'test_project'))
        
        # Initial status (empty project)
        status = check_project_status(project_dir)
        
        assert status['exists'] == True
        assert status['has_config'] == False
        assert status['has_log'] == True  # Created by setup_project_directory
        assert status['has_timeseries'] == False
        assert status['has_tmy'] == False
        assert status['has_plots'] == False
        
        print("  Initial status: Empty project ✓")
        
        # Add config
        write_project_config(
            project_dir=project_dir,
            latitude=40.7,
            longitude=-74.0,
            workflow_type='test'
        )
        
        status = check_project_status(project_dir)
        assert status['has_config'] == True
        assert status['config'] is not None
        print("  After adding config ✓")
        
        # Add dummy timeseries file
        timeseries_dir = os.path.join(project_dir, 'timeseries')
        with open(os.path.join(timeseries_dir, 'test.csv'), 'w') as f:
            f.write("dummy,data\n1,2\n")
        
        status = check_project_status(project_dir)
        assert status['has_timeseries'] == True
        print("  After adding timeseries ✓")
        
        # Add dummy TMY file
        tmy_dir = os.path.join(project_dir, 'tmy')
        with open(os.path.join(tmy_dir, 'tmy.csv'), 'w') as f:
            f.write("dummy,tmy\n1,2\n")
        
        status = check_project_status(project_dir)
        assert status['has_tmy'] == True
        print("  After adding TMY ✓")
        
        # Add dummy plot file
        plots_dir = os.path.join(project_dir, 'plots')
        with open(os.path.join(plots_dir, 'plot.png'), 'w') as f:
            f.write("dummy plot\n")
        
        status = check_project_status(project_dir)
        assert status['has_plots'] == True
        print("  After adding plots ✓")
        
        print("\nFinal status:")
        print(f"  Config: {status['has_config']}")
        print(f"  Log: {status['has_log']}")
        print(f"  Timeseries: {status['has_timeseries']}")
        print(f"  TMY: {status['has_tmy']}")
        print(f"  Plots: {status['has_plots']}")
        
        print("✓ Project status tests passed!\n")
        
    finally:
        shutil.rmtree(temp_dir)


def test_nonexistent_project():
    """Test status checking for non-existent project."""
    print("Testing non-existent project status...")
    
    status = check_project_status('/path/that/does/not/exist')
    
    assert status['exists'] == False
    assert status['has_config'] == False
    assert status['has_log'] == False
    assert status['has_timeseries'] == False
    assert status['has_tmy'] == False
    assert status['has_plots'] == False
    assert status['config'] is None
    
    print("  ✓ Correctly identified non-existent project")
    print("✓ Non-existent project tests passed!\n")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("Config and Logging Tests")
    print("="*70 + "\n")
    
    test_config_write_read()
    test_logging()
    test_project_status()
    test_nonexistent_project()
    
    print("="*70)
    print("All tests passed! ✓")
    print("="*70 + "\n")
