#!/bin/bash

# Deploy script for BADGER badge
# Usage: ./deploy.sh <app_name>/<file_name>
# Example: ./deploy.sh snake/__init__.py

if [ $# -eq 0 ]; then
    echo "Usage: $0 <app_name>/<file_name>"
    echo "Example: $0 snake/__init__.py"
    exit 1
fi

SOURCE_FILE="apps/$1"
BADGER_PATH="/Volumes/BADGER"

# Check if source file exists
if [ ! -f "$SOURCE_FILE" ]; then
    echo "Error: Source file '$SOURCE_FILE' not found"
    exit 1
fi

# Check if BADGER drive is mounted
if [ ! -d "$BADGER_PATH" ]; then
    echo "Error: BADGER drive not found at $BADGER_PATH"
    echo "Please make sure the BADGER badge is connected"
    exit 1
fi

# Create target directory if it doesn't exist
TARGET_DIR="$BADGER_PATH/$(dirname "$SOURCE_FILE")"
mkdir -p "$TARGET_DIR"

# Copy the file
TARGET_FILE="$BADGER_PATH/$SOURCE_FILE"
echo "Copying $SOURCE_FILE to $TARGET_FILE..."
cp "$SOURCE_FILE" "$TARGET_FILE"

if [ $? -eq 0 ]; then
    echo "✓ File copied successfully"
    
    # Eject the drive
    echo "Ejecting BADGER drive..."
    diskutil eject "$BADGER_PATH"
    
    if [ $? -eq 0 ]; then
        echo "✓ BADGER drive ejected successfully"
    else
        echo "✗ Failed to eject BADGER drive"
        exit 1
    fi
else
    echo "✗ Failed to copy file"
    exit 1
fi
