#!/usr/bin/env python3
"""
Download photos and videos from Learning Genie Chat tab (message.json).

Usage:
    ./scripts/download_chat.py data/message.json photos/chat
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Load location from config
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
from config import get_location

LOCATION = get_location()

# Time window (seconds) to look for associated text messages
TEXT_ASSOCIATION_WINDOW = 120


def check_exiftool(exiftool_path=None):
    """Check if exiftool is available."""
    cmd = exiftool_path or 'exiftool'
    try:
        subprocess.run([cmd, '-ver'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_thumbnail(url: str) -> bool:
    """Check if URL is a video thumbnail (ends with 'jpg' without a dot)."""
    return bool(re.search(r'[0-9a-f]jpg$', url))


def get_file_type(url: str) -> str:
    """Get file type from URL."""
    if url.endswith('.mp4'):
        return 'mp4'
    elif url.endswith('.png'):
        return 'jpg'  # These are actually JPEGs despite .png extension
    return 'bin'


def parse_iso_date(iso_str: str) -> str:
    """Convert ISO date to exiftool format: '2026-01-12T22:18:37Z' -> '2026:01:12 22:18:37'"""
    if not iso_str:
        return ''
    # Remove 'T' and 'Z', replace date dashes with colons
    return iso_str.replace('T', ' ').replace('Z', '').replace('-', ':', 2)


def find_associated_text(items, current_idx, sender_id, date_sent):
    """
    Find a text message from the same sender within the time window.
    Look both before and after in the list (messages are sorted by date descending).
    """
    for offset in range(1, 20):  # Look up to 20 messages away
        for direction in [-1, 1]:
            idx = current_idx + (offset * direction)
            if 0 <= idx < len(items):
                item = items[idx]
                # Same sender?
                if item.get('sender_id') != sender_id:
                    continue
                # Is it a text message with actual content?
                msg = item.get('message', '')
                if item.get('content_type') != 'txt' or msg in ['[image]', '[video]', '']:
                    continue
                # Within time window?
                other_date = item.get('date_sent', 0)
                if abs(other_date - date_sent) <= TEXT_ASSOCIATION_WINDOW:
                    return msg
    return None


def parse_messages(messages_path):
    """Parse message.json and extract media items with metadata."""
    with open(messages_path) as f:
        data = json.load(f)

    items = data.get('items', [])
    media_items = []

    for idx, item in enumerate(items):
        attachments = item.get('attachments', [])
        if not attachments:
            continue

        sender_id = item.get('sender_id')
        sender_name = item.get('user_name', 'Teacher')
        date_sent = item.get('date_sent', 0)
        created_at = item.get('created_at', '')
        message_id = item.get('_id', '')
        dialog_name = item.get('_dialog_name', 'Unknown')

        # Try to find associated text message for title
        associated_text = find_associated_text(items, idx, sender_id, date_sent)

        for i, attachment in enumerate(attachments):
            url = attachment.get('url', '')
            if not url:
                continue

            # Skip thumbnails
            if is_thumbnail(url):
                continue

            # Only process images (.png) and videos (.mp4)
            if not (url.endswith('.png') or url.endswith('.mp4')):
                continue

            file_type = get_file_type(url)
            is_video = file_type == 'mp4'

            # Determine title
            if associated_text:
                title = associated_text
            elif is_video:
                title = f"Video from {sender_name}"
            else:
                title = f"Photo from {sender_name}"

            # Truncate title if too long
            if len(title) > 100:
                title = title[:97] + '...'

            # Description includes sender info
            description = f"{title}\n\nSent by {sender_name}" if associated_text else f"Sent by {sender_name}"

            media_items.append({
                'url': url,
                'file_type': file_type,
                'date': parse_iso_date(created_at),
                'date_raw': created_at,
                'message_id': message_id,
                'attachment_idx': i,
                'sender': sender_name,
                'title': title,
                'description': description,
                'dialog_name': dialog_name,
            })

    # Sort by date (oldest first)
    media_items.sort(key=lambda x: x['date_raw'])
    return media_items


def generate_filename(item, date_counts):
    """Generate a unique filename for a media item."""
    date_str = item['date_raw']
    file_type = item['file_type']
    sender = item['sender'].replace(' ', '_').replace('.', '')

    # Parse date: "2026-01-12T22:18:37Z" -> "2026-01-12_22-18-37"
    if date_str:
        date_part = date_str.replace('T', '_').replace('Z', '').replace(':', '-')
    else:
        date_part = 'unknown_date'

    # Handle multiple files with same timestamp
    base_key = f"{sender}_{date_part}"
    date_counts[base_key] += 1
    count = date_counts[base_key]

    if count > 1:
        return f"{sender}_{date_part}_{count:02d}.{file_type}"
    else:
        return f"{sender}_{date_part}.{file_type}"


def download_one(args):
    """Download a single media item. Used by thread pool."""
    item, filepath = args
    try:
        urllib.request.urlretrieve(item['url'], filepath)
        return (filepath, item['date'], item['file_type'], item['title'], item['description'], None)
    except Exception as e:
        return (filepath, item['date'], item['file_type'], item['title'], item['description'], str(e))


def download_media(media_items, output_dir, parallel=50):
    """Download all media items to output directory. Returns only newly downloaded files."""
    os.makedirs(output_dir, exist_ok=True)

    date_counts = defaultdict(int)
    already_exist = 0
    to_download = []

    # First pass: generate filenames and check what needs downloading
    for item in media_items:
        filename = generate_filename(item, date_counts)
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            already_exist += 1
        else:
            to_download.append((item, filepath, filename))

    print(f"Found {len(media_items)} media files, {already_exist} already exist, downloading {len(to_download)}...")

    if not to_download:
        return []

    # Download in parallel
    newly_downloaded = []
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(download_one, (item, filepath)): filename
                   for item, filepath, filename in to_download}

        for i, future in enumerate(as_completed(futures)):
            filename = futures[future]
            result = future.result()
            filepath, date, ftype, title, desc, error = result

            if error:
                print(f"[{i+1}/{len(to_download)}] ERROR {filename}: {error}")
            else:
                print(f"[{i+1}/{len(to_download)}] Downloaded: {filename}")
                newly_downloaded.append((filepath, date, ftype, title, desc))

    return newly_downloaded


def get_location_args(file_type):
    """Get exiftool args for location, or empty list if not configured."""
    if not LOCATION or LOCATION is False:
        return []

    lat = LOCATION.get('latitude')
    lon = LOCATION.get('longitude')

    args = []

    # Add GPS coordinates if available
    if lat is not None and lon is not None:
        if file_type == 'jpg':
            lat_ref = 'N' if lat >= 0 else 'S'
            lon_ref = 'E' if lon >= 0 else 'W'
            args.extend([
                f'-GPSLatitude={abs(lat)}',
                f'-GPSLatitudeRef={lat_ref}',
                f'-GPSLongitude={abs(lon)}',
                f'-GPSLongitudeRef={lon_ref}',
            ])
        else:  # mp4
            args.append(f'-GPSCoordinates={lat} {lon}')

    # Add location name/address if available
    if LOCATION.get('name'):
        args.append(f'-Location={LOCATION["name"]}')
    if LOCATION.get('city'):
        args.append(f'-City={LOCATION["city"]}')
    if LOCATION.get('state'):
        args.append(f'-State={LOCATION["state"]}')
    if LOCATION.get('country'):
        args.append(f'-Country={LOCATION["country"]}')

    return args


def set_metadata(downloaded_files, has_exiftool, exiftool_path=None):
    """Set date and location metadata on downloaded files using exiftool."""
    if not has_exiftool:
        print("\nWarning: exiftool not found. Skipping metadata update.")
        print("Install with: brew install exiftool")
        return

    print(f"\nSetting metadata on {len(downloaded_files)} files...")
    exiftool_cmd = exiftool_path or 'exiftool'

    for i, item in enumerate(downloaded_files):
        filepath, date_str, file_type, title, description = item
        filename = os.path.basename(filepath)
        print(f"[{i+1}/{len(downloaded_files)}] Setting metadata on {filename}")

        args = [exiftool_cmd, '-overwrite_original', '-q']

        # Add location args
        args.extend(get_location_args(file_type))

        # Add title and description (for Apple Photos)
        if title:
            args.extend([
                f'-Title={title}',
                f'-XMP:Title={title}',
                f'-IPTC:ObjectName={title}',
            ])
        if description:
            args.extend([
                f'-Description={description}',
                f'-Caption-Abstract={description}',
                f'-ImageDescription={description}',
            ])

        # Add date tags if we have a date
        if date_str:
            if file_type == 'jpg':
                args.extend([
                    f'-DateTimeOriginal={date_str}',
                    f'-CreateDate={date_str}',
                    f'-ModifyDate={date_str}',
                ])
            elif file_type == 'mp4':
                args.extend([
                    f'-CreateDate={date_str}',
                    f'-ModifyDate={date_str}',
                    f'-MediaCreateDate={date_str}',
                    f'-MediaModifyDate={date_str}',
                    f'-TrackCreateDate={date_str}',
                    f'-TrackModifyDate={date_str}',
                ])

        args.append(filepath)
        subprocess.run(args, capture_output=True)


def sanitize_folder_name(name):
    """Convert a name to a safe folder name."""
    # Replace spaces and special chars with underscores
    safe = re.sub(r'[^\w\-]', '_', name)
    # Remove consecutive underscores
    safe = re.sub(r'_+', '_', safe)
    return safe.strip('_')


def run(messages_path, output_dir, exiftool_path=None):
    """
    Download photos from message.json. Can be called directly or via CLI.
    Returns list of newly downloaded file paths.
    """
    global LOCATION
    LOCATION = get_location()  # Refresh in case config changed

    if not os.path.exists(messages_path):
        print(f"Error: {messages_path} not found")
        return []

    has_exiftool = check_exiftool(exiftool_path)
    if not has_exiftool:
        print("Warning: exiftool not found. Dates and location will not be embedded in files.")

    # Parse messages
    media_items = parse_messages(messages_path)
    print(f"Found {len(media_items)} media items in {messages_path}")

    if not media_items:
        print("No media found.")
        return []

    # Group by dialog (kid)
    by_dialog = defaultdict(list)
    for item in media_items:
        dialog = item.get('dialog_name', 'Unknown')
        by_dialog[dialog].append(item)

    # Download each dialog's media to its own subfolder
    all_downloaded = []
    for dialog_name, items in by_dialog.items():
        kid_folder = sanitize_folder_name(dialog_name)
        kid_path = os.path.join(output_dir, kid_folder)

        print(f"\n--- {dialog_name} ({len(items)} items) ---")
        downloaded = download_media(items, kid_path)
        all_downloaded.extend(downloaded)

    # Set metadata (dates and location)
    set_metadata(all_downloaded, has_exiftool, exiftool_path)

    # Summary
    jpg_count = sum(1 for item in all_downloaded if item[2] == 'jpg')
    mp4_count = sum(1 for item in all_downloaded if item[2] == 'mp4')
    print(f"\nDone! {len(all_downloaded)} files ({jpg_count} photos, {mp4_count} videos)")

    return [item[0] for item in all_downloaded]  # Return file paths


def main():
    script_dir = Path(__file__).parent
    messages_path = sys.argv[1] if len(sys.argv) > 1 else str(script_dir / 'message.json')
    output_dir = sys.argv[2] if len(sys.argv) > 2 else str(script_dir / 'messages')

    run(messages_path, output_dir)


if __name__ == '__main__':
    main()
