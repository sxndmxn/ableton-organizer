#!/usr/bin/env python3
"""
Ableton Project Scanner - Enhanced Version
Analyzes all .als files with session/arrangement detection, multiprocessing, and lxml support

Key features:
- Distinguishes between session view clips and arrangement clips
- Uses lxml for faster XML parsing
- Multiprocessing for parallel analysis
- Detailed session vs arrangement breakdown in reports
"""

import gzip
import hashlib
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool, cpu_count, Manager
from functools import partial
import os

# Try to use lxml for faster parsing, fall back to standard ElementTree
try:
    from lxml import etree as ET  # type: ignore

    USING_LXML = True
except ImportError:
    import xml.etree.ElementTree as ET

    USING_LXML = False


def analyze_single_project(als_file_str: str, db_path: str, log_queue) -> dict:
    """
    Analyze a single .als file - designed to run in parallel.

    Args:
        als_file_str: Path to .als file as string
        db_path: Path to SQLite database
        log_queue: Multiprocessing queue for logging

    Returns:
        dict with analysis results or error info
    """
    als_file = Path(als_file_str)
    result = {"file": str(als_file), "success": False, "error": None}

    try:
        # Read and decompress .als file (gzipped XML)
        with gzip.open(als_file, "rb") as f:
            content = f.read()

        # Calculate file hash
        file_hash = hashlib.md5(content).hexdigest()

        # Parse XML
        if USING_LXML:
            xml_tree = ET.fromstring(content)
        else:
            xml_tree = ET.fromstring(content.decode("utf-8"))

        # Extract all metadata
        metadata = extract_project_metadata(xml_tree, als_file)

        # Calculate audio folder size
        audio_folder = als_file.parent / "Samples" / "Processed" / "Consolidate"
        if not audio_folder.exists():
            audio_folder = als_file.parent / "Samples"
        audio_folder_size = (
            calculate_folder_size(audio_folder) if audio_folder.exists() else 0
        )

        # Get file stats
        file_stat = als_file.stat()

        # Store in database
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO projects 
            (file_path, file_size, last_modified, ableton_version, 
             track_count, plugin_count, effect_count, duration_seconds, bpm, 
             key_signature, project_name, completion_status, 
             complexity_score, analyzed, file_hash, audio_folder_size,
             has_midi_tracks, has_audio_tracks, has_automation, clip_count,
             session_clip_count, arrangement_clip_count, has_arrangement,
             arrangement_duration, session_only, phase_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                str(als_file),
                file_stat.st_size,
                datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
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
                metadata["session_clip_count"],
                metadata["arrangement_clip_count"],
                int(metadata["has_arrangement"]),
                metadata["arrangement_duration"],
                int(metadata["session_only"]),
                metadata["phase_folder"],
            ),
        )
        conn.commit()
        conn.close()

        result["success"] = True
        result["metadata"] = metadata

    except Exception as e:
        result["error"] = str(e)
        if log_queue:
            log_queue.put(f"Error analyzing {als_file.name}: {e}")

    return result


