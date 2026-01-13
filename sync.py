#!/usr/bin/env python3
"""
Interactive sync tool for Learning Genie photos.
Walks you through the entire process step by step.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


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


def main():
    print_header("Learning Genie Photo Sync")

    print("This tool will help you download photos from Learning Genie.")
    print("You'll need to copy some data from Chrome DevTools.\n")
    print("Ready? Let's go!\n")

    input("Press Enter to continue...")

    # Step 1: Chat cURL
    print_step(1, "Get Chat photos data")
    print("""
1. Open Chrome and go to: https://web.learning-genie.com
2. Log in if needed
3. Click on the "Chat" tab
4. Open DevTools: Cmd+Option+I (Mac) or Ctrl+Shift+I (Windows)
5. Click the "Network" tab
6. Click "Fetch/XHR" filter (or just "XHR")
7. Click on any chat conversation to trigger requests
8. Look for a request to "quickblox.com" (like Dialog.json or Message.json)
9. Right-click that request → "Copy as cURL"
""")

    qb_curl = get_multiline_input("Paste the cURL command here:")

    if not qb_curl or 'curl' not in qb_curl.lower():
        print("\nNo valid cURL detected. Skipping Chat photos.")
        qb_curl = None
    else:
        print("\n✓ Got Chat cURL")

    # Step 2: Home cURL
    print_step(2, "Get Home photos data")
    print("""
1. In Learning Genie, click on the "Home" tab
2. In DevTools Network tab, look for new requests
3. Find a request to "api2.learning-genie.com" (like Notes)
4. Right-click that request → "Copy as cURL"
""")

    lg_curl = get_multiline_input("Paste the cURL command here:")

    if not lg_curl or 'curl' not in lg_curl.lower():
        print("\nNo valid cURL detected. Skipping Home photos.")
        lg_curl = None
    else:
        print("\n✓ Got Home cURL")

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
    print("Drag those folders into Apple Photos to import them.\n")


if __name__ == '__main__':
    main()
