#!/usr/bin/env python3
"""
Download all photos from Learning Genie data.

Usage:
    ./download.py              # Download photos
    ./download.py --home-only  # Only download Home photos
    ./download.py --chat-only  # Only download Chat photos

New files are copied to photos/new/ for easy import to your photo library.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PHOTOS_DIR = SCRIPT_DIR / 'photos'
NEW_FILES_DIR = PHOTOS_DIR / 'new'


def clear_new_folder():
    """Clear the 'new' folder at start of each run."""
    if NEW_FILES_DIR.exists():
        shutil.rmtree(NEW_FILES_DIR)


def get_all_media_files(path):
    """Get set of all media files in a directory."""
    files = set()
    if path.exists():
        files.update(path.rglob('*.jpg'))
        files.update(path.rglob('*.mp4'))
    return files


def run_script(script, json_file, output_dir):
    """Run a download script and return list of new files."""
    script_path = SCRIPT_DIR / 'scripts' / script
    json_path = SCRIPT_DIR / json_file
    output_path = SCRIPT_DIR / output_dir

    if not json_path.exists():
        print(f"Skipping {script}: {json_file} not found")
        return [], False

    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Downloading from {json_file}")
    print(f"Output: {output_path.relative_to(SCRIPT_DIR)}/")
    print('='*60)

    # Get files before download
    files_before = get_all_media_files(output_path)

    # Run download (output streams in real-time)
    result = subprocess.run(
        [sys.executable, str(script_path), str(json_path), str(output_path)],
        cwd=SCRIPT_DIR
    )

    # Get files after download
    files_after = get_all_media_files(output_path)

    # New files are the difference
    new_files = list(files_after - files_before)

    return new_files, result.returncode == 0


def copy_to_new_folder(files):
    """Copy files to the 'new' folder, preserving directory structure."""
    for src in files:
        # Preserve structure: photos/home/x.jpg -> photos/new/home/x.jpg
        rel_path = src.relative_to(PHOTOS_DIR)
        dst = NEW_FILES_DIR / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main():
    parser = argparse.ArgumentParser(description='Download Learning Genie photos')
    parser.add_argument('--home-only', action='store_true', help='Only download Home photos')
    parser.add_argument('--chat-only', action='store_true', help='Only download Chat photos')
    args = parser.parse_args()

    if args.home_only and args.chat_only:
        print("Error: Cannot specify both --home-only and --chat-only")
        sys.exit(1)

    # Clear the 'new' folder at start
    clear_new_folder()

    results = []
    all_new_files = []

    if not args.chat_only:
        new_files, success = run_script('download_home.py', 'data/notes.json', 'photos/home')
        results.append(('Home', success, len(new_files)))
        all_new_files.extend(new_files)

    if not args.home_only:
        new_files, success = run_script('download_chat.py', 'data/message.json', 'photos/chat')
        results.append(('Chat', success, len(new_files)))
        all_new_files.extend(new_files)

    # Copy new files to the 'new' folder
    if all_new_files:
        copy_to_new_folder(all_new_files)

    print(f"\n{'='*60}")
    print("Summary")
    print('='*60)
    for name, success, count in results:
        if count > 0:
            print(f"  {name}: {count} new files")
        elif success:
            print(f"  {name}: No new files")
        else:
            print(f"  {name}: Skipped (no data)")

    if all_new_files:
        print(f"\n{len(all_new_files)} new files ready to import from:")
        # List subfolders with new files
        new_folders = set()
        for f in all_new_files:
            rel_path = f.relative_to(PHOTOS_DIR)
            # Get the folder (home or chat/Kid_Name)
            parts = rel_path.parts[:-1]  # Remove filename
            new_folders.add('/'.join(parts))
        for folder in sorted(new_folders):
            print(f"  photos/new/{folder}/")
    else:
        print("\nNo new files to import.")


if __name__ == '__main__':
    main()
