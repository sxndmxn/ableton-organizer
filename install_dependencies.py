#!/usr/bin/env python3
"""
Dependencies Installer for Ableton Organizer
Installs required Python packages and system dependencies
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(command, description):
    """Run a command and return success status"""
    print(f"Installing: {description}")
    print(f"Command: {command}")

    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        if result.stdout.strip():
            print(f"Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr.strip() if e.stderr else 'Unknown error'}")
        return False


def check_python_version():
    """Check Python version compatibility"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print(
            f"Error: Python 3.7+ required. Current version: {version.major}.{version.minor}.{version.micro}"
        )
        return False

    print(f"Python version OK: {version.major}.{version.minor}.{version.micro}")
    return True


def install_python_packages():
    """Install required Python packages"""
    packages = [
        "lxml",  # XML parsing for Ableton files
    ]

    # Try installing with pip
    for package in packages:
        success = run_command(f"pip3 install {package}", f"Python package: {package}")
        if not success:
            print(f"Failed to install {package}")
            return False

    return True


def check_system_tools():
    """Check for required system tools"""
    tools = [
        ("rsync", "File synchronization"),
        ("sqlite3", "Database management"),
        ("md5sum", "File integrity verification"),
        ("find", "File system operations"),
        ("du", "Disk usage analysis"),
        ("df", "Disk space checking"),
        ("bash", "Shell script execution"),
    ]

    missing_tools = []

    for tool, description in tools:
        if run_command(f"which {tool}", f"Checking for {tool}"):
            print(f"✓ {tool} - {description}")
        else:
            print(f"✗ {tool} - {description} (MISSING)")
            missing_tools.append(tool)

    if missing_tools:
        print(f"\nMissing tools: {', '.join(missing_tools)}")
        print("\nInstall missing tools:")
        print("  Ubuntu/Debian: sudo apt install " + " ".join(missing_tools))
        print("  CentOS/RHEL: sudo yum install " + " ".join(missing_tools))
        print("  macOS: brew install " + " ".join(missing_tools))
        return False

    return True


def create_requirements_file():
    """Create requirements.txt file"""
    requirements = """# Ableton Organizer Requirements
# Core dependencies for project analysis and migration

# XML parsing for Ableton .als files
lxml>=4.6.0

# Optional: Enhanced file handling
# pathlib2>=2.3.0  # For Python < 3.4 (should be built-in for modern Python)

# Development dependencies (uncomment if needed)
# pytest>=6.0.0  # For testing
# black>=21.0.0   # For code formatting
# flake8>=3.8.0   # For linting
"""

    with open("requirements.txt", "w") as f:
        f.write(requirements)

    print("Created requirements.txt file")


def main():
    """Main installation process"""
    print("=" * 60)
    print("ABLETON ORGANIZER - DEPENDENCIES INSTALLER")
    print("=" * 60)

    # Check Python version
    if not check_python_version():
        sys.exit(1)

    # Check system tools
    if not check_system_tools():
        print(
            "\nSome system tools are missing. Install them and run this script again."
        )
        sys.exit(1)

    # Install Python packages
    if not install_python_packages():
        print("\nFailed to install Python packages.")
        sys.exit(1)

    # Create requirements file
    create_requirements_file()

    print("\n" + "=" * 60)
    print("INSTALLATION COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run quick test: ./quick_test.sh")
    print("2. Review README.md for usage instructions")
    print("3. Update paths in your workflow command")
    print("\nExample usage:")
    print(
        'python3 workflow.py --source "/path/to/ableton" --nas "/path/to/nas" --complete'
    )


if __name__ == "__main__":
    main()
