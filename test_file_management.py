#!/usr/bin/env python3
"""
Test file management utilities.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from weather_file_builder.utils import generate_filename, get_output_path, setup_project_directory


def test_generate_filename():
    """Test filename generation."""
    print("Testing filename generation...")
    
    # Test timeseries filename
    fn1 = generate_filename(
        'timeseries', 40.7, -74.0, 
        start_date='2020-01-01', end_date='2020-12-31'
    )
    print(f"  Timeseries: {fn1}")
    assert fn1 == 'timeseries_2020-01-01_2020-12-31_40.70_-74.00.csv'
    
    # Test TMY filename
    fn2 = generate_filename(
        'tmy', 40.7, -74.0,
        years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
    )
    print(f"  TMY: {fn2}")
    assert fn2 == 'tmy_2010-2020_40.70_-74.00.csv'
    
    # Test with variables
    fn3 = generate_filename(
        'timeseries', 40.7, -74.0,
        start_date='2020-01-01', end_date='2020-12-31',
        variables=['temperature', 'wind']
    )
    print(f"  With variables: {fn3}")
    assert 'temperature' in fn3 and 'wind' in fn3
    
    print("✓ Filename generation tests passed!\n")


def test_project_directory():
    """Test project directory setup."""
    print("Testing project directory setup...")
    
    import tempfile
    import shutil
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Setup project directory
        project_dir = setup_project_directory(os.path.join(temp_dir, 'test_project'))
        
        # Check that directories were created
        assert os.path.exists(project_dir)
        assert os.path.exists(os.path.join(project_dir, 'timeseries'))
        assert os.path.exists(os.path.join(project_dir, 'tmy'))
        assert os.path.exists(os.path.join(project_dir, 'plots'))
        
        print(f"  Created: {project_dir}")
        print(f"  Subdirectories: timeseries, tmy, plots")
        print("✓ Project directory tests passed!\n")
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir)


def test_output_paths():
    """Test output path generation."""
    print("Testing output path generation...")
    
    project_dir = '/path/to/project'
    
    # Test timeseries path
    path1 = get_output_path(
        project_dir=project_dir,
        data_type='timeseries',
        latitude=40.7,
        longitude=-74.0,
        start_date='2020-01-01',
        end_date='2020-12-31'
    )
    print(f"  Timeseries: {path1}")
    assert path1.startswith('/path/to/project/timeseries/')
    assert path1.endswith('.csv')
    
    # Test TMY path
    path2 = get_output_path(
        project_dir=project_dir,
        data_type='tmy',
        latitude=40.7,
        longitude=-74.0,
        years=[2010, 2020]
    )
    print(f"  TMY: {path2}")
    assert path2.startswith('/path/to/project/tmy/')
    assert 'tmy' in path2
    
    # Test plot path
    path3 = get_output_path(
        project_dir=project_dir,
        data_type='plot',
        latitude=40.7,
        longitude=-74.0,
        filename='custom_plot.png'
    )
    print(f"  Plot: {path3}")
    assert path3.startswith('/path/to/project/plots/')
    assert path3.endswith('custom_plot.png')
    
    print("✓ Output path tests passed!\n")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("File Management Tests")
    print("="*70 + "\n")
    
    test_generate_filename()
    test_project_directory()
    test_output_paths()
    
    print("="*70)
    print("All tests passed! ✓")
    print("="*70 + "\n")
