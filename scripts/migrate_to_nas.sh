#!/bin/bash
# Batch Migration Script for Ableton Projects
# Production-first migration with verification and logging

set -euo pipefail  # Strict error handling

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../configs/migration_config.sh"
DATABASE_PATH="${SCRIPT_DIR}/../database/projects.db"
LOG_FILE="${SCRIPT_DIR}/../logs/migration.log"
MIGRATION_LOG="${SCRIPT_DIR}/../logs/detailed_migration.log"
PROGRESS_FILE="${SCRIPT_DIR}/../temp/migration_progress.txt"

# Source configuration if exists
if [[ -f "$CONFIG_FILE" ]]; then
    source "$CONFIG_FILE"
fi

# Default configuration (can be overridden in config file)
SOURCE_DIR="${SOURCE_DIR:-/media/ableton-projects}"
NAS_ROOT="${NAS_ROOT:-/nas/ableton-projects}"
BATCH_SIZE="${BATCH_SIZE:-25}"
PARALLEL_JOBS="${PARALLEL_JOBS:-4}"
DRY_RUN="${DRY_RUN:-false}"
BACKUP_BEFORE_MIGRATE="${BACKUP_BEFORE_MIGRATE:-true}"

# Ensure directories exist
mkdir -p "$(dirname "$LOG_FILE")"
mkdir - "$(dirname "$MIGRATION_LOG")"
mkdir -p "$(dirname "$PROGRESS_FILE")"

# Logging functions
log_message() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_debug() { log_message "DEBUG" "$@"; }
log_info() { log_message "INFO" "$@"; }
log_warn() { log_message "WARN" "$@"; }
log_error() { log_message "ERROR" "$@"; }

# Progress tracking
update_progress() {
    local current="$1"
    local total="$2"
    local message="$3"
    
    echo "$current/$total - $message" > "$PROGRESS_FILE"
    log_info "Progress: $current/$total - $message"
}

# Database query functions
get_migration_queue() {
    local limit="${1:-$BATCH_SIZE}"
    local category_filter="$2"
    
    local query="
        SELECT file_path, category, usage_priority, complexity_score, project_name, id
        FROM projects 
        WHERE processed = 1 AND migrated = 0"
    
    if [[ -n "$category_filter" ]]; then
        query="$query AND category = '$category_filter'"
    fi
    
    query="$query ORDER BY usage_priority DESC LIMIT $limit"
    
    sqlite3 "$DATABASE_PATH" "$query" 2>/dev/null || {
        log_error "Failed to query database"
        return 1
    }
}

mark_project_migrated() {
    local project_id="$1"
    local success="$2"
    local target_path="$3"
    
    if [[ "$success" == "true" ]]; then
        sqlite3 "$DATABASE_PATH" "UPDATE projects SET migrated = 1, migration_date = datetime('now'), target_path = '$target_path' WHERE id = $project_id"
    else
        sqlite3 "$DATABASE_PATH" "UPDATE projects SET migration_failed = 1, migration_error = '$target_path' WHERE id = $project_id"
    fi
}

get_total_projects() {
    sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM projects WHERE processed = 1 AND migrated = 0"
}

get_migrated_count() {
    sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM projects WHERE migrated = 1"
}

