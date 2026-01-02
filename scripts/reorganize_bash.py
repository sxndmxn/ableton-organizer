#!/usr/bin/env python3
"""
Ableton Project Reorganizer - Bash Move Version

Uses system `mv` command instead of shutil.move for better NTFS compatibility.
"""

import os
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import json


class ProjectReorganizer:
    """Reorganize projects using bash mv for NTFS compatibility."""

    STATUS_FOLDERS = {
        "complete": "COMPLETE",
        "work_in_progress": "WORKINPROGRESS",
        "sketch": "SKETCHES",
        "idea": "IDEAS",
    }

    def __init__(self, projects_root: str, db_path: str, dry_run: bool = False):
        self.projects_root = Path(projects_root)
        self.db_path = db_path
        self.dry_run = dry_run
        self.phases_dir = self.projects_root / "Phases"

        self.moved = []
        self.failed = []
        self.skipped = []

    def log(self, msg: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def get_projects(self) -> list[dict]:
        """Get all projects from database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file_path, project_name, completion_status, phase_folder
            FROM projects
            WHERE analyzed = 1
            ORDER BY phase_folder, completion_status, project_name
        """)

        projects = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return projects

    def get_project_folder(self, als_path: Path) -> Path | None:
        """Get project folder from .als file path."""
        folder = als_path.parent
        return folder if folder.exists() else None

    def extract_phase_info(self, project_folder: Path) -> tuple[str, str]:
        """Extract phase name and relative path."""
        try:
            rel = project_folder.relative_to(self.phases_dir)
            parts = rel.parts
            if len(parts) == 0:
                return ("", project_folder.name)
            phase = parts[0]
            rel_path = str(Path(*parts[1:])) if len(parts) > 1 else project_folder.name
            return (phase, rel_path)
        except ValueError:
            return ("", project_folder.name)

    def move_with_bash(self, src: Path, dest: Path) -> tuple[bool, str]:
        """Move using bash mv command for NTFS compatibility."""
        # Create parent directories
        dest.parent.mkdir(parents=True, exist_ok=True)

        if self.dry_run:
            return True, "dry-run"

        try:
            result = subprocess.run(
                ["mv", str(src), str(dest)], capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                return True, ""
            else:
                return False, result.stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "timeout"
        except Exception as e:
            return False, str(e)

    def reorganize(self):
        """Execute the reorganization."""
        self.log("=" * 60)
        self.log("ABLETON PROJECT REORGANIZATION (BASH MOVE)")
        self.log("=" * 60)

        projects = self.get_projects()
        self.log(f"Found {len(projects)} projects")

        # Create status folders
        for status, folder in self.STATUS_FOLDERS.items():
            folder_path = self.projects_root / folder
            if not self.dry_run:
                folder_path.mkdir(exist_ok=True)
            self.log(f"Status folder: {folder_path}")

        # Process each project
        start = datetime.now()

        for i, proj in enumerate(projects, 1):
            als_path = Path(proj["file_path"])
            status = proj["completion_status"]
            name = proj["project_name"]

            # Progress every 100
            if i % 100 == 0:
                self.log(f"Progress: {i}/{len(projects)}")

            # Get source folder
            src_folder = self.get_project_folder(als_path)
            if src_folder is None:
                self.skipped.append({"name": name, "reason": "not found"})
                continue

            # Skip if already in a status folder
            try:
                rel = src_folder.relative_to(self.projects_root)
                if rel.parts[0] in self.STATUS_FOLDERS.values():
                    self.skipped.append({"name": name, "reason": "already moved"})
                    continue
            except ValueError:
                pass

            # Calculate destination
            status_folder = self.STATUS_FOLDERS.get(status, "SKETCHES")
            phase, rel_path = self.extract_phase_info(src_folder)

            if not phase:
                self.skipped.append({"name": name, "reason": "no phase"})
                continue

            dest_folder = self.projects_root / status_folder / phase / rel_path

            # Skip if destination exists
            if dest_folder.exists():
                self.skipped.append({"name": name, "reason": "dest exists"})
                continue

            # Move!
            success, error = self.move_with_bash(src_folder, dest_folder)

            if success:
                self.moved.append(
                    {
                        "name": name,
                        "status": status,
                        "phase": phase,
                        "src": str(src_folder),
                        "dest": str(dest_folder),
                    }
                )
            else:
                self.failed.append(
                    {"name": name, "error": error, "src": str(src_folder)}
                )
                self.log(f"FAILED: {name} - {error}")

        elapsed = (datetime.now() - start).total_seconds()

        # Summary
        self.log("")
        self.log("=" * 60)
        self.log("SUMMARY")
        self.log("=" * 60)
        self.log(f"Mode: {'DRY-RUN' if self.dry_run else 'LIVE'}")
        self.log(f"Total: {len(projects)}")
        self.log(f"Moved: {len(self.moved)}")
        self.log(f"Failed: {len(self.failed)}")
        self.log(f"Skipped: {len(self.skipped)}")
        self.log(f"Time: {elapsed:.1f}s")

        # Count by status
        status_counts = defaultdict(int)
        for m in self.moved:
            status_counts[m["status"]] += 1

        self.log("")
        self.log("Moved by status:")
        for status, folder in self.STATUS_FOLDERS.items():
            self.log(f"  {folder}: {status_counts.get(status, 0)}")

        # Save results
        results = {
            "moved": self.moved,
            "failed": self.failed,
            "skipped": self.skipped,
            "elapsed": elapsed,
        }

        report_path = Path("reports/bash_reorganize_results.json")
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2)

        self.log(f"\nResults saved to: {report_path}")

        return len(self.failed) == 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-root", required=True)
    parser.add_argument("--database", default="database/projects.db")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    reorg = ProjectReorganizer(
        projects_root=args.projects_root, db_path=args.database, dry_run=args.dry_run
    )

    success = reorg.reorganize()
    exit(0 if success else 1)
