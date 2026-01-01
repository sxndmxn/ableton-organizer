# Ableton Project Organizer

Complete automation suite for organizing 1000+ Ableton projects with production-first priority and NAS integration.

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/sxndmxn/ableton-organizer.git
cd ableton-organizer

# Install dependencies
./install_system_deps.sh
python3 install_dependencies.py

# Quick test (no real drives needed)
./quick_test.sh

# Real usage with your paths
python3 workflow.py \
  --source "/path/to/your/ableton/drive/Ableton/Projects" \
  --nas "/path/to/your/nas" \
  --complete
```

## Directory Structure

Your source drive should contain:
```
/path/to/your/drive/
├── Ableton/
│   ├── Projects/           # Your .als files (will be organized)
│   ├── Sample Packs/       # Left alone
│   └── Soulseek/          # Your music library (will be organized)
```

## What It Does

### Phase 1: Analysis
- Scans all `.als` files automatically
- Extracts metadata: track count, plugins, complexity, BPM, duration
- Analyzes project completion status and file relationships
- Creates intelligent project database

### Phase 2: Classification
- Categorizes projects into 6 smart categories:
  - **Production Ready** (highest priority)
  - **Active Production**
  - **Finished Experiments**  
  - **Development**
  - **Complex Sketches**
  - **Simple Ideas** (lowest priority)
- Calculates usage priority for migration ordering

### Phase 3: NAS Structure
- Creates production-first directory structure on your NAS
- Sets up organized directories for music and samples
- Creates maintenance scripts and documentation
- Prepares Jellyfin integration paths

### Phase 4: Migration
- Migrates projects in priority order
- Parallel processing with integrity verification
- Checksum verification for every file transfer
- Rollback capability and error recovery

### Phase 5: Dashboard
- Real-time migration monitoring
- ASCII dashboard with progress bars
- JSON API for integration
- Detailed reporting and analytics

## Advanced Usage

### Run Specific Phases
```bash
python3 workflow.py --source "/path/to/source" --nas "/path/to/nas" --phase 1  # Analysis only
python3 workflow.py --source "/path/to/source" --nas "/path/to/nas" --phase 2  # Classification only
python3 workflow.py --source "/path/to/source" --nas "/path/to/nas" --phase 3  # NAS structure only
```

### Migration Options
```bash
# Test migration without moving files
python3 workflow.py --source "/source" --nas "/nas" --phase 4 --dry-run

# Migrate specific category only
python3 workflow.py --source "/source" --nas "/nas" --phase 4 --category production_ready

# Limit to specific number of projects
python3 workflow.py --source "/source" --nas "/nas" --phase 4 --limit 50
```

### Dashboard Monitoring
```bash
# One-time dashboard report
python3 workflow.py --source "/source" --nas "/nas" --phase 5

# Real-time monitoring (updates every 30 seconds)
python3 workflow.py --source "/source" --nas "/nas" --phase 5 --watch

# Custom refresh interval
python3 workflow.py --source "/source" --nas "/nas" --phase 5 --watch --refresh 60
```

## Individual Scripts

All scripts can be run independently for fine-grained control:

### Project Scanner
```bash
python3 scripts/project_scanner.py --source "/path/to/projects" --database "database/projects.db"
```

### Project Classifier  
```bash
python3 scripts/project_classifier.py --database "database/projects.db" --show-queue
```

### NAS Structure Creator
```bash
python3 scripts/nas_structure_creator.py --nas-root "/nas/ableton-projects"
```

### Migration Script
```bash
bash scripts/migrate_to_nas.sh --category production_ready --limit 25
```

### Migration Dashboard
```bash
python3 scripts/migration_dashboard.py --database "database/projects.db" --watch
```

## Safety Features

- **Incremental migration**: Process in batches, pause anytime
- **Checksum verification**: Every file verified after transfer
- **Backup creation**: Automatic backups before migration
- **Rollback capability**: Full rollback if needed
- **Parallel processing**: Efficient but controlled transfers
- **Comprehensive logging**: Detailed logs for troubleshooting

## Reports and Analytics

The system generates comprehensive reports:

- **Analysis Report**: Project complexity and completion breakdown
- **Classification Report**: Category distribution and migration priority
- **Structure Report**: Created directories and configuration
- **Migration Report**: Transfer statistics and success rates
- **Dashboard Data**: Real-time JSON API for integration

## Integration with Your Setup

### Jellyfin Integration
- Export-ready directory structure: `08_EXPORTS_FOR_JELLYFIN/`
- Automatic metadata and organization
- Artist/album structure for media server compatibility

### Music Library Organization
- Organizes Soulseek downloads by genre, tempo, mood
- Creates resampling-friendly structure
- Separates production samples from listening library

### Sample Pack Integration
- Organizes commercial sample packs
- Creates producer-friendly directory structure
- Maintains original licensing information

## Configuration

### Environment Variables
```bash
# Optional - override in configs/migration_config.sh
SOURCE_DIR="/media/ableton-projects"
NAS_ROOT="/nas/ableton-projects"  
BATCH_SIZE="25"
PARALLEL_JOBS="4"
DRY_RUN="false"
```

### Custom Categories
Edit `configs/nas_structure.json` to customize:
- Category descriptions
- Directory structures
- Priority levels
- Subdirectory organization

## Troubleshooting

### Common Issues

**Source directory not found**
- Ensure external drive is connected and mounted
- Check path accuracy in command
- Verify drive permissions

**Migration failures**
- Run with `--dry-run` first
- Check `logs/migration.log` for errors
- Verify disk space on NAS

**Database errors**
- Delete `database/projects.db` and restart
- Ensure Python sqlite3 module is available
- Check file permissions

### Logs Location
All logs saved to `logs/` directory:
- `workflow.log` - Main workflow execution
- `scanner.log` - Project analysis details
- `classifier.log` - Classification decisions
- `migration.log` - Transfer operations
- `nas_organizer.log` - Structure creation

### Reports Location
All reports saved to `reports/` directory:
- `analysis_report.txt` - Project analysis results
- `classification_report.txt` - Category breakdown
- `migration_report.txt` - Transfer statistics
- `dashboard_report.txt` - Real-time status

## Next Steps After Setup

1. **Run complete workflow** with your actual paths
2. **Review reports** in `reports/` directory
3. **Monitor migration** with dashboard `--watch` mode
4. **Configure Jellyfin** to point at organized exports
5. **Set up backup schedules** using provided scripts
6. **Customize categories** as needed for your workflow

## Production-First Philosophy

This system prioritizes your most valuable projects first:

1. **Production Ready** - Complete tracks, immediate access
2. **Active Production** - Current work you're developing
3. **Finished Experiments** - Complete but experimental work
4. **Development** - Works in progress
5. **Complex Sketches** - Promising ideas needing work
6. **Simple Ideas** - Basic concepts and inspiration

This ensures your most important and valuable projects are accessible first, with less important material organized later.

## Support

For issues or questions:
1. Check `logs/` directory for detailed error information
2. Review `SETUP_INSTRUCTIONS.txt` generated after first run
3. Use `--dry-run` mode to test without file changes
4. Run individual phases to isolate issues

The system is designed to be robust and recoverable, with comprehensive logging and rollback capabilities at every step.