# Safety and verification functions
validate_environment() {
    log_info "Validating migration environment"
    
    # Check source directory
    if [[ ! -d "$SOURCE_DIR" ]]; then
        log_error "Source directory not found: $SOURCE_DIR"
        return 1
    fi
    
    # Check NAS directory
    if [[ ! -d "$NAS_ROOT" ]]; then
        log_error "NAS directory not found: $NAS_ROOT"
        return 1
    fi
    
    # Check database
    if [[ ! -f "$DATABASE_PATH" ]]; then
        log_error "Database not found: $DATABASE_PATH"
        return 1
    fi
    
    # Check available space
    local source_size=$(du -sb "$SOURCE_DIR" 2>/dev/null | cut -f1 || echo "0")
    local nas_free=$(df -B1 "$NAS_ROOT" 2>/dev/null | tail -1 | awk '{print $4}' || echo "0")
    
    log_info "Source size: $((source_size / 1024 / 1024 / 1024))GB"
    log_info "NAS free space: $((nas_free / 1024 / 1024 / 1024))GB"
    
    if [[ $nas_free -lt $((source_size / 2)) ]]; then
        log_warn "Low disk space on NAS. Consider freeing up space or using smaller batches."
    fi
    
    # Test write permissions
    local test_file="$NAS_ROOT/.migration_test_$$"
    if ! touch "$test_file" 2>/dev/null; then
        log_error "Cannot write to NAS directory: $NAS_ROOT"
        return 1
    fi
    rm -f "$test_file"
    
    log_info "Environment validation passed"
    return 0
}

create_backup() {
    if [[ "$BACKUP_BEFORE_MIGRATE" != "true" ]]; then
        return 0
    fi
    
    log_info "Creating backup before migration"
    local backup_dir="$NAS_ROOT/00_MAINTENANCE/backups/pre_migration_$(date +%Y%m%d_%H%M%S)"
    
    mkdir -p "$backup_dir"
    
    # Create quick backup of critical metadata
    if sqlite3 "$DATABASE_PATH" ".backup $backup_dir/projects_backup.db"; then
        log_info "Database backup created: $backup_dir/projects_backup.db"
    else
        log_warn "Failed to create database backup"
    fi
    
    return 0
}

# Migration functions
get_target_directory() {
    local category="$1"
    
    case "$category" in
        "production_ready") echo "01_PRODUCTION_READY" ;;
        "active_production") echo "02_ACTIVE_PRODUCTION" ;;
        "finished_experiments") echo "03_FINISHED_EXPERIMENTS" ;;
        "development") echo "04_DEVELOPMENT" ;;
        "complex_sketches") echo "05_COMPLEX_SKETCHES" ;;
        "simple_ideas") echo "06_SIMPLE_IDEAS" ;;
        *) echo "00_UNCATEGORIZED" ;;
    esac
}

migrate_single_project() {
    local file_path="$1"
    local category="$2"
    local project_name="$3"
    local project_id="$4"
    
    local target_dir_name
    target_dir_name=$(get_target_directory "$category")
    local target_dir="$NAS_ROOT/$target_dir_name"
    
    # Ensure target directory exists
    mkdir -p "$target_dir"
    
    # Determine target path
    local target_path="$target_dir/$project_name"
    
    # Handle filename conflicts
    local counter=1
    local original_target="$target_path"
    while [[ -e "$target_path" ]]; do
        target_path="${original_target}_${counter}"
        counter=$((counter + 1))
    done
    
    log_debug "Migrating: $file_path -> $target_path"
    
    # Perform migration with verification
    local success=false
    local error_message=""
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would copy $file_path to $target_path"
        mark_project_migrated "$project_id" "true" "$target_path"
        return 0
    fi
    
    # Use rsync with verification
    if rsync -av --progress --checksum \
        --exclude="*.tmp" \
        --exclude="*.bak" \
        "$file_path" "$target_path" 2>&1 | tee -a "$MIGRATION_LOG"; then
        
        # Verify file integrity
        if verify_file_integrity "$file_path" "$target_path"; then
            log_info "Successfully migrated: $project_name"
            success=true
        else
            error_message="Checksum verification failed"
            log_error "Verification failed for: $project_name"
        fi
    else
        error_message="rsync failed"
        log_error "Migration failed for: $project_name"
    fi
    
    mark_project_migrated "$project_id" "$success" "$error_message"
    
    # Remove source if migration successful and configured
    if [[ "$success" == "true" && "${REMOVE_SOURCE_AFTER_MIGRATION:-false}" == "true" ]]; then
        log_debug "Removing source: $file_path"
        rm -rf "$file_path"
    fi
    
    return $([[ "$success" == "true" ]] && echo 0 || echo 1)
}