def extract_project_metadata(xml_tree, file_path: Path) -> dict:
    """
    Extract comprehensive metadata from Ableton project XML.

    Includes session view vs arrangement view clip detection.
    """
    # Extract phase folder from path (e.g., "ventucky", "covid", "ALBUMS")
    phase_folder = ""
    path_parts = file_path.parts
    for i, part in enumerate(path_parts):
        if part == "Phases" and i + 1 < len(path_parts):
            phase_folder = path_parts[i + 1]
            break

    # Core metadata
    metadata = {
        "name": file_path.stem,
        "version": xml_tree.get("MinorVersion", "unknown"),
        "phase_folder": phase_folder,
        "track_count": 0,
        "plugin_count": 0,
        "effect_count": 0,
        "duration": 0,
        "bpm": 120,
        "key": "C",
        "completion": "unknown",
        "complexity": 0,
        "has_midi_tracks": False,
        "has_audio_tracks": False,
        "has_automation": False,
        "clip_count": 0,
        # New session/arrangement fields
        "session_clip_count": 0,
        "arrangement_clip_count": 0,
        "has_arrangement": False,
        "arrangement_duration": 0,
        "session_only": False,
        "audio_folder_size": 0,
    }

    # Find LiveSet root
    live_set = xml_tree.find(".//LiveSet") if xml_tree.tag != "LiveSet" else xml_tree
    if live_set is None:
        live_set = xml_tree

    # Count tracks
    tracks = live_set.findall(".//Tracks/AudioTrack") + live_set.findall(
        ".//Tracks/MidiTrack"
    )
    metadata["track_count"] = len(tracks)

    # Count plugins and effects
    metadata["plugin_count"] = len(live_set.findall(".//PluginDevice"))
    metadata["effect_count"] = len(live_set.findall(".//AudioEffectDevice")) + len(
        live_set.findall(".//MidiEffectDevice")
    )

    # BPM extraction
    tempo_elem = live_set.find(".//MasterTrack//Tempo//Manual")
    if tempo_elem is not None:
        try:
            metadata["bpm"] = float(tempo_elem.get("Value", 120))
        except (ValueError, TypeError):
            pass

    # Automation detection
    automation_envelopes = live_set.findall(".//AutomationEnvelope")
    metadata["has_automation"] = len(automation_envelopes) > 0

    # === SESSION VIEW vs ARRANGEMENT CLIP DETECTION ===

    session_clips = []
    arrangement_clips = []
    max_arrangement_end = 0

    # Process each track
    for track in tracks:
        track_type = "midi" if track.tag == "MidiTrack" else "audio"

        if track_type == "midi":
            metadata["has_midi_tracks"] = True
        else:
            metadata["has_audio_tracks"] = True

        # Find clips in ClipSlotList (SESSION VIEW)
        clip_slots = track.findall(".//ClipSlotList//ClipSlot")
        for slot in clip_slots:
            # Check for MidiClip or AudioClip in the slot's Value
            midi_clip = slot.find(".//Value/MidiClip")
            audio_clip = slot.find(".//Value/AudioClip")
            clip = midi_clip if midi_clip is not None else audio_clip
            if clip is not None:
                session_clips.append(clip)

        # Find clips in MainSequencer/ClipTimeable/ArrangerAutomation/Events (ARRANGEMENT VIEW)
        # This is where arrangement clips are stored
        events_containers = track.findall(
            ".//MainSequencer//ClipTimeable//ArrangerAutomation//Events"
        )
        for events in events_containers:
            # Look for MidiClip or AudioClip children
            for clip in events:
                if clip.tag in ("MidiClip", "AudioClip"):
                    arrangement_clips.append(clip)

                    # Get the clip's time position
                    time_attr = clip.get("Time")
                    if time_attr:
                        try:
                            clip_time = float(time_attr)
                            # Also try to find CurrentEnd for duration
                            current_end = clip.find(".//CurrentEnd")
                            if current_end is not None:
                                end_val = float(current_end.get("Value", 0))
                                max_arrangement_end = max(
                                    max_arrangement_end, clip_time + end_val
                                )
                            else:
                                # Fallback: use clip time + some estimate
                                max_arrangement_end = max(
                                    max_arrangement_end, clip_time + 16
                                )
                        except (ValueError, TypeError):
                            pass

        # Alternative: check Sample/ArrangerAutomation for audio tracks
        sample_arranger = track.findall(".//Sample//ArrangerAutomation//Events")
        for events in sample_arranger:
            for clip in events:
                if clip.tag in ("AudioClip", "SampleClip"):
                    if clip not in arrangement_clips:
                        arrangement_clips.append(clip)
                        time_attr = clip.get("Time")
                        if time_attr:
                            try:
                                max_arrangement_end = max(
                                    max_arrangement_end, float(time_attr) + 16
                                )
                            except (ValueError, TypeError):
                                pass

    # Also check for clips directly under Events (alternative XML structure)
    all_events = live_set.findall(".//ArrangerAutomation/Events")
    for events in all_events:
        for child in events:
            if child.tag in ("MidiClip", "AudioClip"):
                if child not in arrangement_clips:
                    arrangement_clips.append(child)

    # Store session/arrangement counts
    metadata["session_clip_count"] = len(session_clips)
    metadata["arrangement_clip_count"] = len(arrangement_clips)
    metadata["clip_count"] = len(session_clips) + len(arrangement_clips)

    # Determine if project has arrangement content
    metadata["has_arrangement"] = len(arrangement_clips) > 0 or max_arrangement_end > 0
    metadata["arrangement_duration"] = max_arrangement_end

    # Session-only: has session clips but nothing in arrangement
    metadata["session_only"] = (
        len(session_clips) > 0 and not metadata["has_arrangement"]
    )

    # Calculate duration - prefer arrangement duration if available
    if metadata["has_arrangement"] and metadata["arrangement_duration"] > 0:
        metadata["duration"] = metadata["arrangement_duration"]
    else:
        # Fall back to finding max CurrentEnd across all clips
        all_clips = session_clips + arrangement_clips
        max_end = 0
        for clip in all_clips:
            current_end = clip.find(".//CurrentEnd")
            if current_end is not None:
                try:
                    max_end = max(max_end, float(current_end.get("Value", 0)))
                except (ValueError, TypeError):
                    pass
        metadata["duration"] = max_end

    # Calculate complexity score
    metadata["complexity"] = calculate_complexity_score(metadata, live_set)

    # Estimate completion status
    metadata["completion"] = estimate_completion_status(metadata, live_set)

    return metadata


