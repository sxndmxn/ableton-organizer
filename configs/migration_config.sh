# Migration Configuration
# Override defaults by editing this file

# Directories
SOURCE_DIR="/media/ableton-projects"
NAS_ROOT="/nas/ableton-projects"

# Migration Behavior
BATCH_SIZE="25"
PARALLEL_JOBS="4"
DRY_RUN="false"
BACKUP_BEFORE_MIGRATE="true"
REMOVE_SOURCE_AFTER_MIGRATION="false"

# Verification
ENABLE_CHECKSUM_VERIFICATION="true"
SKIP_CORRUPTED_FILES="true"

# Logging
DETAILED_LOGGING="true"
COMPRESS_OLD_LOGS="true"
LOG_RETENTION_DAYS="30"

# Performance
ENABLE_PARALLEL_PROCESSING="true"
MAX_MEMORY_USAGE="2G"
IO_TIMEOUT="300"