verify_file_integrity() {
    local source="$1"
    local target="$2"
    
    # For directories, compare recursively
    if [[ -d "$source" ]]; then
        # Use rsync dry-run to check differences
        if ! rsync -anc --delete "$source/" "$target/" >/dev/null 2>&1; then
            return 1
        fi
    else
        # For single files, compare checksums
        local source_md5 source_target
        source_md5=$(md5sum "$source" 2>/dev/null | cut -d' ' -f1)
        target_md5=$(md5sum "$target" 2>/dev/null | cut -d' ' -f1)
        
        if [[ "$source_md5" != "$target_md5" ]]; then
            return 1
        fi
    fi
    
    return 0
}

# Batch processing functions
process_batch() {
    local batch_data="$1"
    local batch_total="$2"
    local current_total="$3"
    
    echo "$batch_data" | while IFS='|' read -r file_path category priority complexity project_name project_id; do
        [[ -z "$file_path" ]] && continue
        
        log_info "Processing: $project_name (Priority: $priority, Complexity: $complexity)"
        
        if migrate_single_project "$file_path" "$category" "$project_name" "$project_id"; then
            update_progress $((current_total + 1)) "$batch_total" "$project_name"
        else
            log_error "Failed to migrate: $project_name"
        fi
        
        current_total=$((current_total + 1))
    done
}

run_parallel_migration() {
    local category_filter="$1"
    local batch_limit="${2:-0}"
    
    local total_projects
    total_projects=$(get_total_projects)
    
    if [[ $total_projects -eq 0 ]]; then
        log_info "No projects to migrate"
        return 0
    fi
    
    log_info "Starting parallel migration"
    log_info "Total projects to migrate: $total_projects"
    log_info "Batch size: $BATCH_SIZE"
    log_info "Parallel jobs: $PARALLEL_JOBS"
    
    local processed_count=0
    
    while [[ $processed_count -lt $total_projects ]]; do
        local limit=$BATCH_SIZE
        if [[ $batch_limit -gt 0 && $((processed_count + BATCH_SIZE)) -gt $batch_limit ]]; then
            limit=$((batch_limit - processed_count))
        fi
        
        if [[ $limit -le 0 ]]; then
            break
        fi
        
        log_info "Processing batch: $((processed_count + 1))-$((processed_count + limit)) of $total_projects"
        
        # Get next batch
        local batch_data
        batch_data=$(get_migration_queue "$limit" "$category_filter")
        
        if [[ -z "$batch_data" ]]; then
            log_info "No more projects to process"
            break
        fi
        
        # Process batch
        echo "$batch_data" | while IFS='|' read -r file_path category priority complexity project_name project_id; do
            [[ -z "$file_path" ]] && continue
            
            # Run migration in background
            migrate_single_project "$file_path" "$category" "$project_name" "$project_id" &
            
            # Limit parallel jobs
            if [[ $(jobs -r -p | wc -l) -ge $PARALLEL_JOBS ]]; then
                wait -n
            fi
            
            processed_count=$((processed_count + 1))
            update_progress "$processed_count" "$total_projects" "$project_name"
        done
        
        # Wait for all background jobs to complete
        wait
        
        # Small delay between batches
        sleep 2
    done
    
    log_info "Migration batch completed. Processed: $processed_count/$total_projects"
}

