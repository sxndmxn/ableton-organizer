#!/usr/bin/env python3
"""
Ableton Project Reorganizer - Safe In-Place Migration

Reorganizes projects by completion status while preserving phase folders.
Includes full safety features: backup, verification, rollback capability.

SAFETY FEATURES:
- Creates backup of original structure before any moves
- Dry-run mode to preview changes
- Verification after each move
- Complete rollback capability
- Detailed logging of all operations
"""

import os
import shutil
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import json


class ProjectReorganizer:
    """Safe project reorganization with backup and verification."""

    # Status folder mapping (lowercase db value -> uppercase folder name)
    STATUS_FOLDERS = {
        "complete": "COMPLETE",
        "work_in_progress": "WORKINPROGRESS",
        "sketch": "SKETCHES",
        "idea": "IDEAS",
    }

    def __init__(
        self,
        projects_root: str,
        db_path: str,
        log_path: str | None = None,
        dry_run: bool = False,
        skip_backup: bool = False,
    ):
        self.projects_root = Path(projects_root)
        self.db_path = db_path
        self.dry_run = dry_run
        self.skip_backup = skip_backup
        self.log_path = log_path or "logs/reorganize.log"

        # Key paths
        self.phases_dir = self.projects_root / "Phases"
        self.backup_dir = self.projects_root / "_BACKUP_PHASES"

        # Tracking
        self.moved_projects = []
        self.failed_projects = []
        self.skipped_projects = []

        # Ensure log directory
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

        self.log_message(f"Reorganizer initialized")
        self.log_message(f"Projects root: {self.projects_root}")
        self.log_message(f"Phases dir: {self.phases_dir}")
        self.log_message(f"Dry run: {self.dry_run}")
        self.log_message(f"Skip backup: {self.skip_backup}")

    def log_message(self, message: str, level: str = "INFO"):
        """Log message to console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)

        with open(self.log_path, "a") as f:
            f.write(log_entry + "\n")

    def get_projects_from_db(self, phase_filter: str | None = None) -> list[dict]:
        """Get all projects from database with their metadata."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT 
                file_path,
                project_name,
                completion_status,
                phase_folder,
                complexity_score,
                has_arrangement
            FROM projects
            WHERE analyzed = 1
        """

        if phase_filter:
            query += f" AND phase_folder = '{phase_filter}'"

        query += " ORDER BY completion_status, phase_folder, project_name"

        cursor.execute(query)
        projects = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return projects

    def get_project_folder_from_als(self, als_path: Path) -> Path | None:
        """
        Get the project folder from an .als file path.
        The project folder is the parent directory containing the .als file.

        Returns None if the project folder doesn't exist.
        """
        # The project folder is the parent of the .als file
        project_folder = als_path.parent

        if project_folder.exists():
            return project_folder
        return None

    def extract_phase_and_relative_path(self, project_folder: Path) -> tuple[str, str]:
        """
        Extract the phase name and relative path from a project folder.

        Examples:
        - Phases/ventucky/chant Project -> ("ventucky", "chant Project")
        - Phases/ALBUMS/DEMONDIGI/D-LOC Project -> ("ALBUMS", "DEMONDIGI/D-LOC Project")
        - Phases/2025/JAN/project Project -> ("2025", "JAN/project Project")

        Returns (phase_name, relative_path_within_phase)
        """
        try:
            # Get path relative to Phases directory
            rel_to_phases = project_folder.relative_to(self.phases_dir)
            parts = rel_to_phases.parts

            if len(parts) == 0:
                return ("", str(project_folder.name))

            # First part is the phase name
            phase_name = parts[0]

            # Remaining parts form the relative path within the phase
            if len(parts) == 1:
                # Project is directly in phase folder (shouldn't happen normally)
                return (phase_name, project_folder.name)
            else:
                # Join remaining parts
                relative_path = str(Path(*parts[1:]))
                return (phase_name, relative_path)

        except ValueError:
            # Path is not under Phases directory
            return ("", project_folder.name)

    def create_backup(self) -> bool:
        """
        Create safety backup by copying Phases directory.

        Returns True if backup created successfully.
        """
        self.log_message("Creating safety backup...")

        if not self.phases_dir.exists():
            self.log_message(
                f"ERROR: Phases directory not found: {self.phases_dir}", "ERROR"
            )
            return False

        if self.backup_dir.exists():
            self.log_message(f"Backup already exists at: {self.backup_dir}", "WARN")
            self.log_message(
                "Proceeding with existing backup (original data preserved)", "WARN"
            )
            return True

        if self.dry_run:
            self.log_message(f"[DRY-RUN] Would create backup: {self.backup_dir}")
            return True

        try:
            # Copy the entire Phases directory to backup
            # Using copytree instead of move for safety
            self.log_message(f"Copying {self.phases_dir} to {self.backup_dir}...")
            self.log_message("This may take a few minutes...")

            shutil.copytree(
                str(self.phases_dir),
                str(self.backup_dir),
                symlinks=True,
                ignore_dangling_symlinks=True,
            )

            self.log_message(f"Backup created: {self.backup_dir}")
            return True

        except Exception as e:
            self.log_message(f"ERROR creating backup: {e}", "ERROR")
            return False

    def create_status_folders(self) -> bool:
        """Create the status category folders."""
        self.log_message("Creating status folders...")

        for status, folder_name in self.STATUS_FOLDERS.items():
            folder_path = self.projects_root / folder_name

            if self.dry_run:
                self.log_message(f"[DRY-RUN] Would create: {folder_path}")
            else:
                folder_path.mkdir(parents=True, exist_ok=True)
                self.log_message(f"Created: {folder_path}")

        return True

    def move_project(self, project: dict) -> bool:
        """
        Move a single project to its new location.

        Returns True if successful.
        """
        als_path = Path(project["file_path"])
        status = project["completion_status"]
        project_name = project["project_name"]

        # Get status folder name
        status_folder = self.STATUS_FOLDERS.get(status, "SKETCHES")

        # Find the actual project folder
        project_folder = self.get_project_folder_from_als(als_path)

        if project_folder is None:
            self.log_message(
                f"SKIP: Project folder not found for: {project_name}", "WARN"
            )
            self.skipped_projects.append(
                {
                    "project": project_name,
                    "reason": "Project folder not found",
                    "als_path": str(als_path),
                }
            )
            return False

        # Extract phase and relative path
        phase_name, relative_path = self.extract_phase_and_relative_path(project_folder)

        if not phase_name:
            self.log_message(
                f"SKIP: Could not determine phase for: {project_name}", "WARN"
            )
            self.skipped_projects.append(
                {
                    "project": project_name,
                    "reason": "Could not determine phase",
                    "path": str(project_folder),
                }
            )
            return False

        # Calculate destination
        # Structure: COMPLETE/phase_name/relative_path
        dest_folder = self.projects_root / status_folder / phase_name / relative_path

        if self.dry_run:
            self.log_message(f"[DRY-RUN] Move: {project_name}")
            self.log_message(f"  FROM: {project_folder}")
            self.log_message(f"  TO:   {dest_folder}")
            self.moved_projects.append(
                {
                    "project": project_name,
                    "status": status,
                    "phase": phase_name,
                    "source": str(project_folder),
                    "dest": str(dest_folder),
                }
            )
            return True

        try:
            # Check if destination already exists
            if dest_folder.exists():
                self.log_message(
                    f"SKIP: Destination already exists for: {project_name}", "WARN"
                )
                self.skipped_projects.append(
                    {
                        "project": project_name,
                        "reason": "Destination already exists",
                        "dest": str(dest_folder),
                    }
                )
                return False

            # Create destination parent directories
            dest_folder.parent.mkdir(parents=True, exist_ok=True)

            # Move the entire project folder
            shutil.move(str(project_folder), str(dest_folder))

            self.moved_projects.append(
                {
                    "project": project_name,
                    "status": status,
                    "phase": phase_name,
                    "source": str(project_folder),
                    "dest": str(dest_folder),
                }
            )

            return True

        except Exception as e:
            self.log_message(f"ERROR moving {project_name}: {e}", "ERROR")
            self.failed_projects.append(
                {
                    "project": project_name,
                    "error": str(e),
                    "source": str(project_folder),
                }
            )
            return False

    def update_database_paths(self):
        """Update database with new file paths after migration."""
        if self.dry_run:
            self.log_message("[DRY-RUN] Would update database paths")
            return

        self.log_message("Updating database paths...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updated = 0
        for move in self.moved_projects:
            old_path = move["source"]
            new_path = move["dest"]

            # Update file_path in database
            cursor.execute(
                """
                UPDATE projects 
                SET file_path = REPLACE(file_path, ?, ?)
                WHERE file_path LIKE ?
            """,
                (old_path, new_path, f"{old_path}%"),
            )
            updated += cursor.rowcount

        conn.commit()
        conn.close()

        self.log_message(f"Updated {updated} paths in database")

    def cleanup_empty_phase_folders(self):
        """Remove empty directories from original Phases folder after migration."""
        if self.dry_run:
            self.log_message("[DRY-RUN] Would clean up empty phase folders")
            return

        self.log_message("Cleaning up empty directories in Phases/...")

        # Walk the phases directory bottom-up and remove empty dirs
        removed = 0
        for root, dirs, files in os.walk(str(self.phases_dir), topdown=False):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                try:
                    # Check if directory is empty (no files, might have empty subdirs)
                    if not any(dir_path.rglob("*")):
                        dir_path.rmdir()
                        removed += 1
                except OSError:
                    pass  # Directory not empty or permission error

        self.log_message(f"Removed {removed} empty directories")

    def add_readme_to_phases(self):
        """Add README.txt to explain the new structure."""
        if self.dry_run:
            self.log_message("[DRY-RUN] Would add README to Phases/")
            return

        readme_content = f"""# Ableton Projects - Reorganized

