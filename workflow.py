#!/usr/bin/env python3
"""
Complete Ableton Project Organization Workflow
One-stop script for the entire process from analysis to migration
"""

import os
import sys
import time
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import json


class AbletonOrganizerWorkflow:
    def __init__(self, base_dir, source_dir, nas_root):
        self.base_dir = Path(base_dir)
        self.source_dir = Path(source_dir)
        self.nas_root = Path(nas_root)
        self.scripts_dir = self.base_dir / "scripts"
        self.database_path = self.base_dir / "database" / "projects.db"

        # Ensure all directories exist
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "database").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "logs").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "reports").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "temp").mkdir(parents=True, exist_ok=True)

    def log_message(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)

        # Also log to file
        log_file = self.base_dir / "logs" / "workflow.log"
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")

    def run_script(self, script_name, args, description):
        """Run a script and return success status"""
        script_path = self.scripts_dir / script_name

        if not script_path.exists():
            self.log_message(f"Script not found: {script_path}", "ERROR")
            return False

        self.log_message(f"Running: {description}")
        self.log_message(f"Command: python3 {script_path} {args}")

        try:
            result = subprocess.run(
                ["python3", str(script_path)] + args,
                capture_output=True,
                text=True,
                cwd=str(self.base_dir),
            )

            if result.returncode == 0:
                self.log_message(f"✓ {description} completed successfully")
                if result.stdout.strip():
                    self.log_message(f"Output: {result.stdout.strip()}")
                return True
            else:
                self.log_message(f"✗ {description} failed", "ERROR")
                self.log_message(f"Error: {result.stderr.strip()}", "ERROR")
                return False

        except Exception as e:
            self.log_message(f"✗ {description} failed with exception: {e}", "ERROR")
            return False

    def run_bash_script(self, script_name, args, description):
        """Run a bash script and return success status"""
        script_path = self.scripts_dir / script_name

        if not script_path.exists():
            self.log_message(f"Script not found: {script_path}", "ERROR")
            return False

        self.log_message(f"Running: {description}")
        self.log_message(f"Command: bash {script_path} {args}")

        try:
            result = subprocess.run(
                ["bash", str(script_path)] + args,
                capture_output=True,
                text=True,
                cwd=str(self.base_dir),
            )

            if result.returncode == 0:
                self.log_message(f"✓ {description} completed successfully")
                if result.stdout.strip():
                    self.log_message(f"Output: {result.stdout.strip()}")
                return True
            else:
                self.log_message(f"✗ {description} failed", "ERROR")
                self.log_message(f"Error: {result.stderr.strip()}", "ERROR")
                return False

        except Exception as e:
            self.log_message(f"✗ {description} failed with exception: {e}", "ERROR")
            return False

    def check_prerequisites(self):
        """Check if prerequisites are met"""
        self.log_message("Checking prerequisites...")

        # Check Python
        try:
            result = subprocess.run(["python3", "--version"], capture_output=True)
            if result.returncode == 0:
                self.log_message(f"Python: {result.stdout.strip()}")
            else:
                self.log_message("Python 3 not found", "ERROR")
                return False
        except FileNotFoundError:
            self.log_message("Python 3 not found", "ERROR")
            return False

        # Check source directory (may not exist during planning)
        if self.source_dir.exists():
            project_files = list(self.source_dir.rglob("*.als"))
            self.log_message(
                f"Found {len(project_files)} Ableton projects in source directory"
            )
        else:
            self.log_message(
                f"Source directory not found (expected during planning): {self.source_dir}"
            )

        # Check NAS directory (may not exist during planning)
        if self.nas_root.exists():
            self.log_message(f"NAS directory exists: {self.nas_root}")
        else:
            self.log_message(
                f"NAS directory not found (expected during planning): {self.nas_root}"
            )

        # Check SQLite
        try:
            import sqlite3

            self.log_message("SQLite available")
        except ImportError:
            self.log_message("SQLite not available", "ERROR")
            return False

        self.log_message("✓ Prerequisites check completed")
        return True

    def phase_1_analysis(self):
        """Phase 1: Project Analysis"""
        self.log_message("=" * 60)
        self.log_message("PHASE 1: PROJECT ANALYSIS")
        self.log_message("=" * 60)

        # Check if source directory exists
        if not self.source_dir.exists():
            self.log_message(f"Source directory not found: {self.source_dir}", "ERROR")
            self.log_message(
                "Please ensure your Ableton projects drive is connected and path is correct"
            )
            return False

        args = [
            "--source",
            str(self.source_dir),
            "--database",
            str(self.database_path),
            "--log",
            str(self.base_dir / "logs" / "scanner.log"),
        ]

        return self.run_script("project_scanner.py", args, "Project Analysis")

    def phase_2_classification(self):
        """Phase 2: Project Classification"""
        self.log_message("=" * 60)
        self.log_message("PHASE 2: PROJECT CLASSIFICATION")
        self.log_message("=" * 60)

        # Check if analysis was completed
        if not self.database_path.exists():
            self.log_message("Database not found - run Phase 1 first", "ERROR")
            return False

        args = [
            "--database",
            str(self.database_path),
            "--log",
            str(self.base_dir / "logs" / "classifier.log"),
        ]

        return self.run_script("project_classifier.py", args, "Project Classification")

    def phase_3_nas_structure(self):
        """Phase 3: NAS Structure Creation"""
        self.log_message("=" * 60)
        self.log_message("PHASE 3: NAS STRUCTURE CREATION")
        self.log_message("=" * 60)

        # Create NAS root if it doesn't exist (for planning phase)
        self.nas_root.mkdir(parents=True, exist_ok=True)

        args = [
            "--nas-root",
            str(self.nas_root),
            "--config",
            str(self.base_dir / "configs" / "nas_structure.json"),
            "--log",
            str(self.base_dir / "logs" / "nas_organizer.log"),
        ]

        return self.run_script(
            "nas_structure_creator.py", args, "NAS Structure Creation"
        )

    def phase_4_migration(self, category=None, limit=None, dry_run=False):
        """Phase 4: Migration"""
        self.log_message("=" * 60)
        self.log_message("PHASE 4: PROJECT MIGRATION")
        self.log_message("=" * 60)

        # Check prerequisites
        if not self.database_path.exists():
            self.log_message("Database not found - run Phases 1-2 first", "ERROR")
            return False

        if not self.nas_root.exists():
            self.log_message("NAS directory not found - run Phase 3 first", "ERROR")
            return False

        # Build migration arguments
        args = []
        if category:
            args.extend(["--category", category])
        if limit:
            args.extend(["--limit", str(limit)])
        if dry_run:
            args.append("--dry-run")

        # Set environment variables for migration script
        env = os.environ.copy()
        env["SOURCE_DIR"] = str(self.source_dir)
        env["NAS_ROOT"] = str(self.nas_root)
        env["DATABASE_PATH"] = str(self.database_path)

        return self.run_bash_script("migrate_to_nas.sh", args, "Project Migration")

    def phase_5_dashboard(self, watch=False, refresh_interval=30):
        """Phase 5: Dashboard and Reporting"""
        self.log_message("=" * 60)
        self.log_message("PHASE 5: DASHBOARD AND REPORTING")
        self.log_message("=" * 60)

        args = ["--database", str(self.database_path)]
        if watch:
            args.extend(["--watch", "--refresh", str(refresh_interval)])

        return self.run_script("migration_dashboard.py", args, "Migration Dashboard")

    def run_complete_workflow(self, category=None, limit=None, dry_run=False):
        """Run the complete workflow"""
        self.log_message("Starting complete Ableton organization workflow")
        self.log_message(f"Source: {self.source_dir}")
        self.log_message(f"NAS: {self.nas_root}")
        self.log_message(f"Base: {self.base_dir}")

        # Check prerequisites
        if not self.check_prerequisites():
            return False

        # Phase 1: Analysis
        if not self.phase_1_analysis():
            return False

        # Phase 2: Classification
        if not self.phase_2_classification():
            return False

        # Phase 3: NAS Structure
        if not self.phase_3_nas_structure():
            return False

        # Phase 4: Migration (optional)
        if category is not None or limit is not None or dry_run:
            if not self.phase_4_migration(category, limit, dry_run):
                return False

        # Phase 5: Dashboard
        if not self.phase_5_dashboard():
            return False

        self.log_message("=" * 60)
        self.log_message("WORKFLOW COMPLETED SUCCESSFULLY")
        self.log_message("=" * 60)
        return True

    def generate_setup_instructions(self):
        """Generate setup instructions file"""
        instructions = f"""
ABLETON PROJECT ORGANIZER - SETUP INSTRUCTIONS
===============================================
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

REQUIRED SETUP
--------------
1. Connect your Ableton projects drive
2. Update the paths below if needed
3. Run the workflow script

CURRENT CONFIGURATION
---------------------
Source Directory: {self.source_dir}
NAS Directory: {self.nas_root}
Organizer Base: {self.base_dir}

QUICK START COMMANDS
-------------------
# Test prerequisites
python3 workflow.py --test-prereqs

# Run complete workflow
python3 workflow.py --complete

# Run specific phases
python3 workflow.py --phase 1    # Analysis only
python3 workflow.py --phase 2    # Classification only
python3 workflow.py --phase 3    # NAS structure only
python3 workflow.py --phase 4    # Migration only
python3 workflow.py --phase 5    # Dashboard only

# Migration options
python3 workflow.py --phase 4 --category production_ready --limit 10
python3 workflow.py --phase 4 --dry-run

# Watch dashboard
python3 workflow.py --phase 5 --watch

DIRECTORY STRUCTURE EXPECTED
----------------------------
Your Ableton drive should contain:
/path/to/your/drive/
├── Ableton/
│   ├── Projects/           (Your .als files)
│   ├── Sample Packs/       (Will be left alone)
│   └── Soulseek/          (Your music library)

NAS STRUCTURE WILL BE CREATED
------------------------------
{self.nas_root}/
├── 01_PRODUCTION_READY/
├── 02_ACTIVE_PRODUCTION/
├── 03_FINISHED_EXPERIMENTS/
├── 04_DEVELOPMENT/
├── 05_COMPLEX_SKETCHES/
├── 06_SIMPLE_IDEAS/
├── 07_ARCHIVED_SAMPLES/
├── 08_EXPORTS_FOR_JELLYFIN/
├── 09_COLLABORATIONS/
├── 10_ARCHIVE/
├── Soulseek_Organized/
├── Sample_Packs_Organized/
└── 00_MAINTENANCE/

TROUBLESHOOTING
---------------
1. If source directory not found:
   - Connect your external drive
   - Check the path in configuration
   - Ensure drive is mounted

2. If NAS directory issues:
   - Create the NAS root directory first
   - Check permissions
   - Ensure sufficient disk space

3. If database errors:
   - Delete database directory and restart
   - Check Python sqlite3 module

4. If migration fails:
   - Run with --dry-run first
   - Check logs in logs/ directory
   - Verify file permissions

NEXT STEPS
----------
1. Review this file
2. Connect your drives
3. Update paths if needed
4. Run: python3 workflow.py --test-prereqs
5. Run: python3 workflow.py --complete

For detailed help: python3 workflow.py --help
"""

        instructions_path = self.base_dir / "SETUP_INSTRUCTIONS.txt"
        with open(instructions_path, "w") as f:
            f.write(instructions)

        self.log_message(f"Setup instructions saved to: {instructions_path}")
        return instructions_path


