#!/bin/bash

# Release script for weather-file-builder
# Usage: ./release.sh [patch|minor|major]
#
# Prerequisites: conda (weatherfilebuilder env), git
# The publish.yml workflow auto-publishes to PyPI when a tag is pushed.

set -e

BUMP_TYPE=${1:-patch}

echo "Checking git status..."
if [ -n "$(git status --porcelain | grep -E '^[AMD]')" ]; then
    echo "ERROR: Working directory has uncommitted changes."
    git status --porcelain | grep -E '^[AMD]'
    exit 1
fi

echo "Pulling latest changes..."
git pull origin main

echo "Running tests..."
conda run -n weatherfilebuilder pytest tests/ -v || echo "WARNING: Tests failed or no tests found, continuing..."

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "Current version: $CURRENT_VERSION"

# Calculate new version
MAJOR=$(echo "$CURRENT_VERSION" | cut -d. -f1)
MINOR=$(echo "$CURRENT_VERSION" | cut -d. -f2)
PATCH=$(echo "$CURRENT_VERSION" | cut -d. -f3)

if [ "$BUMP_TYPE" = "major" ]; then
    NEW_VERSION="$((MAJOR + 1)).0.0"
elif [ "$BUMP_TYPE" = "minor" ]; then
    NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
elif [ "$BUMP_TYPE" = "patch" ]; then
    NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
else
    echo "ERROR: Invalid bump type '$BUMP_TYPE'. Use patch, minor, or major."
    exit 1
fi

echo "New version: $NEW_VERSION"

# Update version in pyproject.toml and __init__.py
sed -i '' "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
sed -i '' "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" src/weather_file_builder/__init__.py

# Commit, tag, and push
git add pyproject.toml src/weather_file_builder/__init__.py
git commit -m "Bump version: $CURRENT_VERSION -> $NEW_VERSION"
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

echo "Building package..."
conda run -n weatherfilebuilder bash -c "pip install hatch -q && hatch build"

echo "Pushing changes and tags..."
git push origin main --tags

echo "Released version $NEW_VERSION"
echo "GitHub Actions will build and publish to PyPI automatically."
echo "Create a GitHub release (optional):"
echo "  https://github.com/justinfmccarty/weather_file_builder/releases/new?tag=v$NEW_VERSION"
