#!/usr/bin/env python3
"""
Automated login to Learning Genie using Playwright.

Captures authentication tokens by intercepting network requests,
then triggers a full sync.

Usage:
    ./login.py           # Login and sync
    ./login.py --tokens  # Just print tokens (for debugging)
"""

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from config import get_email, get_op_path, set_email, set_op_path

LG_WEB_URL = 'https://web.learning-genie.com'


def get_password_from_1password(op_path):
    """Try to get password from 1Password CLI."""
    try:
        result = subprocess.run(
            ['op', 'read', op_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def get_credentials():
    """Get email and password from config/env/prompt."""
    # Email: config → prompt (and save)
    email = get_email()
    if not email:
        email = input("Learning Genie email: ").strip()
        if email:
            set_email(email)
            print("✓ Email saved to config.json")

    if not email:
        print("Error: Email is required")
        sys.exit(1)

    # Password: 1Password → env var → prompt
    password = None

    # Try 1Password
    op_path = get_op_path()
    if op_path:
        password = get_password_from_1password(op_path)
        if password:
            print("✓ Got password from 1Password")

    # Try environment variable
    if not password:
        password = os.environ.get('LG_PASSWORD')
        if password:
            print("✓ Got password from LG_PASSWORD env var")

    # Prompt as fallback
    if not password:
        password = getpass.getpass("Learning Genie password: ")

        # Offer to set up 1Password for next time
        if not op_path:
            print("\nTip: To avoid entering password each time, you can:")
            print("  1. Set LG_PASSWORD environment variable, or")
            print("  2. Use 1Password CLI (op)")
            setup = input("\nSet up 1Password path? (e.g., op://Private/Learning Genie/password) [skip]: ").strip()
            if setup:
                set_op_path(setup)
                print("✓ 1Password path saved to config.json")

    if not password:
        print("Error: Password is required")
        sys.exit(1)

    return email, password


def login_and_capture_tokens(email, password, headless=True):
    """Use Playwright to login and capture auth tokens."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: playwright not installed")
        print("Install with: .venv/bin/pip install playwright && .venv/bin/playwright install chromium")
        sys.exit(1)

    tokens = {
        'lg_session': None,
        'x_uid': None,
        'qb_token': None,
    }

    print(f"\nLaunching browser (headless={headless})...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()

        # Intercept requests to capture tokens
        def handle_request(request):
            url = request.url

            # Capture Learning Genie API tokens
            if 'api2.learning-genie.com' in url:
                headers = request.headers
                if 'x-uid' in headers and not tokens['x_uid']:
                    tokens['x_uid'] = headers['x-uid']
                    print("  ✓ Captured x-uid")

            # Capture QuickBlox token
            if 'quickblox.com' in url:
                headers = request.headers
                if 'qb-token' in headers and not tokens['qb_token']:
                    tokens['qb_token'] = headers['qb-token']
                    print("  ✓ Captured QB-Token")

        context.on('request', handle_request)

        page = context.new_page()

        # Navigate to Learning Genie
        print(f"Navigating to {LG_WEB_URL}...")
        page.goto(LG_WEB_URL)

        # Wait for and fill login form
        print("Waiting for login form...")
        page.wait_for_selector('input[type="email"], input[name="email"], input[placeholder*="email" i]', timeout=15000)

        # Fill email
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first
        email_input.fill(email)

        # Fill password
        password_input = page.locator('input[type="password"]').first
        password_input.fill(password)

        # Submit
        print("Submitting login...")
        submit_button = page.locator('button[type="submit"], input[type="submit"], button:has-text("Log in"), button:has-text("Sign in")').first
        submit_button.click()

        # Wait for redirect to main app (Home tab)
        print("Waiting for login to complete...")
        try:
            page.wait_for_url('**/home**', timeout=30000)
        except Exception:
            # Try alternative URL patterns
            page.wait_for_selector('[class*="home"], [class*="dashboard"], [data-tab="home"]', timeout=30000)

        print("✓ Logged in successfully")

        # Get lg_session from cookies
        cookies = context.cookies()
        for cookie in cookies:
            if cookie['name'] == 'lg_session':
                tokens['lg_session'] = cookie['value']
                print("  ✓ Captured lg_session")
                break

        # Navigate to Chat to capture QB token
        print("\nNavigating to Chat tab...")

        # Look for Chat link/button
        chat_link = page.locator('a:has-text("Chat"), button:has-text("Chat"), [href*="chat"]').first
        chat_link.click()

        # Chat might open in new tab - handle both cases
        page.wait_for_timeout(3000)  # Give time for requests to fire

        # If QB token not captured yet, try to trigger a request
        if not tokens['qb_token']:
            print("  Waiting for Chat API requests...")
            page.wait_for_timeout(5000)

        browser.close()

    return tokens


def run_fetch(tokens):
    """Run fetch.py with captured tokens."""
    print("\n" + "="*60)
    print("Running fetch with captured tokens...")
    print("="*60 + "\n")

    # Build fake cURL commands that fetch.py can parse
    lg_curl = f"curl 'https://api2.learning-genie.com/api/v1/Notes' -H 'x-uid: {tokens['x_uid']}' -H 'Cookie: lg_session={tokens['lg_session']}'"
    qb_curl = f"curl 'https://apilearninggenie.quickblox.com/chat/Dialog.json' -H 'QB-Token: {tokens['qb_token']}'"

    cmd = [sys.executable, str(SCRIPT_DIR / 'fetch.py')]

    if tokens['lg_session'] and tokens['x_uid']:
        cmd.extend(['--lg-curl', lg_curl])

    if tokens['qb_token']:
        cmd.extend(['--qb-curl', qb_curl])

    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    return result.returncode == 0


def run_download():
    """Run download.py."""
    print("\n" + "="*60)
    print("Downloading photos...")
    print("="*60 + "\n")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / 'download.py')],
        cwd=SCRIPT_DIR
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description='Automated Learning Genie login and sync')
    parser.add_argument('--tokens', action='store_true', help='Just print captured tokens (for debugging)')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window (for debugging)')
    args = parser.parse_args()

    print("="*60)
    print("  Learning Genie Auto-Login")
    print("="*60 + "\n")

    email, password = get_credentials()

    tokens = login_and_capture_tokens(email, password, headless=not args.no_headless)

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

    if args.tokens:
        print("\nCaptured tokens:")
        for key, value in tokens.items():
            if value:
                display = value[:50] + '...' if len(value) > 50 else value
                print(f"  {key}: {display}")
            else:
                print(f"  {key}: (not captured)")
        return

    # Run fetch and download
    if tokens['lg_session'] or tokens['qb_token']:
        if run_fetch(tokens):
            run_download()
    else:
        print("\nError: No tokens captured. Cannot proceed with sync.")
        sys.exit(1)


if __name__ == '__main__':
    main()
