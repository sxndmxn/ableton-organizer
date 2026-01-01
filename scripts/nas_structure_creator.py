#!/usr/bin/env python3
"""
NAS Structure Creator
Creates the production-first directory structure for organized Ableton projects
"""

import os
from pathlib import Path
import argparse
import json
from datetime import datetime


class NASOrganizer:
    def __init__(self, nas_root, config_file=None, log_path=None):
        self.nas_root = Path(nas_root)
        self.config_file = config_file or "configs/nas_structure.json"
        self.log_path = log_path or "logs/nas_organizer.log"
        self.structure_config = self.load_structure_config()
        self.ensure_log_directory()

    def ensure_log_directory(self):
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def log_message(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        print(log_entry.strip())

        if self.log_path:
            with open(self.log_path, "a") as f:
                f.write(log_entry)

    def load_structure_config(self):
        """Load NAS structure configuration"""
        default_config = {
            "production_first_structure": {
                "01_PRODUCTION_READY": {
                    "description": "Complete projects ready for release, mixing, or mastering",
                    "subdirs": [
                        "by_genre",
                        "by_tempo",
                        "by_year",
                        "ready_for_jellyfin",
                    ],
                    "priority": 1,
                },
                "02_ACTIVE_PRODUCTION": {
                    "description": "High-quality works in progress with substantial development",
                    "subdirs": ["current_projects", "on_hold", "collaborations"],
                    "priority": 2,
                },
                "03_FINISHED_EXPERIMENTS": {
                    "description": "Complete but experimental or niche projects",
                    "subdirs": [
                        "sound_design",
                        "atmospheric",
                        "techno_experiments",
                        "ambient_works",
                    ],
                    "priority": 3,
                },
                "04_DEVELOPMENT": {
                    "description": "Works in progress with moderate complexity",
                    "subdirs": ["arrangements", "productions", "developments"],
                    "priority": 4,
                },
                "05_COMPLEX_SKETCHES": {
                    "description": "Complex ideas that need development but show promise",
                    "subdirs": [
                        "melodies",
                        "rhythms",
                        "harmonic_ideas",
                        "texture_experiments",
                    ],
                    "priority": 5,
                },
                "06_SIMPLE_IDEAS": {
                    "description": "Basic sketches, starting points, and quick ideas",
                    "subdirs": ["loops", "one_shots", "basic_sketches", "inspiration"],
                    "priority": 6,
                },
                "07_ARCHIVED_SAMPLES": {
                    "description": "Organized sample library used in projects",
                    "subdirs": [
                        "by_genre",
                        "by_instrument",
                        "by_tempo",
                        "by_mood",
                        "personal_recordings",
                    ],
                    "priority": 7,
                },
                "08_EXPORTS_FOR_JELLYFIN": {
                    "description": "Finished exports organized for media server",
                    "subdirs": [
                        "albums",
                        "singles",
                        "compilations",
                        "dj_sets",
                        "soundtracks",
                    ],
                    "priority": 8,
                },
                "09_COLLABORATIONS": {
                    "description": "Projects involving other artists or clients",
                    "subdirs": [
                        "remixes",
                        "features",
                        "commissioned_work",
                        "shared_projects",
                    ],
                    "priority": 9,
                },
                "10_ARCHIVE": {
                    "description": "Old projects, backup copies, and legacy work",
                    "subdirs": [
                        "pre_2020",
                        "unreleased",
                        "learning_projects",
                        "backup_versions",
                    ],
                    "priority": 10,
                },
            },
            "music_integration_structure": {
                "Soulseek_Organized": {
                    "description": "Organized music library from Soulseek downloads",
                    "subdirs": [
                        "by_genre/electronic",
                        "by_genre/ambient",
                        "by_genre/experimental",
                        "by_genre/hip_hop",
                        "by_genre/classical",
                        "by_tempo/60-80_bpm",
                        "by_tempo/80-120_bpm",
                        "by_tempo/120-140_bpm",
                        "by_tempo/140+_bpm",
                        "for_resampling/vocals",
                        "for_resampling/drums",
                        "for_resampling/melodies",
                        "for_resampling/atmospheres",
                        "favorites/production_ready",
                        "favorites/reference_tracks",
                    ],
                },
                "Sample_Packs_Organized": {
                    "description": "Organized commercial sample packs",
                    "subdirs": [
                        "drums/kicks",
                        "drums/snares",
                        "drums/hats",
                        "drums/percussion",
                        "basics/synths",
                        "basics/pads",
                        "basics_leads",
                        "vocals/chopped",
                        "vocals_phrases",
                        "effects/risers",
                        "effects/impacts",
                        "loops/drum_loops",
                        "loops/melodic_loops",
                        "ambient/textures",
                    ],
                },
            },
        }

        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    user_config = json.load(f)
                    # Merge with default config
                    for key, value in user_config.items():
                        if key in default_config:
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
            except (json.JSONDecodeError, IOError) as e:
                self.log_message(
                    f"Warning: Could not load config file {config_path}: {e}"
                )
                self.log_message("Using default configuration")
        else:
            # Save default config for future editing
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(default_config, f, indent=2)
            self.log_message(f"Created default config file: {config_path}")

        return default_config

    def create_nas_structure(self):
        """Create the complete NAS directory structure"""
        self.log_message(f"Creating NAS structure in: {self.nas_root}")

        if not self.nas_root.exists():
            self.log_message(f"Creating NAS root directory: {self.nas_root}")
            self.nas_root.mkdir(parents=True, exist_ok=True)

        # Create production-first structure
        production_dirs = self.structure_config.get("production_first_structure", {})

        for dir_name, config in production_dirs.items():
            self.create_category_directory(dir_name, config)

        # Create music integration structure
        music_dirs = self.structure_config.get("music_integration_structure", {})

        for dir_name, config in music_dirs.items():
            self.create_category_directory(dir_name, config)

        # Create utility directories
        self.create_utility_directories()

        # Create documentation files
        self.create_documentation()

        self.log_message("NAS structure creation complete")
        self.generate_structure_report()

    def create_category_directory(self, dir_name, config):
        """Create a category directory with its subdirectories"""
        category_path = self.nas_root / dir_name

        if category_path.exists():
            self.log_message(f"Directory already exists: {category_path}")
        else:
            category_path.mkdir(parents=True, exist_ok=True)
            self.log_message(f"Created: {category_path}")

        # Create subdirectories
        subdirs = config.get("subdirs", [])
        for subdir in subdirs:
            subdir_path = category_path / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
            self.log_message(f"  Created: {subdir_path}")

        # Create README file for category
        readme_content = f"""# {dir_name.replace("_", " ").upper()}

{config.get("description", "No description available")}

## Subdirectories
"""
        for subdir in subdirs:
            readme_content += f"- `{subdir}`: Organized content for this subcategory\n"

        readme_content += f"""
## Priority
This directory has priority level {config.get("priority", "N/A")} for migration.

## Organization Guidelines
- Keep file names consistent and descriptive
- Follow the established naming conventions
- Update metadata when adding new content
- Maintain clean folder structure

Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        readme_path = category_path / "README.md"
        if not readme_path.exists():
            with open(readme_path, "w") as f:
                f.write(readme_content)
            self.log_message(f"  Created: {readme_path}")

    def create_utility_directories(self):
        """Create utility and maintenance directories"""
        utility_dirs = [
            "00_MAINTENANCE",
            "00_MAINTENANCE/backups",
            "00_MAINTENANCE/logs",
            "00_MAINTENANCE/temp",
            "00_MAINTENANCE/scripts",
            "00_TEMP_INGEST",
            "00_UNCATEGORIZED",
            "00_CORRUPTED_FILES",
        ]

        for util_dir in utility_dirs:
            util_path = self.nas_root / util_dir
            util_path.mkdir(parents=True, exist_ok=True)
            self.log_message(f"Created utility directory: {util_path}")

        # Create maintenance scripts
        self.create_maintenance_scripts()

    def create_maintenance_scripts(self):
        """Create basic maintenance scripts"""
        scripts_dir = self.nas_root / "00_MAINTENANCE/scripts"

        # Create backup script template
        backup_script = """#!/bin/bash
# Backup script for Ableton projects
# Customize paths and schedules as needed

SOURCE_DIR="/nas/ableton-projects"
BACKUP_DIR="/backup/ableton-projects"
DATE=$(date +%Y%m%d_%H%M%S)

echo "Starting backup: $DATE"

# Create backup directory
mkdir -p "$BACKUP_DIR/$DATE"

# Perform incremental backup using rsync
rsync -av --progress --delete \\
    --exclude="00_TEMP_INGEST" \\
    --exclude="00_MAINTENANCE/logs" \\
    "$SOURCE_DIR/" "$BACKUP_DIR/$DATE/"

echo "Backup completed: $DATE"
echo "Size: $(du -sh "$BACKUP_DIR/$DATE" | cut -f1)"
"""

        with open(scripts_dir / "backup.sh", "w") as f:
            f.write(backup_script)

        # Create cleanup script template
        cleanup_script = """#!/bin/bash
# Cleanup script for temporary files and maintenance

TEMP_DIR="/nas/ableton-projects/00_TEMP_INGEST"
LOG_DIR="/nas/ableton-projects/00_MAINTENANCE/logs"

echo "Starting cleanup..."

# Clean temp files older than 7 days
find "$TEMP_DIR" -type f -mtime +7 -delete 2>/dev/null
find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null

echo "Cleanup completed"
"""

        with open(scripts_dir / "cleanup.sh", "w") as f:
            f.write(cleanup_script)

        # Make scripts executable
        (scripts_dir / "backup.sh").chmod(0o755)
        (scripts_dir / "cleanup.sh").chmod(0o755)

    def create_documentation(self):
        """Create main documentation files"""
        # Main README
        main_readme = f"""# Ableton Projects NAS

Production-first organization system for Ableton Live projects and music library.

## Structure Overview

This directory is organized using a production-first priority system:

### Production Categories (Priority 1-6)
1. **01_PRODUCTION_READY** - Complete projects ready for release
2. **02_ACTIVE_PRODUCTION** - High-quality works in progress
3. **03_FINISHED_EXPERIMENTS** - Complete experimental works
4. **04_DEVELOPMENT** - Moderate complexity works in progress
5. **05_COMPLEX_SKETCHES** - Complex ideas needing development
6. **06_SIMPLE_IDEAS** - Basic sketches and inspiration

### Supporting Categories (Priority 7-10)
7. **07_ARCHIVED_SAMPLES** - Organized sample library
8. **08_EXPORTS_FOR_JELLYFIN** - Media server ready exports
9. **09_COLLABORATIONS** - Collaborative and client work
10. **10_ARCHIVE** - Legacy and backup projects

### Music Integration
- **Soulseek_Organized** - Organized music downloads
- **Sample_Packs_Organized** - Commercial sample libraries

### Maintenance
- **00_MAINTENANCE** - Backups, logs, and scripts
- **00_TEMP_INGEST** - Temporary staging area
- **00_UNCATEGORIZED** - Files needing classification
- **00_CORRUPTED_FILES** - Damaged files for recovery

## Migration Priority

Projects are migrated in this order:
1. Production Ready (highest priority)
2. Active Production
3. Finished Experiments
4. Development
5. Complex Sketches
6. Simple Ideas (lowest priority)

## Naming Conventions

### Projects
- Use descriptive names
- Include date/version if helpful
- Avoid special characters
- Example: "Deep_House_Journey_2025_03_15"

### Exports
- Format: "Artist_Name_-_Track_Name_-_Mix_Version"
- Include metadata and artwork
- High-quality formats for archival
- Compressed formats for distribution

### Samples
- Organize by type, genre, tempo
- Clear, descriptive naming
- Include key and BPM where applicable

## Automation

This NAS structure is designed to work with automated migration scripts:
- Projects are categorized by complexity and completion
- Migration follows priority queue
- Verification ensures data integrity
- Rollback capability for safety

Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        with open(self.nas_root / "README.md", "w") as f:
            f.write(main_readme)

        self.log_message("Created main README documentation")

    def generate_structure_report(self):
        """Generate a report of the created structure"""
        created_dirs = []
        for item in self.nas_root.rglob("*"):
            if item.is_dir():
                created_dirs.append(str(item.relative_to(self.nas_root)))

        created_dirs = sorted(set(created_dirs))

        report = f"""NAS STRUCTURE CREATION REPORT
===============================
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
NAS Root: {self.nas_root}

TOTAL DIRECTORIES CREATED: {len(created_dirs)}

DIRECTORY STRUCTURE
------------------
"""

        for directory in created_dirs:
            report += f"{directory}\n"

        report += f"""

CONFIGURATION USED
------------------
Structure configuration loaded from: {self.config_file}

NEXT STEPS
----------
1. Verify all directories were created correctly
2. Review and customize category descriptions
3. Test migration scripts with sample data
4. Set appropriate permissions for your system
5. Configure backup schedules

MAINTENANCE REMINDERS
--------------------
- Regular backups using scripts in 00_MAINTENANCE/scripts/
- Monitor storage usage and plan for expansion
- Review and clean up 00_TEMP_INGEST periodically
- Update documentation as structure evolves
"""

        report_path = Path("reports/nas_structure_report.txt")
        with open(report_path, "w") as f:
            f.write(report)

        self.log_message(f"Structure report saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Create NAS directory structure for Ableton projects"
    )
    parser.add_argument(
        "--nas-root", required=True, help="Root directory for NAS structure"
    )
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--log", help="Log file path")

    args = parser.parse_args()

    organizer = NASOrganizer(args.nas_root, args.config, args.log)
    organizer.create_nas_structure()


if __name__ == "__main__":
    main()