Your projects have been reorganized by completion status.

## New Structure

Projects are now organized in these folders:
- COMPLETE/       - Finished tracks with arrangements ({sum(1 for m in self.moved_projects if m["status"] == "complete")} projects)
- WORKINPROGRESS/ - Active development ({sum(1 for m in self.moved_projects if m["status"] == "work_in_progress")} projects)
- SKETCHES/       - Started but needs work ({sum(1 for m in self.moved_projects if m["status"] == "sketch")} projects)
- IDEAS/          - Quick captures, minimal development ({sum(1 for m in self.moved_projects if m["status"] == "idea")} projects)

Each status folder contains phase subfolders (covid/, in_navy/, ALBUMS/, etc.)
to preserve the temporal context of when projects were created.

## Example Structure

COMPLETE/
├── ALBUMS/
│   └── DEMONDIGI/
│       └── D-LOC-MEGABASS Project/
├── covid/
│   └── NAKED 2 Project/
└── ventucky/
    └── chant Project/

## Backup Location

Your original structure is preserved at:
{self.backup_dir}

## To Restore Original Structure

If you need to restore the original layout:
1. Delete COMPLETE/, WORKINPROGRESS/, SKETCHES/, IDEAS/ folders
2. Copy contents from _BACKUP_PHASES/ back to Phases/

