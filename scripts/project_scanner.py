#!/usr/bin/env python3
"""
Ableton Project Scanner
Analyzes all .als files and extracts metadata for intelligent categorization
"""

import os
import json
import sqlite3
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import argparse
import hashlib


class AbletonProjectScanner:
    def __init__(self, source_dir, db_path, log_path=None):
        self.source_dir = Path(source_dir)
        self.db_path = db_path
        self.log_path = log_path or "logs/scanner.log"
        self.conn = sqlite3.connect(db_path)
        self.init_database()
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

    def init_database(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE,
                file_size INTEGER,
                last_modified TEXT,
                ableton_version TEXT,
                track_count INTEGER,
                plugin_count INTEGER,
                effect_count INTEGER,
                duration_seconds REAL,
                bpm REAL,
                key_signature TEXT,
                project_name TEXT,
                completion_status TEXT,
                complexity_score REAL,
                usage_priority INTEGER,
                analyzed BOOLEAN DEFAULT 0,
                processed BOOLEAN DEFAULT 0,
                category TEXT,
                migrated BOOLEAN DEFAULT 0,
                file_hash TEXT,
                audio_folder_size INTEGER,
                has_midi_tracks INTEGER,
                has_audio_tracks INTEGER,
                has_automation INTEGER,
                clip_count INTEGER
            )
        """)
        self.conn.commit()

    def scan_projects(self):
        self.log_message(f"Starting project scan in: {self.source_dir}")

        if not self.source_dir.exists():
            self.log_message(
                f"ERROR: Source directory does not exist: {self.source_dir}"
            )
            return

        als_files = list(self.source_dir.rglob("*.als"))
        self.log_message(f"Found {len(als_files)} Ableton projects")

        for idx, als_file in enumerate(als_files, 1):
            self.log_message(f"Analyzing {idx}/{len(als_files)}: {als_file.name}")
            self.analyze_project(als_file)

        self.log_message("Project analysis complete")
        self.generate_report()

    def analyze_project(self, als_file):
        try:
            with open(als_file, "rb") as f:
                content = f.read()

            # Calculate file hash for integrity checking
            file_hash = hashlib.md5(content).hexdigest()

            # Extract metadata from XML
            tree = ET.fromstring(content)
            metadata = self.extract_metadata(tree, als_file)

            # Calculate audio folder size
            audio_folder = als_file.parent / "Audio"
            audio_folder_size = (
                self.calculate_folder_size(audio_folder) if audio_folder.exists() else 0
            )

            # Store in database
            self.conn.execute(
                """
                INSERT OR REPLACE INTO projects 
                (file_path, file_size, last_modified, ableton_version, 
                 track_count, plugin_count, effect_count, duration_seconds, bpm, 
                 key_signature, project_name, completion_status, 
                 complexity_score, analyzed, file_hash, audio_folder_size,
                 has_midi_tracks, has_audio_tracks, has_automation, clip_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(als_file),
                    als_file.stat().st_size,
                    datetime.fromtimestamp(als_file.stat().st_mtime).isoformat(),
                    metadata["version"],
                    metadata["track_count"],
                    metadata["plugin_count"],
                    metadata["effect_count"],
                    metadata["duration"],
                    metadata["bpm"],
                    metadata["key"],
                    metadata["name"],
                    metadata["completion"],
                    metadata["complexity"],
                    1,  # analyzed
                    file_hash,
                    audio_folder_size,
                    int(metadata["has_midi_tracks"]),
                    int(metadata["has_audio_tracks"]),
                    int(metadata["has_automation"]),
                    metadata["clip_count"],
                ),
            )

        except Exception as e:
            self.log_message(f"Error analyzing {als_file}: {str(e)}")

        self.conn.commit()

    def extract_metadata(self, xml_tree, file_path):
        # Core metadata extraction
        metadata = {
            "name": file_path.stem,
            "version": xml_tree.get("MinorVersion", "unknown"),
            "track_count": len(xml_tree.findall(".//Track")),
            "plugin_count": len(xml_tree.findall(".//PluginDevice")),
            "effect_count": len(xml_tree.findall(".//AudioEffect")),
            "duration": 0,
            "bpm": 120,
            "key": "C",
            "completion": "unknown",
            "complexity": 0,
            "has_midi_tracks": False,
            "has_audio_tracks": False,
            "has_automation": False,
            "clip_count": 0,
        }

        # BPM extraction
        tempo_elem = xml_tree.find(".//MasterTrack//Tempo//Manual")
        if tempo_elem is not None:
            try:
                metadata["bpm"] = float(tempo_elem.get("Value", 120))
            except (ValueError, TypeError):
                pass

        # Key signature extraction
        key_elem = xml_tree.find(".//MasterTrack//KeySignature//Manual")
        if key_elem is not None:
            metadata["key"] = key_elem.get("Key", "C")

        # Duration estimation (last clip end time)
        last_clip_time = 0
        clips = xml_tree.findall(".//SampleClip") + xml_tree.findall(".//MidiClip")
        metadata["clip_count"] = len(clips)

        for clip in clips:
            try:
                start_time = float(clip.get("CurrentStart", 0))
                duration = float(clip.get("CurrentLength", 0))
                last_clip_time = max(last_clip_time, start_time + duration)

                # Check for MIDI vs Audio
                if clip.tag == "MidiClip":
                    metadata["has_midi_tracks"] = True
                else:
                    metadata["has_audio_tracks"] = True

            except (ValueError, TypeError):
                pass

        metadata["duration"] = last_clip_time

        # Automation detection
        automation_envelopes = xml_tree.findall(".//AutomationEnvelope")
        metadata["has_automation"] = len(automation_envelopes) > 0

        # Complexity scoring algorithm
        metadata["complexity"] = self.calculate_complexity(metadata, xml_tree)

        # Completion status estimation
        metadata["completion"] = self.estimate_completion(xml_tree, metadata)

        return metadata

    def calculate_complexity(self, metadata, xml_tree):
        # Multi-factor complexity algorithm
        track_score = metadata["track_count"] * 10
        plugin_score = metadata["plugin_count"] * 15
        effect_score = metadata["effect_count"] * 8
        automation_score = len(xml_tree.findall(".//AutomationEnvelope")) * 5
        clip_score = metadata["clip_count"] * 2

        # Audio processing complexity
        audio_processing_score = 0
        if metadata["has_audio_tracks"]:
            audio_processing_score = len(xml_tree.findall(".//AudioEffect")) * 10

        base_complexity = (
            track_score
            + plugin_score
            + effect_score
            + automation_score
            + clip_score
            + audio_processing_score
        )

        # Normalize by duration to prevent very short projects from appearing complex
        duration_factor = max(1, metadata["duration"] / 60)  # Normalize by minute

        # Audio folder size contributes to complexity (more recordings = more work)
        audio_size_factor = min(
            50, metadata["audio_folder_size"] / (1024 * 1024 * 1024)
        )  # GB to score

        final_complexity = (base_complexity / duration_factor) + audio_size_factor

        return min(100, final_complexity)  # Cap at 100

    def estimate_completion(self, xml_tree, metadata):
        # Enhanced completion detection using multiple factors
        total_tracks = len(xml_tree.findall(".//Track"))

        # Check for muted tracks
        muted_tracks = len(xml_tree.findall('.//Track[@isMuted="true"]'))
        muted_ratio = muted_tracks / max(1, total_tracks)

        # Check for empty tracks (no clips)
        empty_tracks = 0
        for track in xml_tree.findall(".//Track"):
            if not track.findall(".//ClipSlot/Clip"):
                empty_tracks += 1

        empty_ratio = empty_tracks / max(1, total_tracks)

        # Check arrangement length
        arrangement_length = metadata["duration"]
        has_substance = arrangement_length > 60  # At least 1 minute

        # Check automation density (more automation usually means more refined)
        automation_density = len(xml_tree.findall(".//AutomationEnvelope")) / max(
            1, metadata["track_count"]
        )

        # Completion scoring
        completion_score = 0

        # Penalize high mute/empty ratios
        if muted_ratio > 0.5:
            completion_score -= 2
        if empty_ratio > 0.3:
            completion_score -= 2

        # Reward substance
        if has_substance:
            completion_score += 1

        # Reward refinement
        if automation_density > 2:
            completion_score += 1

        # Reward complexity (complex projects are usually more developed)
        if metadata["complexity"] > 50:
            completion_score += 1

        # Final classification
        if completion_score >= 2:
            return "complete"
        elif completion_score >= 0:
            return "work_in_progress"
        else:
            return "sketch"

    def calculate_folder_size(self, folder_path):
        """Calculate total size of a folder recursively"""
        total_size = 0
        try:
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except (OSError, PermissionError):
            pass
        return total_size

    def generate_report(self):
        """Generate analysis report"""
        cursor = self.conn.cursor()

        # Get statistics
        cursor.execute("SELECT COUNT(*) FROM projects WHERE analyzed = 1")
        total_analyzed = cursor.fetchone()[0]

        cursor.execute(
            "SELECT AVG(complexity_score), MAX(complexity_score), MIN(complexity_score) FROM projects WHERE analyzed = 1"
        )
        avg_complexity, max_complexity, min_complexity = cursor.fetchone()

        cursor.execute(
            "SELECT completion_status, COUNT(*) FROM projects WHERE analyzed = 1 GROUP BY completion_status"
        )
        completion_breakdown = dict(cursor.fetchall())

        # Write report
        report = f"""
ABLETON PROJECT ANALYSIS REPORT
=================================
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Source Directory: {self.source_dir}

SUMMARY
-------
Total Projects Analyzed: {total_analyzed}
Average Complexity: {avg_complexity:.1f}
Highest Complexity: {max_complexity:.1f}
Lowest Complexity: {min_complexity:.1f}

COMPLETION BREAKDOWN
-------------------
Complete: {completion_breakdown.get("complete", 0)}
Work in Progress: {completion_breakdown.get("work_in_progress", 0)}
Sketches: {completion_breakdown.get("sketch", 0)}

TOP 10 MOST COMPLEX PROJECTS
----------------------------
"""

        cursor.execute("""
            SELECT project_name, complexity_score, completion_status, track_count, plugin_count 
            FROM projects WHERE analyzed = 1 
            ORDER BY complexity_score DESC 
            LIMIT 10
        """)

        for project in cursor.fetchall():
            report += f"{project[0]}: {project[1]:.1f} ({project[2]}) - {project[3]} tracks, {project[4]} plugins\n"

        # Save report
        report_path = Path("reports/analysis_report.txt")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w") as f:
            f.write(report)

        self.log_message(f"Analysis report saved to: {report_path}")

        # Also save CSV for spreadsheet analysis
        csv_path = Path("reports/project_analysis.csv")
        with open(csv_path, "w") as f:
            f.write(
                "project_name,file_size,complexity_score,completion_status,track_count,plugin_count,duration,bpm\n"
            )
            cursor.execute("""
                SELECT project_name, file_size, complexity_score, completion_status, 
                       track_count, plugin_count, duration_seconds, bpm
                FROM projects WHERE analyzed = 1
                ORDER BY complexity_score DESC
            """)
            for row in cursor.fetchall():
                f.write(",".join(str(x) for x in row) + "\n")

        self.log_message(f"CSV data saved to: {csv_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Ableton projects for intelligent organization"
    )
    parser.add_argument(
        "--source", required=True, help="Source directory containing Ableton projects"
    )
    parser.add_argument(
        "--database", default="database/projects.db", help="Database file path"
    )
    parser.add_argument("--log", default="logs/scanner.log", help="Log file path")

    args = parser.parse_args()

    scanner = AbletonProjectScanner(args.source, args.database, args.log)
    scanner.scan_projects()


if __name__ == "__main__":
    main()
