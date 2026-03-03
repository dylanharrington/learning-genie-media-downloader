#!/bin/bash
# update_dashboard.sh - Sync Learning Genie photos and update the family dashboard
#
# Fetches latest photos from Learning Genie, picks the most recent day's photos,
# resizes them for the dashboard, and copies to ~/clawd/dashboard/
#
# Usage:
#   ./update_dashboard.sh          # Full sync + dashboard update
#   ./update_dashboard.sh --skip-sync  # Just update dashboard from existing photos
#   ./update_dashboard.sh --deploy     # Full sync + dashboard update + vercel deploy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DASHBOARD_DIR="$HOME/clawd/dashboard"
PHOTOS_DIR="$SCRIPT_DIR/photos/home"
VENV="$SCRIPT_DIR/.venv/bin/python"
MAX_PHOTOS=5          # Max photos to put on dashboard
MAX_WIDTH=825         # Max width for dashboard photos (matches current)
QUALITY=85            # JPEG quality

SKIP_SYNC=false
DEPLOY=false

for arg in "$@"; do
    case $arg in
        --skip-sync) SKIP_SYNC=true ;;
        --deploy) DEPLOY=true ;;
    esac
done

echo "=== Learning Genie → Dashboard Update ==="
echo ""

# Step 1: Sync photos from Learning Genie
if [ "$SKIP_SYNC" = false ]; then
    echo "[1/3] Syncing photos from Learning Genie..."
    cd "$SCRIPT_DIR"
    "$VENV" sync.py 2>&1
    echo ""
else
    echo "[1/3] Skipping sync (--skip-sync)"
    echo ""
fi

# Step 2: Find the most recent school day's photos
echo "[2/3] Selecting latest photos for dashboard..."

# Get most recent date that has photos (excluding videos)
LATEST_DATE=$(ls "$PHOTOS_DIR"/*.jpg 2>/dev/null | \
    sed 's/.*_\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)_.*/\1/' | \
    sort -u | tail -1)

if [ -z "$LATEST_DATE" ]; then
    echo "  No photos found!"
    exit 1
fi

echo "  Latest photo date: $LATEST_DATE"

# Get photos from that date (only JPGs, not videos)
PHOTOS=($(ls "$PHOTOS_DIR"/*"${LATEST_DATE}"*.jpg 2>/dev/null | sort))
TOTAL=${#PHOTOS[@]}

echo "  Found $TOTAL photos from $LATEST_DATE"

# Select up to MAX_PHOTOS (spread evenly if more than MAX_PHOTOS)
if [ "$TOTAL" -le "$MAX_PHOTOS" ]; then
    SELECTED=("${PHOTOS[@]}")
else
    # Evenly space selection across available photos
    SELECTED=()
    for i in $(seq 0 $((MAX_PHOTOS - 1))); do
        IDX=$(( i * (TOTAL - 1) / (MAX_PHOTOS - 1) ))
        SELECTED+=("${PHOTOS[$IDX]}")
    done
fi

echo "  Selected ${#SELECTED[@]} photos for dashboard"

# Step 3: Resize and copy to dashboard
echo ""
echo "[3/3] Processing photos for dashboard..."

# Remove old school photos
rm -f "$DASHBOARD_DIR"/lucy-school-[0-9]*.jpg

for i in "${!SELECTED[@]}"; do
    SRC="${SELECTED[$i]}"
    NUM=$((i + 1))
    DST="$DASHBOARD_DIR/lucy-school-${NUM}.jpg"
    
    # Copy and resize using sips (macOS built-in)
    cp "$SRC" "$DST"
    sips --resampleWidth "$MAX_WIDTH" -s formatOptions "$QUALITY" "$DST" >/dev/null 2>&1
    
    SIZE=$(ls -lh "$DST" | awk '{print $5}')
    echo "  lucy-school-${NUM}.jpg ($SIZE) ← $(basename "$SRC")"
done

# Generate manifest JSON for dashboard
MANIFEST="$DASHBOARD_DIR/lucy-school-photos.json"
echo "{" > "$MANIFEST"
echo "  \"date\": \"$LATEST_DATE\"," >> "$MANIFEST"
echo "  \"count\": ${#SELECTED[@]}," >> "$MANIFEST"
echo "  \"updated\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$MANIFEST"
echo "  \"photos\": [" >> "$MANIFEST"
for i in "${!SELECTED[@]}"; do
    NUM=$((i + 1))
    COMMA=","
    [ "$NUM" -eq "${#SELECTED[@]}" ] && COMMA=""
    echo "    \"lucy-school-${NUM}.jpg\"${COMMA}" >> "$MANIFEST"
done
echo "  ]" >> "$MANIFEST"
echo "}" >> "$MANIFEST"
echo "  lucy-school-photos.json (manifest)"

# Step 3.5: Enrich manifest with activity captions from notes.json
echo "  Enriching manifest with activity captions..."
python3 - "$LATEST_DATE" "$MANIFEST" "$SCRIPT_DIR/data/notes.json" "$SCRIPT_DIR/data/message.json" << 'PYEOF'
import json, sys

date = sys.argv[1]
manifest_path = sys.argv[2]
notes_path = sys.argv[3]
messages_path = sys.argv[4]

with open(manifest_path) as f:
    manifest = json.load(f)

# Read activity notes
try:
    with open(notes_path) as f:
        notes = json.load(f)
except:
    notes = []

# Read teacher messages
try:
    with open(messages_path) as f:
        messages_data = json.load(f)
        messages = messages_data.get('items', [])
except:
    messages = []

# Find activities for this date (with meaningful descriptions)
activities = []
for note in notes:
    create_date = note.get('create_at', '')[:10]
    if create_date == date and note.get('payload'):
        payload = note['payload'].strip()
        if len(payload) > 10:  # Skip very short payloads
            activities.append({
                'description': payload,
                'type': note.get('type', 'Activity'),
                'time': note.get('create_at', '')[11:16],
            })

# Find teacher text messages for this date
teacher_msgs = []
for msg in messages:
    created = msg.get('created_at', '')[:10]
    if created == date and msg.get('message') and msg['message'] != '[image]':
        teacher_msgs.append({
            'message': msg['message'],
            'from': msg.get('user_name', 'Teacher'),
            'time': msg.get('created_at', '')[11:16],
        })

manifest['activities'] = activities
manifest['teacherMessages'] = teacher_msgs

with open(manifest_path, 'w') as f:
    json.dump(manifest, f, indent=2)

print(f"    {len(activities)} activities, {len(teacher_msgs)} teacher messages added")
PYEOF

echo ""
echo "✅ Dashboard updated with ${#SELECTED[@]} photos from $LATEST_DATE"
echo "   Photos in: $DASHBOARD_DIR/lucy-school-*.jpg"

# Step 4: Deploy if requested
if [ "$DEPLOY" = true ]; then
    echo ""
    echo "[4/4] Deploying dashboard..."
    cd "$DASHBOARD_DIR"
    vercel --prod 2>&1
    echo "✅ Dashboard deployed!"
fi

echo ""
echo "Done!"