def main():
    parser = argparse.ArgumentParser(
        description="Complete Ableton project organization workflow"
    )

    # Path configuration
    parser.add_argument(
        "--source", required=True, help="Source directory with Ableton projects"
    )
    parser.add_argument(
        "--nas", required=True, help="NAS root directory for organized files"
    )
    parser.add_argument(
        "--base",
        default="~/ableton-organizer",
        help="Organizer base directory (default: ~/ableton-organizer)",
    )

    # Workflow control
    parser.add_argument("--complete", action="store_true", help="Run complete workflow")
    parser.add_argument(
        "--phase", type=int, choices=[1, 2, 3, 4, 5], help="Run specific phase only"
    )
    parser.add_argument(
        "--test-prereqs", action="store_true", help="Test prerequisites only"
    )

    # Migration options
    parser.add_argument("--category", help="Migrate specific category only")
    parser.add_argument("--limit", type=int, help="Limit migration to N projects")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Migration dry run (no actual file moves)",
    )

    # Dashboard options
    parser.add_argument(
        "--watch", action="store_true", help="Run dashboard in watch mode"
    )
    parser.add_argument(
        "--refresh", type=int, default=30, help="Dashboard refresh interval (seconds)"
    )

    args = parser.parse_args()

    # Expand paths
    base_dir = Path(args.base).expanduser()
    source_dir = Path(args.source).expanduser()
    nas_dir = Path(args.nas).expanduser()

    # Create workflow instance
    workflow = AbletonOrganizerWorkflow(base_dir, source_dir, nas_dir)

    # Generate setup instructions
    workflow.generate_setup_instructions()

    # Execute requested action
    if args.test_prereqs:
        success = workflow.check_prerequisites()
        sys.exit(0 if success else 1)

    elif args.complete:
        success = workflow.run_complete_workflow(
            args.category, args.limit, args.dry_run
        )
        sys.exit(0 if success else 1)

    elif args.phase:
        phase_methods = {
            1: workflow.phase_1_analysis,
            2: workflow.phase_2_classification,
            3: workflow.phase_3_nas_structure,
            4: lambda: workflow.phase_4_migration(
                args.category, args.limit, args.dry_run
            ),
            5: lambda: workflow.phase_5_dashboard(args.watch, args.refresh),
        }

        success = phase_methods[args.phase]()
        sys.exit(0 if success else 1)

    else:
        print("No action specified. Use --complete, --phase N, or --test-prereqs")
        print("See setup instructions for detailed usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
