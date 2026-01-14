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
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR / 'scripts'))

PHOTOS_DIR = SCRIPT_DIR / 'photos'
NEW_FILES_DIR = PHOTOS_DIR / 'new'


def clear_new_folder():
    """Clear the 'new' folder at start of each run."""
    if NEW_FILES_DIR.exists():
        shutil.rmtree(NEW_FILES_DIR)


def copy_to_new_folder(files):
    """Copy files to the 'new' folder, preserving directory structure."""
    for src in files:
        src = Path(src)
        # Preserve structure: photos/home/x.jpg -> photos/new/home/x.jpg
        rel_path = src.relative_to(PHOTOS_DIR)
        dst = NEW_FILES_DIR / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def run(home_only=False, chat_only=False, exiftool_path=None):
    """
    Download photos from Learning Genie data files.
    Returns list of all newly downloaded files.
    """
    from download_chat import run as run_chat
    from download_home import run as run_home

    # Clear the 'new' folder at start
    clear_new_folder()

    results = []
    all_new_files = []

    if not chat_only:
        notes_path = SCRIPT_DIR / 'data' / 'notes.json'
        output_dir = PHOTOS_DIR / 'home'

        if notes_path.exists():
            print(f"\n{'='*60}")
            print("Downloading from data/notes.json")
            print("Output: photos/home/")
            print('='*60)

            output_dir.mkdir(parents=True, exist_ok=True)
            new_files = run_home(str(notes_path), str(output_dir), exiftool_path)
            results.append(('Home', True, len(new_files)))
            all_new_files.extend(new_files)
        else:
            print("Skipping Home: data/notes.json not found")
            results.append(('Home', False, 0))

    if not home_only:
        messages_path = SCRIPT_DIR / 'data' / 'message.json'
        output_dir = PHOTOS_DIR / 'chat'

        if messages_path.exists():
            print(f"\n{'='*60}")
            print("Downloading from data/message.json")
            print("Output: photos/chat/")
            print('='*60)

            output_dir.mkdir(parents=True, exist_ok=True)
            new_files = run_chat(str(messages_path), str(output_dir), exiftool_path)
            results.append(('Chat', True, len(new_files)))
            all_new_files.extend(new_files)
        else:
            print("Skipping Chat: data/message.json not found")
            results.append(('Chat', False, 0))

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
            f = Path(f)
            rel_path = f.relative_to(PHOTOS_DIR)
            # Get the folder (home or chat/Kid_Name)
            parts = rel_path.parts[:-1]  # Remove filename
            new_folders.add('/'.join(parts))
        for folder in sorted(new_folders):
            print(f"  photos/new/{folder}/")
    else:
        print("\nNo new files to import.")

    return all_new_files


def main():
    parser = argparse.ArgumentParser(description='Download Learning Genie photos')
    parser.add_argument('--home-only', action='store_true', help='Only download Home photos')
    parser.add_argument('--chat-only', action='store_true', help='Only download Chat photos')
    args = parser.parse_args()

    if args.home_only and args.chat_only:
        print("Error: Cannot specify both --home-only and --chat-only")
        sys.exit(1)

    run(home_only=args.home_only, chat_only=args.chat_only)


if __name__ == '__main__':
    main()
