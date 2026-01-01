#!/usr/bin/env python3
"""
Migration Progress Dashboard
Real-time monitoring and reporting for Ableton project migration
"""

import sqlite3
import json
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import math


class MigrationDashboard:
    def __init__(self, db_path, progress_file=None):
        self.db_path = db_path
        self.progress_file = progress_file or "temp/migration_progress.txt"
        self.conn = sqlite3.connect(db_path)

    def get_migration_statistics(self):
        """Get comprehensive migration statistics"""
        cursor = self.conn.cursor()

        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM projects WHERE analyzed = 1")
        total_analyzed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM projects WHERE processed = 1")
        total_processed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM projects WHERE migrated = 1")
        migrated_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM projects WHERE migration_failed = 1")
        failed_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM projects WHERE processed = 1 AND migrated = 0 AND migration_failed = 0"
        )
        remaining_count = cursor.fetchone()[0]

        # Success rates
        migration_success_rate = 0
        if total_processed > 0:
            migration_success_rate = round((migrated_count / total_processed) * 100, 1)

        # Storage statistics
        cursor.execute("""
            SELECT SUM(file_size), SUM(audio_folder_size) 
            FROM projects WHERE migrated = 1
        """)
        size_data = cursor.fetchone()
        migrated_file_size = size_data[0] or 0
        migrated_audio_size = size_data[1] or 0

        # Category breakdown
        cursor.execute("""
            SELECT category, COUNT(*) 
            FROM projects WHERE processed = 1 
            GROUP BY category
            ORDER BY COUNT(*) DESC
        """)
        category_stats = dict(cursor.fetchall())

        # Migration category breakdown
        cursor.execute("""
            SELECT category, COUNT(*) 
            FROM projects WHERE migrated = 1 
            GROUP BY category
            ORDER BY COUNT(*) DESC
        """)
        migrated_category_stats = dict(cursor.fetchall())

        # Timeline data
        cursor.execute("""
            SELECT DATE(migration_date), COUNT(*) 
            FROM projects WHERE migrated = 1 AND migration_date IS NOT NULL
            GROUP BY DATE(migration_date)
            ORDER BY DATE(migration_date) DESC
            LIMIT 7
        """)
        timeline_data = cursor.fetchall()

        # Top recent migrations
        cursor.execute("""
            SELECT project_name, category, migration_date, target_path
            FROM projects WHERE migrated = 1
            ORDER BY migration_date DESC
            LIMIT 10
        """)
        recent_migrations = cursor.fetchall()

        # Failed migrations
        cursor.execute("""
            SELECT project_name, category, migration_error
            FROM projects WHERE migration_failed = 1
            ORDER BY migration_date DESC
            LIMIT 10
        """)
        failed_migrations = cursor.fetchall()

        return {
            "total_analyzed": total_analyzed,
            "total_processed": total_processed,
            "migrated_count": migrated_count,
            "failed_count": failed_count,
            "remaining_count": remaining_count,
            "migration_success_rate": migration_success_rate,
            "migrated_file_size_gb": round(migrated_file_size / (1024**3), 2),
            "migrated_audio_size_gb": round(migrated_audio_size / (1024**3), 2),
            "category_stats": category_stats,
            "migrated_category_stats": migrated_category_stats,
            "timeline_data": timeline_data,
            "recent_migrations": recent_migrations,
            "failed_migrations": failed_migrations,
        }

    def get_current_progress(self):
        """Get current progress from progress file"""
        try:
            if Path(self.progress_file).exists():
                with open(self.progress_file, "r") as f:
                    return f.read().strip()
        except IOError:
            pass
        return "No progress information available"

    def calculate_eta(self, stats):
        """Calculate estimated time remaining"""
        if stats["remaining_count"] == 0:
            return "Complete"

        # Get migration rate from recent timeline
        if len(stats["timeline_data"]) >= 2:
            recent_days = min(3, len(stats["timeline_data"]))
            total_migrated_recent = sum(
                count for _, count in stats["timeline_data"][-recent_days:]
            )
            daily_rate = total_migrated_recent / recent_days

            if daily_rate > 0:
                days_remaining = math.ceil(stats["remaining_count"] / daily_rate)
                return f"{days_remaining} days (at {daily_rate:.1f} projects/day)"

        return "Unknown (insufficient data)"

    def generate_ascii_dashboard(self, stats):
        """Generate ASCII dashboard display"""
        progress = self.get_current_progress()
        eta = self.calculate_eta(stats)

        # Progress bar
        if stats["total_processed"] > 0:
            completion_percent = (
                stats["migrated_count"] / stats["total_processed"]
            ) * 100
            bar_length = 40
            filled_length = int(bar_length * completion_percent / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            progress_line = f"[{bar}] {completion_percent:.1f}%"
        else:
            progress_line = "No projects processed"

        dashboard = f"""
╔══════════════════════════════════════════════════════════════╗
║                    MIGRATION DASHBOARD                      ║
╠══════════════════════════════════════════════════════════════╣
║ Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S"):>46} ║
║ Current: {progress[:43]:43} ║
║ ETA: {eta:>49} ║
╠══════════════════════════════════════════════════════════════╣
║                        STATISTICS                           ║
╠══════════════════════════════════════════════════════════════╣
║ Total Analyzed: {stats["total_analyzed"]:>42} ║
║ Total Processed: {stats["total_processed"]:>42} ║
║ Successfully Migrated: {stats["migrated_count"]:>35} ║
║ Failed Migrations: {stats["failed_count"]:>38} ║
║ Remaining: {stats["remaining_count"]:>46} ║
║ Success Rate: {stats["migration_success_rate"]:>42}% ║
╠══════════════════════════════════════════════════════════════╣
║                     STORAGE USAGE                            ║
╠══════════════════════════════════════════════════════════════╣
║ Migrated File Size: {stats["migrated_file_size_gb"]:>37.2f} GB ║
║ Migrated Audio Size: {stats["migrated_audio_size_gb"]:>34.2f} GB ║
╠══════════════════════════════════════════════════════════════╣
║                    PROGRESS BAR                              ║
╠══════════════════════════════════════════════════════════════╣
║ {progress_line:58} ║
╠══════════════════════════════════════════════════════════════╣
║                  CATEGORY BREAKDOWN                         ║
╠══════════════════════════════════════════════════════════════╣
"""

        # Add category breakdown
        for category, count in list(stats["category_stats"].items())[:6]:
            category_name = category.replace("_", " ").title()
            migrated_count = stats["migrated_category_stats"].get(category, 0)
            remaining = count - migrated_count
            dashboard += f"║ {category_name:<24}: {migrated_count:>3}/{count:<3} ({remaining:>3} remaining) ║\n"

        dashboard += f"""
╠══════════════════════════════════════════════════════════════╣
║                 RECENT MIGRATIONS                           ║
╠══════════════════════════════════════════════════════════════╣
"""

        # Add recent migrations
        for name, category, migration_date, target_path in stats["recent_migrations"][
            :5
        ]:
            # Truncate long names
            display_name = name[:35] + "..." if len(name) > 35 else name
            dashboard += f"║ {display_name:<43} {category:<12} ║\n"

        if len(stats["recent_migrations"]) == 0:
            dashboard += f"║ {'No recent migrations':^58} ║\n"

        if stats["failed_count"] > 0:
            dashboard += f"""
╠══════════════════════════════════════════════════════════════╣
║                  FAILED MIGRATIONS                          ║
╠══════════════════════════════════════════════════════════════╣
"""
            for name, category, error in stats["failed_migrations"][:3]:
                display_name = name[:35] + "..." if len(name) > 35 else name
                display_error = (
                    error[:18] + "..."
                    if error and len(error) > 18
                    else (error or "Unknown error")
                )
                dashboard += f"║ {display_name:<35} {display_error:<20} ║\n"

        dashboard += "╚══════════════════════════════════════════════════════════════╝"

        return dashboard

    def save_json_report(self, stats):
        """Save detailed JSON report"""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "statistics": stats,
            "current_progress": self.get_current_progress(),
            "eta": self.calculate_eta(stats),
        }

        json_path = Path("reports/dashboard_data.json")
        json_path.parent.mkdir(parents=True, exist_ok=True)

        with open(json_path, "w") as f:
            json.dump(report_data, f, indent=2)

        return json_path

    def watch_mode(self, refresh_interval=30):
        """Run dashboard in watch mode"""
        try:
            while True:
                # Clear screen
                os.system("clear" if os.name == "posix" else "cls")

                # Get stats and display
                stats = self.get_migration_statistics()
                dashboard = self.generate_ascii_dashboard(stats)
                print(dashboard)

                # Save JSON report
                self.save_json_report(stats)

                print(
                    f"\nRefreshing every {refresh_interval} seconds. Press Ctrl+C to exit."
                )
                time.sleep(refresh_interval)

        except KeyboardInterrupt:
            print("\n\nDashboard monitoring stopped.")

    def single_run(self):
        """Run dashboard once"""
        stats = self.get_migration_statistics()

        # Print ASCII dashboard
        dashboard = self.generate_ascii_dashboard(stats)
        print(dashboard)

        # Save reports
        json_path = self.save_json_report(stats)

        # Generate detailed text report
        text_report = self.generate_text_report(stats)
        text_path = Path("reports/dashboard_report.txt")
        with open(text_path, "w") as f:
            f.write(text_report)

        print(f"\nReports saved:")
        print(f"  JSON: {json_path}")
        print(f"  Text: {text_path}")

    def generate_text_report(self, stats):
        """Generate detailed text report"""
        progress = self.get_current_progress()
        eta = self.calculate_eta(stats)

        report = f"""
ABLETON PROJECT MIGRATION REPORT
================================
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Current Progress: {progress}
Estimated Time Remaining: {eta}

EXECUTIVE SUMMARY
----------------
Total Projects Analyzed: {stats["total_analyzed"]}
Total Projects Processed: {stats["total_processed"]}
Successfully Migrated: {stats["migrated_count"]}
Failed Migrations: {stats["failed_count"]}
Remaining Projects: {stats["remaining_count"]}
Migration Success Rate: {stats["migration_success_rate"]}%

STORAGE ANALYSIS
----------------
Total Migrated File Size: {stats["migrated_file_size_gb"]:.2f} GB
Migrated Audio Content: {stats["migrated_audio_size_gb"]:.2f} GB
Average Project Size: {stats["migrated_file_size_gb"] / max(1, stats["migrated_count"]):.2f} GB

CATEGORY BREAKDOWN
-----------------
"""

        for category, total in stats["category_stats"].items():
            migrated = stats["migrated_category_stats"].get(category, 0)
            remaining = total - migrated
            percentage = (migrated / total) * 100 if total > 0 else 0

            report += f"""
{category.replace("_", " ").title()}:
  Total: {total}
  Migrated: {migrated} ({percentage:.1f}%)
  Remaining: {remaining}
"""

        if stats["timeline_data"]:
            report += "\nDAILY MIGRATION ACTIVITY\n------------------------\n"
            for date, count in stats["timeline_data"]:
                report += f"{date}: {count} projects\n"

        if stats["recent_migrations"]:
            report += "\nRECENT SUCCESSFUL MIGRATIONS\n------------------------------\n"
            for name, category, migration_date, target_path in stats[
                "recent_migrations"
            ]:
                report += f"{name} ({category}) - {migration_date}\n"
                report += f"  Target: {target_path}\n\n"

        if stats["failed_migrations"]:
            report += "\nFAILED MIGRATIONS\n-----------------\n"
            for name, category, error in stats["failed_migrations"]:
                report += f"{name} ({category}) - {error}\n\n"

        return report


def main():
    parser = argparse.ArgumentParser(
        description="Migration progress dashboard for Ableton projects"
    )
    parser.add_argument(
        "--database", default="database/projects.db", help="Database file path"
    )
    parser.add_argument("--progress-file", help="Progress file path")
    parser.add_argument("--watch", action="store_true", help="Run in watch mode")
    parser.add_argument(
        "--refresh",
        type=int,
        default=30,
        help="Refresh interval for watch mode (seconds)",
    )
    parser.add_argument("--output", help="Output file for ASCII dashboard")

    args = parser.parse_args()

    dashboard = MigrationDashboard(args.database, args.progress_file)

    if args.watch:
        print("Starting migration dashboard in watch mode...")
        dashboard.watch_mode(args.refresh)
    else:
        dashboard.single_run()

        if args.output:
            stats = dashboard.get_migration_statistics()
            ascii_dashboard = dashboard.generate_ascii_dashboard(stats)
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                f.write(ascii_dashboard)
            print(f"ASCII dashboard saved to: {args.output}")


if __name__ == "__main__":
    main()
