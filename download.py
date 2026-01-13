#!/usr/bin/env python3
"""
Download all photos from Learning Genie data.

Usage:
    ./download.py              # Download to timestamped folders (e.g., photos/home/2025-01-13/)
    ./download.py --home-only  # Only download Home photos
    ./download.py --chat-only  # Only download Chat photos

Photos are organized by date for easy drag-and-drop into Apple/Google Photos.
"""

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def get_dated_folder(base_path):
    """Get a dated folder path, adding suffix if folder already exists."""
    today = date.today().isoformat()  # e.g., "2025-01-13"
    folder = base_path / today

    if not folder.exists():
        return folder

    # Folder exists, find next available suffix
    suffix = 2
    while True:
        folder = base_path / f"{today}_{suffix}"
        if not folder.exists():
            return folder
        suffix += 1


def run_script(script, json_file, base_output_dir, use_dated_folder=True):
    """Run a download script."""
    script_path = SCRIPT_DIR / 'scripts' / script
    json_path = SCRIPT_DIR / json_file
    base_path = SCRIPT_DIR / base_output_dir

    if not json_path.exists():
        print(f"Skipping {script}: {json_file} not found")
        return None, False

    # Create output folder (dated for home, flat for chat which has kid subfolders)
    if use_dated_folder:
        output_path = get_dated_folder(base_path)
    else:
        output_path = base_path
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Downloading from {json_file}")
    print(f"Output: {output_path.relative_to(SCRIPT_DIR)}/")
    print('='*60)

    result = subprocess.run(
        [sys.executable, str(script_path), str(json_path), str(output_path)],
        cwd=SCRIPT_DIR
    )

    # Check if any files were downloaded (check recursively for subfolders)
    files = list(output_path.rglob('*.jpg')) + list(output_path.rglob('*.mp4'))

    # For dated folders, remove if empty
    if use_dated_folder and not files:
        try:
            output_path.rmdir()
        except OSError:
            pass  # Not empty or other error
        return None, True  # Success but no new files

    return output_path, result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description='Download Learning Genie photos')
    parser.add_argument('--home-only', action='store_true', help='Only download Home photos')
    parser.add_argument('--chat-only', action='store_true', help='Only download Chat photos')
    args = parser.parse_args()

    if args.home_only and args.chat_only:
        print("Error: Cannot specify both --home-only and --chat-only")
        sys.exit(1)

    results = []
    new_folders = []

    if not args.chat_only:
        folder, success = run_script('download_home.py', 'data/notes.json', 'photos/home')
        results.append(('Home', success, folder))
        if folder:
            new_folders.append(folder)

    if not args.home_only:
        # Chat creates its own kid/date subfolders internally
        folder, success = run_script('download_chat.py', 'data/message.json', 'photos/chat', use_dated_folder=False)
        results.append(('Chat', success, folder))
        if folder:
            # Find the dated folders inside each kid folder
            for kid_folder in folder.iterdir():
                if kid_folder.is_dir():
                    for dated_folder in kid_folder.iterdir():
                        if dated_folder.is_dir() and list(dated_folder.glob('*')):
                            new_folders.append(dated_folder)

    print(f"\n{'='*60}")
    print("Summary")
    print('='*60)
    for name, success, folder in results:
        if folder:
            # Count files recursively for folders with subfolders
            file_count = len(list(folder.rglob('*.jpg'))) + len(list(folder.rglob('*.mp4')))
            print(f"  {name}: {file_count} files → {folder.relative_to(SCRIPT_DIR)}/")
        elif success:
            print(f"  {name}: No new files")
        else:
            print(f"  {name}: Skipped (no data)")

    if new_folders:
        print(f"\nDrag these folders into your photo library:")
        for folder in new_folders:
            print(f"  {folder.relative_to(SCRIPT_DIR)}/")


if __name__ == '__main__':
    main()
