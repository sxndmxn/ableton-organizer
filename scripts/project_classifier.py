#!/usr/bin/env python3
"""
Project Classifier
Categorizes analyzed projects into smart categories for NAS organization
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import math


class ProjectClassifier:
    def __init__(self, db_path, log_path=None):
        self.db_path = db_path
        self.log_path = log_path or "logs/classifier.log"
        self.conn = sqlite3.connect(db_path)
        self.ensure_log_directory()
        self.category_definitions = self.define_categories()

    def ensure_log_directory(self):
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def log_message(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        print(log_entry.strip())

        if self.log_path:
            with open(self.log_path, "a") as f:
                f.write(log_entry)

    def define_categories(self):
        """Define category rules and characteristics"""
        return {
            "production_ready": {
                "description": "Complete projects ready for release/mixing",
                "completion_required": ["complete"],
                "complexity_min": 60,
                "complexity_max": 100,
                "duration_min": 120,  # 2+ minutes
                "priority_multiplier": 1.0,
            },
            "active_production": {
                "description": "High-quality works in progress with substance",
                "completion_required": ["work_in_progress"],
                "complexity_min": 40,
                "complexity_max": 100,
                "duration_min": 60,  # 1+ minutes
                "priority_multiplier": 0.8,
            },
            "finished_experiments": {
                "description": "Complete but experimental/less commercial",
                "completion_required": ["complete"],
                "complexity_min": 0,
                "complexity_max": 60,
                "duration_min": 30,  # 30+ seconds
                "priority_multiplier": 0.6,
            },
            "development": {
                "description": "Works in progress with moderate complexity",
                "completion_required": ["work_in_progress"],
                "complexity_min": 20,
                "complexity_max": 70,
                "duration_min": 30,  # 30+ seconds
                "priority_multiplier": 0.4,
            },
            "complex_sketches": {
                "description": "Complex ideas that need development",
                "completion_required": ["sketch"],
                "complexity_min": 30,
                "complexity_max": 100,
                "duration_min": 0,
                "priority_multiplier": 0.3,
            },
            "simple_ideas": {
                "description": "Basic sketches and starting points",
                "completion_required": ["sketch"],
                "complexity_min": 0,
                "complexity_max": 30,
                "duration_min": 0,
                "priority_multiplier": 0.1,
            },
        }

    def classify_all_projects(self):
        """Classify all unprocessed projects"""
        self.log_message("Starting project classification")

        # Reset processed status for fresh classification
        self.conn.execute(
            "UPDATE projects SET processed = 0, category = NULL, usage_priority = 0"
        )
        self.conn.commit()

        projects = self.get_unclassified_projects()
        self.log_message(f"Found {len(projects)} projects to classify")

        classification_stats = {}

        for project in projects:
            category = self.determine_category(project)
            priority = self.calculate_priority(project, category)

            self.update_project_classification(project["id"], category, priority)

            # Track statistics
            if category not in classification_stats:
                classification_stats[category] = 0
            classification_stats[category] += 1

        self.conn.commit()
        self.log_message(f"Classification complete. Processed {len(projects)} projects")

        # Log breakdown
        for category, count in classification_stats.items():
            self.log_message(f"  {category}: {count} projects")

        self.generate_classification_report()

    def get_unclassified_projects(self):
        """Get all analyzed but unprocessed projects"""
        cursor = self.conn.execute("""
            SELECT * FROM projects 
            WHERE analyzed = 1 AND (processed = 0 OR processed IS NULL)
            ORDER BY complexity_score DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def determine_category(self, project):
        """Determine the best category for a project"""
        completion_status = project["completion_status"]
        complexity = project["complexity_score"]
        duration = project["duration_seconds"]

        # Find matching categories
        matching_categories = []

        for category_name, category_rules in self.category_definitions.items():
            if completion_status in category_rules["completion_required"]:
                if (
                    category_rules["complexity_min"]
                    <= complexity
                    <= category_rules["complexity_max"]
                    and duration >= category_rules["duration_min"]
                ):
                    matching_categories.append(category_name)

        # Special cases for edge scenarios
        if not matching_categories:
            # Fallback logic
            if completion_status == "complete":
                if complexity > 50:
                    return "production_ready"
                else:
                    return "finished_experiments"
            elif completion_status == "work_in_progress":
                if complexity > 40:
                    return "active_production"
                else:
                    return "development"
            else:  # sketch
                if complexity > 30:
                    return "complex_sketches"
                else:
                    return "simple_ideas"

        # Return highest priority match
        return matching_categories[0]

    def calculate_priority(self, project, category):
        """Calculate usage priority (0-100) for migration ordering"""
        base_score = 50  # Start at middle

        # Category-based priority
        category_multiplier = self.category_definitions[category]["priority_multiplier"]
        category_score = base_score * category_multiplier

        # Complexity factor (more complex = higher priority)
        complexity_bonus = (project["complexity_score"] / 100) * 20

        # Duration factor (longer = more substance = higher priority)
        duration_minutes = project["duration_seconds"] / 60
        duration_bonus = min(10, duration_minutes / 6)  # Max 10 points for 6+ minutes

        # Audio content factor (projects with more audio recordings = higher priority)
        audio_size_gb = project["audio_folder_size"] / (1024**3)
        audio_bonus = min(15, audio_size_gb * 5)  # Max 15 points

        # Track count factor (more tracks = more developed = higher priority)
        track_bonus = min(10, project["track_count"] / 2)

        # Recency factor (more recent = higher priority)
        try:
            last_modified = datetime.fromisoformat(project["last_modified"])
            days_old = (datetime.now() - last_modified).days
            recency_bonus = max(0, 10 - (days_old / 30))  # Decay over months
        except (ValueError, TypeError):
            recency_bonus = 0

        # Final priority calculation
        final_priority = (
            category_score
            + complexity_bonus
            + duration_bonus
            + audio_bonus
            + track_bonus
            + recency_bonus
        )

        # Ensure 0-100 range
        final_priority = max(0, min(100, final_priority))

        return int(final_priority)

    def update_project_classification(self, project_id, category, priority):
        """Update project with classification and priority"""
        self.conn.execute(
            """
            UPDATE projects 
            SET category = ?, usage_priority = ?, processed = 1
            WHERE id = ?
        """,
            (category, priority, project_id),
        )

    def generate_classification_report(self):
        """Generate detailed classification report"""
        cursor = self.conn.cursor()

        # Get classification statistics
        cursor.execute("""
            SELECT category, COUNT(*), AVG(complexity_score), AVG(usage_priority)
            FROM projects WHERE processed = 1
            GROUP BY category
            ORDER BY COUNT(*) DESC
        """)

        category_stats = cursor.fetchall()

        # Get top projects by priority
        cursor.execute("""
            SELECT project_name, category, usage_priority, complexity_score, completion_status
            FROM projects WHERE processed = 1
            ORDER BY usage_priority DESC
            LIMIT 20
        """)

        top_projects = cursor.fetchall()

        # Generate report
        report = f"""
PROJECT CLASSIFICATION REPORT
============================
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

CATEGORY BREAKDOWN
------------------
"""

        for category, count, avg_complexity, avg_priority in category_stats:
            category_desc = self.category_definitions.get(category, {}).get(
                "description", "No description"
            )
            report += f"""
{category.upper().replace("_", " ")} ({count} projects)
  Description: {category_desc}
  Average Complexity: {avg_complexity:.1f}
  Average Priority: {avg_priority:.1f}
"""

        report += """

TOP 20 PROJECTS BY PRIORITY
---------------------------
"""

        for i, (name, category, priority, complexity, completion) in enumerate(
            top_projects, 1
        ):
            report += f"{i:2d}. {name} ({category}) - Priority: {priority:3d}, Complexity: {complexity:5.1f}, Status: {completion}\n"

        # Migration queue by priority
        cursor.execute("""
            SELECT category, COUNT(*)
            FROM projects WHERE processed = 1
            GROUP BY category
            ORDER BY AVG(usage_priority) DESC
        """)

        migration_order = cursor.fetchall()

        report += "\n\nMIGRATION PRIORITY ORDER\n------------------------\n"
        for i, (category, count) in enumerate(migration_order, 1):
            report += f"{i}. {category.replace('_', ' ').title()}: {count} projects\n"

        # Save report
        report_path = Path("reports/classification_report.txt")
        with open(report_path, "w") as f:
            f.write(report)

        self.log_message(f"Classification report saved to: {report_path}")

        # Save JSON for dashboard
        stats_data = {"categories": {}, "total_projects": 0, "migration_order": []}

        for category, count, avg_complexity, avg_priority in category_stats:
            stats_data["categories"][category] = {
                "count": count,
                "avg_complexity": round(avg_complexity, 1),
                "avg_priority": round(avg_priority, 1),
                "description": self.category_definitions.get(category, {}).get(
                    "description", ""
                ),
            }
            stats_data["total_projects"] += count

        stats_data["migration_order"] = [cat[0] for cat in migration_order]

        json_path = Path("reports/classification_data.json")
        with open(json_path, "w") as f:
            json.dump(stats_data, f, indent=2)

        self.log_message(f"Classification data saved to: {json_path}")

    def get_migration_queue(self, category=None, limit=None):
        """Get migration queue ordered by priority"""
        query = """
            SELECT file_path, category, usage_priority, complexity_score, project_name
            FROM projects WHERE processed = 1
        """
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY usage_priority DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def main():
    parser = argparse.ArgumentParser(
        description="Classify Ableton projects for NAS organization"
    )
    parser.add_argument(
        "--database", default="database/projects.db", help="Database file path"
    )
    parser.add_argument("--log", default="logs/classifier.log", help="Log file path")
    parser.add_argument(
        "--show-queue", action="store_true", help="Show migration queue and exit"
    )
    parser.add_argument("--category", help="Filter queue by category")
    parser.add_argument("--limit", type=int, help="Limit queue output")

    args = parser.parse_args()

    classifier = ProjectClassifier(args.database, args.log)

    if args.show_queue:
        queue = classifier.get_migration_queue(args.category, args.limit)
        print(f"\nMIGRATION QUEUE ({len(queue)} projects)")
        print("=" * 50)

        for i, project in enumerate(queue, 1):
            print(f"{i:3d}. {project['project_name']}")
            print(f"     Category: {project['category']}")
            print(
                f"     Priority: {project['usage_priority']} | Complexity: {project['complexity_score']:.1f}"
            )
            print(f"     Path: {project['file_path']}")
            print()
    else:
        classifier.classify_all_projects()


if __name__ == "__main__":
    main()