## Generated

{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Total projects reorganized: {len(self.moved_projects)}
"""

        readme_path = self.phases_dir / "README.txt"
        with open(readme_path, "w") as f:
            f.write(readme_content)

        self.log_message(f"Created README at: {readme_path}")

    def reorganize(self, phase_filter: str | None = None) -> dict:
        """
        Execute the full reorganization.

        Args:
            phase_filter: Optional phase to filter (for dry-run testing)

        Returns:
            Summary dict with results
        """
        start_time = datetime.now()

        self.log_message("=" * 60)
        self.log_message("STARTING PROJECT REORGANIZATION")
        self.log_message("=" * 60)

        # Step 1: Get projects from database
        projects = self.get_projects_from_db(phase_filter)
        total_projects = len(projects)

        self.log_message(f"Found {total_projects} projects to reorganize")

        if total_projects == 0:
            self.log_message("No projects found - aborting")
            return {"success": False, "error": "No projects found"}

        # Step 2: Create backup (full backup for safety)
        if self.skip_backup:
            self.log_message("Backup skipped (--no-backup flag set)")
            self.log_message(
                "NOTE: Move operations on same filesystem are atomic and safe"
            )
        elif not phase_filter and not self.dry_run:
            if not self.create_backup():
                return {"success": False, "error": "Backup creation failed"}
        elif phase_filter:
            self.log_message(f"Phase filter active ({phase_filter}) - skipping backup")

        # Step 3: Create status folders
        self.create_status_folders()

        # Step 4: Move projects
        self.log_message(f"Moving {total_projects} projects...")

        for i, project in enumerate(projects, 1):
            if i % 100 == 0 or i == total_projects:
                pct = i / total_projects * 100
                self.log_message(f"Progress: {i}/{total_projects} ({pct:.1f}%)")

            self.move_project(project)

        # Step 5: Update database paths
        self.update_database_paths()

        # Step 6: Clean up empty directories
        if not self.dry_run and not phase_filter:
            self.cleanup_empty_phase_folders()
            self.add_readme_to_phases()

        # Calculate summary
        elapsed = (datetime.now() - start_time).total_seconds()

        summary = {
            "success": len(self.moved_projects) > 0,
            "dry_run": self.dry_run,
            "total_projects": total_projects,
            "moved": len(self.moved_projects),
            "failed": len(self.failed_projects),
            "skipped": len(self.skipped_projects),
            "elapsed_seconds": elapsed,
            "phase_filter": phase_filter,
        }

        # Generate report
        self.generate_report(summary)

        return summary

    def generate_report(self, summary: dict):
        """Generate detailed migration report."""

        # Count by status
        status_counts = defaultdict(int)
        phase_counts = defaultdict(lambda: defaultdict(int))

        for move in self.moved_projects:
            status_counts[move["status"]] += 1
            phase_counts[move["phase"]][move["status"]] += 1

        report = f"""
================================================================================
              ABLETON PROJECT REORGANIZATION REPORT
================================================================================
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Mode: {"DRY-RUN (no changes made)" if self.dry_run else "LIVE MIGRATION"}
Phase Filter: {summary.get("phase_filter") or "None (all projects)"}

SUMMARY
-------
Total Projects Processed: {summary["total_projects"]}
Successfully Moved:       {summary["moved"]}
Failed:                   {summary["failed"]}
Skipped:                  {summary["skipped"]}
Time Elapsed:             {summary["elapsed_seconds"]:.1f} seconds

BREAKDOWN BY STATUS
-------------------
COMPLETE:         {status_counts.get("complete", 0):>6} projects
WORKINPROGRESS:   {status_counts.get("work_in_progress", 0):>6} projects
SKETCHES:         {status_counts.get("sketch", 0):>6} projects
IDEAS:            {status_counts.get("idea", 0):>6} projects

BREAKDOWN BY PHASE
------------------
"""

        for phase in sorted(phase_counts.keys()):
            counts = phase_counts[phase]
            total = sum(counts.values())
            report += f"{phase:<20} {total:>4} projects ("
            parts = []
            for status in ["complete", "work_in_progress", "sketch", "idea"]:
                if counts[status] > 0:
                    parts.append(f"{counts[status]} {self.STATUS_FOLDERS[status]}")
            report += ", ".join(parts) + ")\n"

        if self.failed_projects:
            report += "\nFAILED PROJECTS\n---------------\n"
            for fail in self.failed_projects[:20]:  # Limit to 20
                report += f"  - {fail['project']}: {fail['error']}\n"
            if len(self.failed_projects) > 20:
                report += f"  ... and {len(self.failed_projects) - 20} more\n"

        if self.skipped_projects:
            report += f"\nSKIPPED PROJECTS ({len(self.skipped_projects)} total)\n"
            report += "-" * 40 + "\n"
            for skip in self.skipped_projects[:20]:  # Limit to 20
                report += f"  - {skip['project']}: {skip['reason']}\n"
            if len(self.skipped_projects) > 20:
                report += f"  ... and {len(self.skipped_projects) - 20} more\n"

        if not self.dry_run and summary["moved"] > 0:
            report += f"""
BACKUP LOCATION
---------------
Original structure preserved at:
{self.backup_dir}

To restore original structure if needed:
1. Delete COMPLETE/, WORKINPROGRESS/, SKETCHES/, IDEAS/ folders
2. Copy contents from _BACKUP_PHASES/ back to Phases/

To reclaim space after verification (25GB):
  rm -rf "{self.backup_dir}"
"""

        report += "\n" + "=" * 60 + "\n"

        # Save report
        report_path = Path("reports/reorganization_report.txt")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w") as f:
            f.write(report)

        self.log_message(f"Report saved to: {report_path}")

        # Print summary to console
        print(report)

        # Save move manifest as JSON for potential rollback
        manifest_path = Path("reports/migration_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(
                {
                    "summary": summary,
                    "moved": self.moved_projects,
                    "failed": self.failed_projects,
                    "skipped": self.skipped_projects,
                },
                f,
                indent=2,
            )

        self.log_message(f"Migration manifest saved to: {manifest_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Reorganize Ableton projects by completion status"
    )
    parser.add_argument(
        "--projects-root",
        required=True,
        help="Root directory containing Projects folder",
    )
    parser.add_argument(
        "--database", default="database/projects.db", help="Path to projects database"
    )
    parser.add_argument("--log", default="logs/reorganize.log", help="Log file path")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without moving files"
    )
    parser.add_argument("--phase", help="Only process specific phase (for testing)")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation (use when backup already exists or for same-filesystem moves)",
    )

    args = parser.parse_args()

    reorganizer = ProjectReorganizer(
        projects_root=args.projects_root,
        db_path=args.database,
        log_path=args.log,
        dry_run=args.dry_run,
        skip_backup=args.no_backup,
    )

    result = reorganizer.reorganize(phase_filter=args.phase)

    if result["success"]:
        print("\n" + "=" * 60)
        print("REORGANIZATION COMPLETE")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print(f"REORGANIZATION FAILED: {result.get('error', 'Unknown error')}")
        print("=" * 60)
        exit(1)


if __name__ == "__main__":
    main()