# Reporting functions
generate_migration_report() {
    local total_projects migrated_projects failed_projects
    total_projects=$(sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM projects WHERE processed = 1")
    migrated_projects=$(get_migrated_count)
    failed_projects=$(sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM projects WHERE migration_failed = 1")
    
    local success_rate=0
    if [[ $total_projects -gt 0 ]]; then
        success_rate=$(( (migrated_projects * 100) / total_projects ))
    fi
    
    local report="
MIGRATION REPORT
===============
Generated: $(date)
Source Directory: $SOURCE_DIR
NAS Directory: $NAS_ROOT

SUMMARY
-------
Total Analyzed Projects: $total_projects
Successfully Migrated: $migrated_projects
Failed Migrations: $failed_projects
Success Rate: ${success_rate}%

CATEGORY BREAKDOWN
-----------------
"
    
    # Add category breakdown
    while IFS='|' read -r category count; do
        [[ -z "$category" ]] && continue
        report+="$(echo "$category" | tr '_' ' ' | tr '[:lower:]' '[:upper:]'): $count projects\n"
    done <<< "$(sqlite3 "$DATABASE_PATH" "SELECT category, COUNT(*) FROM projects WHERE processed = 1 GROUP BY category")"
    
    report+="
RECENT MIGRATIONS
-----------------
"
    
    # Add recent migrations
    while IFS='|' read -r name date path; do
        [[ -z "$name" ]] && continue
        report+="$name - $date -> $path\n"
    done <<< "$(sqlite3 "$DATABASE_PATH" "SELECT project_name, migration_date, target_path FROM projects WHERE migrated = 1 ORDER BY migration_date DESC LIMIT 10")"
    
    echo -e "$report" > "${SCRIPT_DIR}/../reports/migration_report.txt"
    log_info "Migration report saved to: ${SCRIPT_DIR}/../reports/migration_report.txt"
    
    echo -e "$report"
}

# Main execution
main() {
    log_info "Starting Ableton project migration"
    
    # Validate environment
    if ! validate_environment; then
        log_error "Environment validation failed"
        exit 1
    fi
    
    # Create backup
    create_backup
    
    # Parse command line arguments
    local category_filter=""
    local batch_limit=0
    local show_help=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --category)
                category_filter="$2"
                shift 2
                ;;
            --limit)
                batch_limit="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --cleanup-only)
                # Only run cleanup, no migration
                cleanup_and_exit
                exit 0
                ;;
            --help|-h)
                show_help=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    if [[ "$show_help" == "true" ]]; then
        cat << EOF
Ableton Project Migration Script

Usage: $0 [OPTIONS]

OPTIONS:
  --category CATEGORY    Only migrate projects from this category
  --limit COUNT           Limit migration to COUNT projects
  --dry-run               Show what would be migrated without actual transfer
  --cleanup-only          Only run cleanup and exit
  --help, -h              Show this help message

EXAMPLES:
  $0                                    # Migrate all projects
  $0 --category production_ready        # Only migrate production-ready projects
  $0 --limit 50                        # Migrate only 50 projects
  $0 --category active_production --limit 25  # 25 active production projects
  $0 --dry-run                         # Test run without actual migration

ENVIRONMENT VARIABLES:
  SOURCE_DIR          Source directory containing Ableton projects
  NAS_ROOT            Target NAS directory
  BATCH_SIZE          Number of projects per batch (default: 25)
  PARALLEL_JOBS       Parallel migration jobs (default: 4)
  DRY_RUN             Set to 'true' for test run (default: false)
  BACKUP_BEFORE_MIGRATE  Create backup before migration (default: true)

CONFIGURATION:
  Override settings in: $CONFIG_FILE
EOF
        exit 0
    fi
    
    # Run migration
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN MODE - No files will be moved"
    fi
    
    run_parallel_migration "$category_filter" "$batch_limit"
    
    # Generate final report
    generate_migration_report
    
    log_info "Migration process completed"
}

# Cleanup function
cleanup_and_exit() {
    log_info "Performing cleanup"
    
    # Clean up temporary files
    find "${SCRIPT_DIR}/../temp" -name "*.tmp" -mtime +1 -delete 2>/dev/null || true
    
    # Compress old logs
    find "$(dirname "$LOG_FILE")" -name "*.log" -mtime +30 -exec gzip {} \; 2>/dev/null || true
    
    log_info "Cleanup completed"
}

# Trap for cleanup
trap cleanup_and_exit EXIT

# Run main function with all arguments
main "$@"