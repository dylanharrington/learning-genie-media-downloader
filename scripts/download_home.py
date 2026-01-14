#!/usr/bin/env python3
"""
Download photos from LearningGenie Home tab (notes.json).

Usage:
    ./scripts/download_home.py data/notes.json photos/home
"""

import json
import os
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


def check_exiftool(exiftool_path=None):
    """Check if exiftool is available."""
    cmd = exiftool_path or "exiftool"
    try:
        subprocess.run([cmd, "-ver"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def parse_notes(notes_path):
    """Parse notes.json and extract media items with metadata."""
    with open(notes_path) as f:
        notes = json.load(f)

    media_items = []
    for note in notes:
        children_names = [c.get("displayName", "Unknown") for c in note.get("children", [])]
        child_name = children_names[0] if children_names else "Unknown"

        # Get the activity description for titles
        payload = note.get("payload", "") or ""
        # Create a short title from the first sentence or first 100 chars
        title = payload.split(".")[0].strip() if payload else ""
        if len(title) > 100:
            title = title[:97] + "..."

        for media in note.get("media", []):
            url = media.get("public_url", "")
            if url:
                media_items.append(
                    {
                        "url": url,
                        "fileType": media.get("fileType", "unknown"),
                        "date": media.get("createAtUtc", ""),
                        "child": child_name,
                        "title": title,
                        "description": payload,
                    }
                )

    # Sort by date
    media_items.sort(key=lambda x: x["date"])
    return media_items


def generate_filename(item, date_counts):
    """Generate a unique filename for a media item."""
    child = item["child"].replace(" ", "_")
    file_type = item["fileType"]
    date_str = item["date"]

    # Parse date: "2026-01-12 21:19:51" -> "2026-01-12_21-19-51"
    if date_str:
        date_part = date_str.replace(" ", "_").replace(":", "-")
    else:
        date_part = "unknown_date"

    # Handle multiple files with same timestamp
    base_key = f"{child}_{date_part}"
    date_counts[base_key] += 1
    count = date_counts[base_key]

    if count > 1:
        return f"{child}_{date_part}_{count:02d}.{file_type}"
    else:
        return f"{child}_{date_part}.{file_type}"


def download_one(args):
    """Download a single media item. Used by thread pool."""
    item, filepath = args
    try:
        urllib.request.urlretrieve(item["url"], filepath)
        return (filepath, item["date"], item["fileType"], item.get("title", ""), item.get("description", ""), None)
    except Exception as e:
        return (filepath, item["date"], item["fileType"], item.get("title", ""), item.get("description", ""), str(e))


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
        futures = {
            executor.submit(download_one, (item, filepath)): filename for item, filepath, filename in to_download
        }

        for i, future in enumerate(as_completed(futures)):
            filename = futures[future]
            result = future.result()
            filepath, date, ftype, title, desc, error = result

            if error:
                print(f"[{i + 1}/{len(to_download)}] ERROR {filename}: {error}")
            else:
                print(f"[{i + 1}/{len(to_download)}] Downloaded: {filename}")
                newly_downloaded.append((filepath, date, ftype, title, desc))

    return newly_downloaded


def get_location_args(file_type):
    """Get exiftool args for location, or empty list if not configured."""
    if not LOCATION or LOCATION is False:
        return []

    lat = LOCATION.get("latitude")
    lon = LOCATION.get("longitude")

    args = []

    # Add GPS coordinates if available
    if lat is not None and lon is not None:
        if file_type == "jpg":
            lat_ref = "N" if lat >= 0 else "S"
            lon_ref = "E" if lon >= 0 else "W"
            args.extend(
                [
                    f"-GPSLatitude={abs(lat)}",
                    f"-GPSLatitudeRef={lat_ref}",
                    f"-GPSLongitude={abs(lon)}",
                    f"-GPSLongitudeRef={lon_ref}",
                ]
            )
        else:  # mp4
            args.append(f"-GPSCoordinates={lat} {lon}")

    # Add location name/address if available
    if LOCATION.get("name"):
        args.append(f"-Location={LOCATION['name']}")
    if LOCATION.get("city"):
        args.append(f"-City={LOCATION['city']}")
    if LOCATION.get("state"):
        args.append(f"-State={LOCATION['state']}")
    if LOCATION.get("country"):
        args.append(f"-Country={LOCATION['country']}")

    return args


def set_metadata(downloaded_files, has_exiftool, exiftool_path=None):
    """Set date and location metadata on downloaded files using exiftool."""
    if not has_exiftool:
        print("\nWarning: exiftool not found. Skipping metadata update.")
        print("Install with: brew install exiftool")
        return

    print(f"\nSetting metadata on {len(downloaded_files)} files...")
    exiftool_cmd = exiftool_path or "exiftool"

    for i, item in enumerate(downloaded_files):
        filepath, date_str, file_type, title, description = item
        filename = os.path.basename(filepath)
        print(f"[{i + 1}/{len(downloaded_files)}] Setting metadata on {filename}")

        args = [exiftool_cmd, "-overwrite_original", "-q"]

        # Add location args
        args.extend(get_location_args(file_type))

        # Add title and description (for Apple Photos)
        if title:
            args.extend(
                [
                    f"-Title={title}",
                    f"-XMP:Title={title}",
                    f"-IPTC:ObjectName={title}",
                ]
            )
        if description:
            args.extend(
                [
                    f"-Description={description}",
                    f"-Caption-Abstract={description}",
                    f"-ImageDescription={description}",
                ]
            )

        # Add date tags if we have a date
        if date_str:
            # Format for exiftool: "YYYY:MM:DD HH:MM:SS"
            exif_date = date_str.replace("-", ":")

            if file_type == "jpg":
                args.extend(
                    [
                        f"-DateTimeOriginal={exif_date}",
                        f"-CreateDate={exif_date}",
                        f"-ModifyDate={exif_date}",
                    ]
                )
            elif file_type == "mp4":
                args.extend(
                    [
                        f"-CreateDate={exif_date}",
                        f"-ModifyDate={exif_date}",
                        f"-MediaCreateDate={exif_date}",
                        f"-MediaModifyDate={exif_date}",
                        f"-TrackCreateDate={exif_date}",
                        f"-TrackModifyDate={exif_date}",
                    ]
                )

        args.append(filepath)
        subprocess.run(args, capture_output=True)


def run(notes_path, output_dir, exiftool_path=None):
    """
    Download photos from notes.json. Can be called directly or via CLI.
    Returns list of newly downloaded file paths.
    """
    global LOCATION
    LOCATION = get_location()  # Refresh in case config changed

    if not os.path.exists(notes_path):
        print(f"Error: {notes_path} not found")
        return []

    has_exiftool = check_exiftool(exiftool_path)
    if not has_exiftool:
        print("Warning: exiftool not found. Dates and location will not be embedded in files.")

    # Parse and download
    media_items = parse_notes(notes_path)
    print(f"Found {len(media_items)} media items in {notes_path}")

    if not media_items:
        print("No media found.")
        return []

    downloaded = download_media(media_items, output_dir)

    # Set metadata (dates and location)
    set_metadata(downloaded, has_exiftool, exiftool_path)

    # Summary
    jpg_count = sum(1 for item in downloaded if item[2] == "jpg")
    mp4_count = sum(1 for item in downloaded if item[2] == "mp4")
    print(f"\nDone! Downloaded {len(downloaded)} files ({jpg_count} photos, {mp4_count} videos)")

    return [item[0] for item in downloaded]  # Return file paths


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    notes_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./media"

    run(notes_path, output_dir)


if __name__ == "__main__":
    main()
