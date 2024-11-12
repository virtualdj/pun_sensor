#!/usr/bin/env bash

# Check for git and python3
for command in git python3
do
    if ! command -v "$command" &> /dev/null
    then
        echo "$command is not found in your PATH."
        exit 1
    fi
done

# Get the latest tag name
latest_tag=$(git describe --tags --abbrev=0)
echo "Latest tag (might be wrong): $latest_tag"

# Patch the manifest
python3 .github/workflows/update_manifest.py --version $latest_tag