def calculate_complexity_score(metadata: dict, xml_tree) -> float:
    """
    Calculate project complexity score with arrangement priority.

    Projects with arrangement content get higher scores.
    """
    # Base scores
    track_score = metadata["track_count"] * 10
    plugin_score = metadata["plugin_count"] * 15
    effect_score = metadata["effect_count"] * 8
    automation_score = 5 if metadata["has_automation"] else 0
    clip_score = metadata["clip_count"] * 2

    # Audio processing complexity
    audio_processing_score = 0
    if metadata["has_audio_tracks"]:
        audio_processing_score = metadata["effect_count"] * 5

    base_complexity = (
        track_score
        + plugin_score
        + effect_score
        + automation_score
        + clip_score
        + audio_processing_score
    )

    # === ARRANGEMENT PRIORITY BONUS ===
    # Projects with arrangement content get significant bonus
    if metadata["has_arrangement"]:
        # More arrangement clips = more work put into arrangement
        arrangement_bonus = metadata["arrangement_clip_count"] * 5

        # Longer arrangements = more developed tracks
        # Convert beats to bars (assuming 4/4), then to minutes at project BPM
        arrangement_bars = metadata["arrangement_duration"] / 4
        arrangement_minutes = arrangement_bars / (
            metadata["bpm"] / 4
        )  # bars per minute
        duration_bonus = min(30, arrangement_minutes * 10)  # Cap at 30

        base_complexity += arrangement_bonus + duration_bonus

    # Session-only projects: valuable as idea jams but not as "complete"
    # Don't penalize them heavily, but don't boost like arrangements
    if metadata["session_only"]:
        # Still value complex session projects (lots of clips, effects)
        session_complexity_boost = metadata["session_clip_count"] * 2
        base_complexity += session_complexity_boost

    # Normalize - cap at 100 but allow natural distribution
    return min(100, base_complexity / 10)


def estimate_completion_status(metadata: dict, xml_tree) -> str:
    """
    Estimate project completion status.

    Uses arrangement presence as primary indicator.
    """
    completion_score = 0

    # Strong indicator: Has arrangement with significant duration
    if metadata["has_arrangement"]:
        # Convert beats to bars
        arrangement_bars = metadata["arrangement_duration"] / 4

        if arrangement_bars >= 32:  # 32+ bars = likely has structure
            completion_score += 3
        elif arrangement_bars >= 16:  # 16+ bars = developing
            completion_score += 2
        elif arrangement_bars > 0:  # Any arrangement = started
            completion_score += 1

    # Session-only with lots of clips = active development
    if metadata["session_only"]:
        if metadata["session_clip_count"] >= 16:
            completion_score += 1
        elif metadata["session_clip_count"] >= 8:
            completion_score += 0
        else:
            completion_score -= 1

    # Complexity contributes
    if metadata["complexity"] >= 50:
        completion_score += 1
    elif metadata["complexity"] >= 25:
        completion_score += 0
    else:
        completion_score -= 1

    # Automation indicates refinement
    if metadata["has_automation"]:
        completion_score += 1

    # Plugin usage indicates serious work
    if metadata["plugin_count"] >= 5:
        completion_score += 1

    # Final classification
    if completion_score >= 4:
        return "complete"
    elif completion_score >= 2:
        return "work_in_progress"
    elif completion_score >= 0:
        return "sketch"
    else:
        return "idea"


def calculate_folder_size(folder_path: Path) -> int:
    """Calculate total size of a folder recursively."""
    total_size = 0
    try:
        for file_path in folder_path.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except (OSError, PermissionError):
        pass
    return total_size


