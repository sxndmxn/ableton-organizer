#!/bin/bash
# Install missing system dependencies
# Run this script with sudo if needed

echo "Checking for missing system tools..."

# Check if rsync is installed
if ! command -v rsync &> /dev/null; then
    echo "rsync is not installed. Installing..."
    
    # Detect package manager and install
    if command -v pacman &> /dev/null; then
        echo "Using pacman (Arch Linux)..."
        pacman -S rsync
    elif command -v apt-get &> /dev/null; then
        echo "Using apt (Debian/Ubuntu)..."
        apt-get update && apt-get install -y rsync
    elif command -v yum &> /dev/null; then
        echo "Using yum (CentOS/RHEL)..."
        yum install -y rsync
    elif command -v brew &> /dev/null; then
        echo "Using Homebrew (macOS)..."
        brew install rsync
    else
        echo "Cannot detect package manager. Please install rsync manually."
        echo "  Arch Linux: sudo pacman -S rsync"
        echo "  Ubuntu/Debian: sudo apt-get install rsync"
        echo "  CentOS/RHEL: sudo yum install rsync"
        echo "  macOS: brew install rsync"
        exit 1
    fi
else
    echo "rsync is already installed"
fi

echo "Dependency installation complete!"