#!/bin/bash
# Quick Test Script for Ableton Organizer
# Tests the workflow without actual file operations

set -e

echo "=================================="
echo "ABLETON ORGANIZER QUICK TEST"
echo "=================================="

# Test configuration
BASE_DIR="$(pwd)/test_organizer"
SOURCE_DIR="$(pwd)/test_source"
NAS_DIR="$(pwd)/test_nas"

echo "Creating test environment..."

# Clean up previous test
rm -rf "$BASE_DIR" "$SOURCE_DIR" "$NAS_DIR"

# Create test structure
mkdir -p "$BASE_DIR"
mkdir -p "$SOURCE_DIR/Ableton/Projects"
mkdir -p "$SOURCE_DIR/Ableton/Sample Packs"
mkdir -p "$SOURCE_DIR/Ableton/Soulseek"
mkdir -p "$NAS_DIR"

# Create fake Ableton projects for testing
cat > "$SOURCE_DIR/Ableton/Projects/test_project_1.als" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="11" MinorVersion="3">
  <Tracks>
    <Track Id="1">
      <Name>Test Track</Name>
      <DeviceChain>
        <Main>
          <AudioEffect>
            <Name>Reverb</Name>
          </AudioEffect>
          <PluginDevice>
            <Name>Compressor</Name>
          </PluginDevice>
        </Main>
      </DeviceChain>
    </Track>
    <Track Id="2">
      <Name>Bass</Name>
    </Track>
  </Tracks>
  <MasterTrack>
    <Tempo>
      <Manual Value="120.0"/>
    </Tempo>
  </MasterTrack>
</Ableton>
EOF

# Create a second project with different characteristics
cat > "$SOURCE_DIR/Ableton/Projects/simple_idea.als" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="11" MinorVersion="3">
  <Tracks>
    <Track Id="1">
      <Name>Idea</Name>
    </Track>
  </Tracks>
  <MasterTrack>
    <Tempo>
      <Manual Value="128.0"/>
    </Tempo>
  </MasterTrack>
</Ableton>
EOF

echo "Test environment created:"
echo "  Base: $BASE_DIR"
echo "  Source: $SOURCE_DIR"
echo "  NAS: $NAS_DIR"

echo ""
echo "Running workflow test..."

# Test prerequisites
python3 workflow.py \
  --source "$SOURCE_DIR/Ableton/Projects" \
  --nas "$NAS_DIR" \
  --base "$BASE_DIR" \
  --test-prereqs

echo ""
echo "Running complete workflow (dry run)..."

# Run complete workflow
python3 workflow.py \
  --source "$SOURCE_DIR/Ableton/Projects" \
  --nas "$NAS_DIR" \
  --base "$BASE_DIR" \
  --complete

echo ""
echo "Test completed! Check results:"
echo "  Database: $BASE_DIR/database/projects.db"
echo "  Reports: $BASE_DIR/reports/"
echo "  Logs: $BASE_DIR/logs/"

echo ""
echo "Viewing dashboard results..."
python3 workflow.py \
  --source "$SOURCE_DIR/Ableton/Projects" \
  --nas "$NAS_DIR" \
  --base "$BASE_DIR" \
  --phase 5

echo ""
echo "Test complete! Clean up with:"
echo "rm -rf $BASE_DIR $SOURCE_DIR $NAS_DIR"