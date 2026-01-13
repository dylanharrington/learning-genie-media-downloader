#!/usr/bin/env python3
"""
Interactive sync tool for Learning Genie photos.
Walks you through the entire process step by step.

Usage:
    ./sync.py         # Manual mode (copy cURL commands)
    ./sync.py --auto  # Automatic mode (browser automation)
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from config import load_config, prompt_for_location


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60 + "\n")


def print_step(num, text):
    print(f"\n[Step {num}] {text}\n")


def get_multiline_input(prompt):
    """Get input that might span multiple lines (for pasted cURL)."""
    print(prompt)
    print("(Paste your cURL command, then press Enter twice when done)\n")

    lines = []
    empty_count = 0

    while True:
        try:
            line = input()
            if line == '':
                empty_count += 1
                if empty_count >= 1 and lines:  # One empty line after content = done
                    break
                lines.append(line)
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break

    return ' '.join(line.strip() for line in lines if line.strip())


def run_fetch(qb_curl=None, lg_curl=None):
    """Run fetch.py with provided cURLs."""
    cmd = [sys.executable, str(SCRIPT_DIR / 'fetch.py')]

    if qb_curl:
        cmd.extend(['--qb-curl', qb_curl])
    if lg_curl:
        cmd.extend(['--lg-curl', lg_curl])

    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    return result.returncode == 0


def run_download():
    """Run download.py."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / 'download.py')],
        cwd=SCRIPT_DIR
    )
    return result.returncode == 0


def check_first_run():
    """Check if this is the first run and prompt for location if needed."""
    config = load_config()

    # If location hasn't been configured yet (None = never asked)
    if config.get('location') is None:
        prompt_for_location()


def run_auto_login():
    """Run login.py for automatic browser-based authentication."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / 'login.py')],
        cwd=SCRIPT_DIR
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description='Sync photos from Learning Genie')
    parser.add_argument('--auto', action='store_true', help='Use browser automation instead of manual cURL')
    args = parser.parse_args()

    print_header("Learning Genie Photo Sync")

    # First run setup
    check_first_run()

    # Auto mode: use browser automation
    if args.auto:
        print("Using automatic browser login...\n")
        success = run_auto_login()
        if not success:
            print("\nAuto-login failed.")
            sys.exit(1)
        return

    # Manual mode: guide through cURL copying
    print("This tool will help you download photos from Learning Genie.")
    print("You'll need to copy some data from Chrome DevTools.")
    print("\nTip: Use './sync.py --auto' for automatic browser login.\n")

    print("Ready? Let's go!\n")
    input("Press Enter to continue...")

    # Step 1: Home cURL (user starts on Home tab after login)
    print_step(1, "Get Home photos data")
    print("""
1. Open Chrome and go to: https://web.learning-genie.com
2. Log in if needed (you'll land on the Home tab)
3. Open DevTools: right-click anywhere → "Inspect", then click "Network" tab
   (or use View menu → Developer → Developer Tools)
4. Click "Fetch/XHR" filter
5. Refresh the page to trigger requests
6. Look for a request to "api2.learning-genie.com" (like "Notes")
7. Right-click that request → "Copy as cURL"
""")

    lg_curl = get_multiline_input("Paste the cURL command here:")

    if not lg_curl or 'curl' not in lg_curl.lower():
        print("\nNo valid cURL detected. Skipping Home photos.")
        lg_curl = None
    else:
        print("\n✓ Got Home cURL")

    # Step 2: Chat cURL (opens in new tab, so DevTools needs to be reopened)
    print_step(2, "Get Chat photos data")
    print("""
1. Click the "Chat" tab (this opens in a new browser tab)
2. Open DevTools again: right-click → "Inspect" → "Network" tab
3. Click "Fetch/XHR" filter
4. Click on any chat conversation to trigger requests
5. Look for a request to "quickblox.com" (like Dialog.json)
6. Right-click that request → "Copy as cURL"
""")

    qb_curl = get_multiline_input("Paste the cURL command here:")

    if not qb_curl or 'curl' not in qb_curl.lower():
        print("\nNo valid cURL detected. Skipping Chat photos.")
        qb_curl = None
    else:
        print("\n✓ Got Chat cURL")

    if not qb_curl and not lg_curl:
        print("\nNo data to fetch. Exiting.")
        sys.exit(1)

    # Step 3: Fetch data
    print_step(3, "Fetching data from Learning Genie")

    success = run_fetch(qb_curl, lg_curl)

    if not success:
        print("\nFetch failed. Check the error messages above.")
        sys.exit(1)

    # Step 4: Download photos
    print_step(4, "Downloading photos")

    run_download()

    # Done!
    print_header("Done!")
    print("Your photos have been downloaded to dated folders in photos/")
    print("Drag those folders into your photo library (Apple Photos, Google Photos, etc.)\n")


if __name__ == '__main__':
    main()
