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

# De Anza College Child Development Center, Cupertino, CA
LOCATION = {
    'name': 'De Anza Child Development Center',
    'address': '21250 Stevens Creek Blvd',
    'city': 'Cupertino',
    'state': 'California',
    'country': 'United States',
    'latitude': 37.3195,
    'longitude': -122.0448,
}

# Time window (seconds) to look for associated text messages
TEXT_ASSOCIATION_WINDOW = 120


def check_exiftool():
    """Check if exiftool is available."""
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
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
    with open(messages_path, 'r') as f:
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
        content_type = item.get('content_type', '')

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


def download_media(media_items, output_dir, parallel=10):
    """Download all media items to output directory."""
    os.makedirs(output_dir, exist_ok=True)

    date_counts = defaultdict(int)
    downloaded = []
    to_download = []

    # First pass: generate filenames and check what needs downloading
    for item in media_items:
        filename = generate_filename(item, date_counts)
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            downloaded.append((filepath, item['date'], item['file_type'], item['title'], item['description']))
        else:
            to_download.append((item, filepath, filename))

    print(f"Found {len(media_items)} media files, {len(downloaded)} already exist, downloading {len(to_download)}...")

    if not to_download:
        return downloaded

    # Download in parallel
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
                downloaded.append((filepath, date, ftype, title, desc))

    return downloaded


def set_metadata(downloaded_files, has_exiftool):
    """Set date and location metadata on downloaded files using exiftool."""
    if not has_exiftool:
        print("\nWarning: exiftool not found. Skipping metadata update.")
        print("Install with: brew install exiftool")
        return

    print(f"\nSetting date and location metadata on {len(downloaded_files)} files...")

    lat = LOCATION['latitude']
    lon = LOCATION['longitude']
    lat_ref = 'N' if lat >= 0 else 'S'
    lon_ref = 'E' if lon >= 0 else 'W'

    # Location tags for JPG (EXIF uses separate ref tags)
    jpg_location_args = [
        f'-GPSLatitude={abs(lat)}',
        f'-GPSLatitudeRef={lat_ref}',
        f'-GPSLongitude={abs(lon)}',
        f'-GPSLongitudeRef={lon_ref}',
        f'-Location={LOCATION["name"]}',
        f'-City={LOCATION["city"]}',
        f'-State={LOCATION["state"]}',
        f'-Country={LOCATION["country"]}',
    ]

    # Location tags for MP4 (uses signed coordinates)
    mp4_location_args = [
        f'-GPSCoordinates={lat} {lon}',
        f'-Location={LOCATION["name"]}',
        f'-City={LOCATION["city"]}',
        f'-State={LOCATION["state"]}',
        f'-Country={LOCATION["country"]}',
    ]

    for i, item in enumerate(downloaded_files):
        filepath, date_str, file_type, title, description = item
        filename = os.path.basename(filepath)
        print(f"[{i+1}/{len(downloaded_files)}] Setting metadata on {filename}")

        # Build base args with appropriate location tags
        loc_args = jpg_location_args if file_type == 'jpg' else mp4_location_args
        args = ['exiftool', '-overwrite_original', '-q'] + loc_args

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


def main():
    script_dir = Path(__file__).parent
    messages_path = sys.argv[1] if len(sys.argv) > 1 else str(script_dir / 'message.json')
    output_dir = sys.argv[2] if len(sys.argv) > 2 else str(script_dir / 'messages')

    if not os.path.exists(messages_path):
        print(f"Error: {messages_path} not found")
        sys.exit(1)

    has_exiftool = check_exiftool()
    if not has_exiftool:
        print("Warning: exiftool not found. Dates and location will not be embedded in files.")
        print("Install with: brew install exiftool\n")

    # Parse and download
    media_items = parse_messages(messages_path)
    print(f"Found {len(media_items)} media items in {messages_path}")

    if not media_items:
        print("No media found.")
        sys.exit(0)

    downloaded = download_media(media_items, output_dir)

    # Set metadata (dates and location)
    set_metadata(downloaded, has_exiftool)

    # Summary
    jpg_count = sum(1 for item in downloaded if item[2] == 'jpg')
    mp4_count = sum(1 for item in downloaded if item[2] == 'mp4')
    print(f"\nDone! {len(downloaded)} files ({jpg_count} photos, {mp4_count} videos)")


if __name__ == '__main__':
    main()
