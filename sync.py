#!/usr/bin/env python3
"""
Interactive sync tool for Learning Genie photos.
Walks you through the entire process step by step.

Usage:
    ./sync.py           # Automatic mode (browser automation)
    ./sync.py --manual  # Manual mode (copy cURL commands)
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR / 'scripts'))
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
    """Run fetch with provided cURLs."""
    from fetch import run as fetch_run
    return fetch_run(qb_curl=qb_curl, lg_curl=lg_curl)


def run_download():
    """Run download."""
    from download import run as download_run
    download_run()
    return True


def check_first_run():
    """Check if this is the first run and prompt for location if needed."""
    config = load_config()

    # If location hasn't been configured yet (None = never asked)
    if config.get('location') is None:
        prompt_for_location()


def run_auto_login():
    """Run automatic browser-based authentication."""
    from login import get_credentials, login_and_capture_tokens, run_download, run_fetch

    email, password = get_credentials()
    tokens = login_and_capture_tokens(email, password, headless=True)

    # Check what we got
    missing = []
    if not tokens['lg_session']:
        missing.append('lg_session')
    if not tokens['x_uid']:
        missing.append('x_uid')
    if not tokens['qb_token']:
        missing.append('QB-Token')

    if missing:
        print(f"\n⚠ Warning: Could not capture: {', '.join(missing)}")

    # Run fetch and download
    if tokens['lg_session'] or tokens['qb_token']:
        if run_fetch(tokens):
            run_download()
            return True
    else:
        print("\nError: No tokens captured. Cannot proceed with sync.")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description='Sync photos from Learning Genie')
    parser.add_argument('--manual', action='store_true', help='Use manual cURL copying instead of browser automation')
    args = parser.parse_args()

    print_header("Learning Genie Photo Sync")

    # First run setup
    check_first_run()

    # Manual mode: guide through cURL copying
    if args.manual:
        run_manual_mode()
        return

    # Auto mode (default): use browser automation
    print("Using automatic browser login...\n")
    success = run_auto_login()
    if not success:
        print("\nAuto-login failed. Try './sync.py --manual' for manual mode.")
        sys.exit(1)


def run_manual_mode():
    """Guide user through manual cURL copying process."""
    print("This tool will help you download photos from Learning Genie.")
    print("You'll need to copy some data from Chrome DevTools.\n")

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