class AbletonProjectScanner:
    """Main scanner class with multiprocessing support."""

    def __init__(
        self,
        source_dir: str,
        db_path: str,
        log_path: str | None = None,
        num_workers: int | None = None,
    ):
        self.source_dir = Path(source_dir)
        self.db_path = db_path
        self.log_path = log_path or "logs/scanner.log"
        self.num_workers = num_workers or min(cpu_count(), 8)

        # Ensure directories exist
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self.init_database()

        self.log_message(f"Scanner initialized with {self.num_workers} workers")
        self.log_message(
            f"Using {'lxml' if USING_LXML else 'standard ElementTree'} for XML parsing"
        )

    def log_message(self, message: str):
        """Log a message to console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)

        with open(self.log_path, "a") as f:
            f.write(log_entry + "\n")

    def init_database(self):
        """Initialize SQLite database with enhanced schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
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
                usage_priority INTEGER DEFAULT 0,
                analyzed BOOLEAN DEFAULT 0,
                processed BOOLEAN DEFAULT 0,
                category TEXT,
                migrated BOOLEAN DEFAULT 0,
                file_hash TEXT,
                audio_folder_size INTEGER,
                has_midi_tracks INTEGER,
                has_audio_tracks INTEGER,
                has_automation INTEGER,
                clip_count INTEGER,
                -- New session/arrangement columns
                session_clip_count INTEGER DEFAULT 0,
                arrangement_clip_count INTEGER DEFAULT 0,
                has_arrangement INTEGER DEFAULT 0,
                arrangement_duration REAL DEFAULT 0,
                session_only INTEGER DEFAULT 0,
                phase_folder TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()

    def scan_projects(self):
        """Scan all .als files using multiprocessing."""
        self.log_message(f"Starting project scan in: {self.source_dir}")

        if not self.source_dir.exists():
            self.log_message(
                f"ERROR: Source directory does not exist: {self.source_dir}"
            )
            return

        # Find all .als files, excluding Backup folders
        als_files = [
            str(f) for f in self.source_dir.rglob("*.als") if "Backup" not in str(f)
        ]

        total_files = len(als_files)
        self.log_message(f"Found {total_files} Ableton projects (excluding backups)")

        if total_files == 0:
            self.log_message("No projects found to analyze")
            return

        # Create multiprocessing manager for logging
        manager = Manager()
        log_queue = manager.Queue()

        # Create partial function with fixed arguments
        analyze_func = partial(
            analyze_single_project, db_path=self.db_path, log_queue=log_queue
        )

        # Process in parallel
        self.log_message(
            f"Starting parallel analysis with {self.num_workers} workers..."
        )

        start_time = datetime.now()

        with Pool(self.num_workers) as pool:
            results = []
            for i, result in enumerate(pool.imap_unordered(analyze_func, als_files), 1):
                results.append(result)

                # Progress logging every 10 projects or at milestones
                if i % 10 == 0 or i == total_files:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = i / elapsed if elapsed > 0 else 0
                    eta = (total_files - i) / rate if rate > 0 else 0
                    self.log_message(
                        f"Progress: {i}/{total_files} ({i / total_files * 100:.1f}%) - {rate:.1f}/sec - ETA: {eta:.0f}s"
                    )

        # Process log queue
        while not log_queue.empty():
            self.log_message(log_queue.get())

        # Count successes and failures
        successes = sum(1 for r in results if r["success"])
        failures = sum(1 for r in results if not r["success"])

        elapsed_total = (datetime.now() - start_time).total_seconds()

        self.log_message(f"Analysis complete in {elapsed_total:.1f}s")
        self.log_message(f"Successfully analyzed: {successes}")
        self.log_message(f"Failed: {failures}")

        # Generate report
        self.generate_report()

    def generate_report(self):
        """Generate comprehensive analysis report with session/arrangement breakdown."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Basic statistics
        cursor.execute("SELECT COUNT(*) FROM projects WHERE analyzed = 1")
        total_analyzed = cursor.fetchone()[0]

        if total_analyzed == 0:
            self.log_message("No projects analyzed yet")
            return

        cursor.execute("""
            SELECT 
                AVG(complexity_score), MAX(complexity_score), MIN(complexity_score),
                AVG(duration_seconds), MAX(duration_seconds)
            FROM projects WHERE analyzed = 1
        """)
        avg_complexity, max_complexity, min_complexity, avg_duration, max_duration = (
            cursor.fetchone()
        )

        # Completion breakdown
        cursor.execute("""
            SELECT completion_status, COUNT(*) 
            FROM projects WHERE analyzed = 1 
            GROUP BY completion_status
        """)
        completion_breakdown = dict(cursor.fetchall())

        # Session vs Arrangement breakdown
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN has_arrangement = 1 THEN 1 ELSE 0 END) as with_arrangement,
                SUM(CASE WHEN session_only = 1 THEN 1 ELSE 0 END) as session_only,
                AVG(CASE WHEN has_arrangement = 1 THEN arrangement_duration ELSE NULL END) as avg_arr_duration,
                AVG(CASE WHEN has_arrangement = 1 THEN arrangement_clip_count ELSE NULL END) as avg_arr_clips,
                AVG(session_clip_count) as avg_session_clips
            FROM projects WHERE analyzed = 1
        """)
        session_arr_stats = cursor.fetchone()

        # Phase folder breakdown
        cursor.execute("""
            SELECT 
                phase_folder,
                COUNT(*) as total,
                SUM(CASE WHEN has_arrangement = 1 THEN 1 ELSE 0 END) as arranged,
                SUM(CASE WHEN session_only = 1 THEN 1 ELSE 0 END) as session_only,
                ROUND(AVG(complexity_score), 1) as avg_complexity,
                ROUND(AVG(CASE WHEN has_arrangement = 1 THEN arrangement_duration/4 ELSE NULL END), 1) as avg_bars
            FROM projects 
            WHERE analyzed = 1 AND phase_folder != ''
            GROUP BY phase_folder
            ORDER BY total DESC
        """)
        phase_breakdown = cursor.fetchall()

        # Build report
        report = f"""
================================================================================
                    ABLETON PROJECT ANALYSIS REPORT
================================================================================
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Source Directory: {self.source_dir}
XML Parser: {"lxml (fast)" if USING_LXML else "ElementTree (standard)"}
Workers: {self.num_workers}

================================================================================
                              SUMMARY
================================================================================
Total Projects Analyzed: {total_analyzed}

Complexity Scores:
  Average: {avg_complexity:.1f}
  Highest: {max_complexity:.1f}
  Lowest:  {min_complexity:.1f}

Duration (beats):
  Average: {avg_duration:.1f} ({avg_duration / 4:.1f} bars)
  Longest: {max_duration:.1f} ({max_duration / 4:.1f} bars)

================================================================================
                       COMPLETION STATUS BREAKDOWN
================================================================================
Complete:         {completion_breakdown.get("complete", 0):>6} ({completion_breakdown.get("complete", 0) / total_analyzed * 100:.1f}%)
Work in Progress: {completion_breakdown.get("work_in_progress", 0):>6} ({completion_breakdown.get("work_in_progress", 0) / total_analyzed * 100:.1f}%)
Sketches:         {completion_breakdown.get("sketch", 0):>6} ({completion_breakdown.get("sketch", 0) / total_analyzed * 100:.1f}%)
Ideas:            {completion_breakdown.get("idea", 0):>6} ({completion_breakdown.get("idea", 0) / total_analyzed * 100:.1f}%)

================================================================================
                    SESSION VIEW vs ARRANGEMENT BREAKDOWN
================================================================================
Projects with Arrangement: {session_arr_stats[1]:>6} ({session_arr_stats[1] / total_analyzed * 100:.1f}%)
  - These have clips drawn in the arrangement timeline
  - Average arrangement length: {(session_arr_stats[3] or 0):.1f} beats ({(session_arr_stats[3] or 0) / 4:.1f} bars)
  - Average arrangement clips: {(session_arr_stats[4] or 0):.1f}

Session-Only Projects:     {session_arr_stats[2]:>6} ({session_arr_stats[2] / total_analyzed * 100:.1f}%)
  - These have clips only in session/clip view (idea jams)
  - Average session clips: {(session_arr_stats[5] or 0):.1f}

Mixed/Empty:               {total_analyzed - session_arr_stats[1] - session_arr_stats[2]:>6}

================================================================================
                         LIFE PHASE BREAKDOWN
================================================================================
{"Phase":<20} {"Total":>8} {"Arranged":>10} {"Session":>10} {"Complexity":>12} {"Avg Bars":>10}
{"-" * 72}
"""

        for phase in phase_breakdown:
            phase_name = phase[0] if phase[0] else "(root)"
            report += f"{phase_name:<20} {phase[1]:>8} {phase[2]:>10} {phase[3]:>10} {phase[4]:>12} {phase[5] if phase[5] else 'N/A':>10}\n"

        # Top 15 most complex projects
        report += """
================================================================================
                     TOP 15 MOST COMPLEX PROJECTS
================================================================================
"""
        cursor.execute("""
            SELECT project_name, complexity_score, completion_status, 
                   has_arrangement, arrangement_duration/4 as bars, 
                   track_count, plugin_count, phase_folder
            FROM projects WHERE analyzed = 1 
            ORDER BY complexity_score DESC 
            LIMIT 15
        """)

        for project in cursor.fetchall():
            arr_status = "ARR" if project[3] else "SES"
            bars = f"{project[4]:.0f} bars" if project[4] else "N/A"
            report += f"  {project[0][:40]:<40} {project[1]:>6.1f} [{arr_status}] {bars:>10} ({project[5]} tracks, {project[6]} plugins) [{project[7]}]\n"

        # Top 15 longest arrangements
        report += """
================================================================================
                     TOP 15 LONGEST ARRANGEMENTS
================================================================================
"""
        cursor.execute("""
            SELECT project_name, arrangement_duration/4 as bars, complexity_score,
                   track_count, arrangement_clip_count, phase_folder
            FROM projects 
            WHERE analyzed = 1 AND has_arrangement = 1
            ORDER BY arrangement_duration DESC 
            LIMIT 15
        """)

        for project in cursor.fetchall():
            report += f"  {project[0][:40]:<40} {project[1]:>6.0f} bars  (complexity: {project[2]:.1f}, {project[3]} tracks, {project[4]} arr clips) [{project[5]}]\n"

        # Top 15 complex session-only jams
        report += """
================================================================================
                  TOP 15 COMPLEX SESSION-ONLY JAMS
================================================================================
"""
        cursor.execute("""
            SELECT project_name, session_clip_count, complexity_score,
                   track_count, plugin_count, phase_folder
            FROM projects 
            WHERE analyzed = 1 AND session_only = 1
            ORDER BY complexity_score DESC 
            LIMIT 15
        """)

        for project in cursor.fetchall():
            report += f"  {project[0][:40]:<40} {project[1]:>4} clips  (complexity: {project[2]:.1f}, {project[3]} tracks, {project[4]} plugins) [{project[5]}]\n"

        report += """
================================================================================
                              END OF REPORT
================================================================================
"""

        # Save report
        report_path = Path("reports/analysis_report.txt")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w") as f:
            f.write(report)

        self.log_message(f"Analysis report saved to: {report_path}")

        # Also save CSV for detailed analysis
        csv_path = Path("reports/project_analysis.csv")
        with open(csv_path, "w") as f:
            f.write(
                "project_name,phase_folder,file_size,complexity_score,completion_status,"
            )
            f.write(
                "has_arrangement,arrangement_duration,arrangement_clips,session_clips,"
            )
            f.write("track_count,plugin_count,bpm,session_only\n")

            cursor.execute("""
                SELECT project_name, phase_folder, file_size, complexity_score, completion_status,
                       has_arrangement, arrangement_duration, arrangement_clip_count, session_clip_count,
                       track_count, plugin_count, bpm, session_only
                FROM projects WHERE analyzed = 1
                ORDER BY complexity_score DESC
            """)

            for row in cursor.fetchall():
                f.write(",".join(str(x) if x is not None else "" for x in row) + "\n")

        self.log_message(f"CSV data saved to: {csv_path}")

        conn.close()

        # Print summary to console
        print("\n" + "=" * 60)
        print("QUICK SUMMARY")
        print("=" * 60)
        print(f"Total Projects: {total_analyzed}")
        print(
            f"With Arrangement: {session_arr_stats[1]} ({session_arr_stats[1] / total_analyzed * 100:.1f}%)"
        )
        print(
            f"Session-Only (Jams): {session_arr_stats[2]} ({session_arr_stats[2] / total_analyzed * 100:.1f}%)"
        )
        print(f"Complete: {completion_breakdown.get('complete', 0)}")
        print(f"Work in Progress: {completion_breakdown.get('work_in_progress', 0)}")
        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Ableton projects with session/arrangement detection"
    )
    parser.add_argument(
        "--source", required=True, help="Source directory containing Ableton projects"
    )
    parser.add_argument(
        "--database", default="database/projects.db", help="Database file path"
    )
    parser.add_argument("--log", default="logs/scanner.log", help="Log file path")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Number of worker processes (default: {min(cpu_count(), 8)})",
    )

    args = parser.parse_args()

    scanner = AbletonProjectScanner(args.source, args.database, args.log, args.workers)
    scanner.scan_projects()


if __name__ == "__main__":
    main()
