#!/bin/bash
# Quick setup script for weather-file-builder

echo "Weather File Builder - Setup"
echo "=============================="
echo ""

# Check if in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Run this script from the project root directory"
    exit 1
fi

echo "1. Installing package in development mode..."
pip install -e .

if [ $? -ne 0 ]; then
    echo "   Error: Installation failed"
    exit 1
fi

echo "   ✓ Package installed"
echo ""

echo "2. Checking CDS API configuration..."
if [ -f ~/.cdsapirc ]; then
    echo "   ✓ CDS API config found: ~/.cdsapirc"
else
    echo "   ⚠ CDS API config not found!"
    echo "   "
    echo "   Please create ~/.cdsapirc with:"
    echo "   "
    echo "   url: https://cds.climate.copernicus.eu/api"
    echo "   key: YOUR_UID:YOUR_API_KEY"
    echo "   "
    echo "   Get your API key from: https://cds.climate.copernicus.eu/"
    echo "   "
fi

echo ""
echo "3. Testing installation..."
python -c "import weather_file_builder; print(f'   ✓ Version {weather_file_builder.__version__}')"

if [ $? -ne 0 ]; then
    echo "   Error: Import test failed"
    exit 1
fi

echo ""
echo "4. Checking CLI..."
weather-file-builder --help > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "   ✓ CLI command available: weather-file-builder"
else
    echo "   ⚠ CLI not available, try: python -m weather_file_builder.cli"
fi

echo ""
echo "=============================="
echo "Setup complete!"
echo ""
echo "Quick test (requires CDS API key):"
echo "  weather-file-builder download --lat 40.7 --lon -74.0 --years 2023 --output test.csv"
echo ""
echo "For more information:"
echo "  - Read README.md for usage examples"
echo "  - Read PROJECT_GUIDE.md for architecture details"
echo "  - Check examples/basic_usage.py for code examples"
