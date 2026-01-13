#!/usr/bin/env python3
"""
Fetch Learning Genie data using tokens extracted from cURL commands.

Usage:
    ./fetch.py --qb-curl 'curl ...'      # Fetch Chat messages
    ./fetch.py --lg-curl 'curl ...'      # Fetch Home notes
    ./fetch.py --qb-token TOKEN --lg-session SESSION --x-uid UID  # Direct tokens

Get cURL commands from Chrome DevTools (Network tab → right-click → Copy as cURL):
    - Chat:  Any request to quickblox.com (e.g., Dialog.json)
    - Home:  Any request to api2.learning-genie.com
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

QUICKBLOX_API = 'https://apilearninggenie.quickblox.com'
LG_API = 'https://api2.learning-genie.com'
SCRIPT_DIR = Path(__file__).parent


def parse_curl(curl_cmd):
    """Extract headers and URL from a cURL command."""
    url_match = re.search(r"curl\s+'([^']+)'", curl_cmd)
    if not url_match:
        url_match = re.search(r'curl\s+"([^"]+)"', curl_cmd)
    url = url_match.group(1) if url_match else None

    headers = {}
    header_matches = re.findall(r"-H\s+'([^:]+):\s*([^']*)'", curl_cmd)
    if not header_matches:
        header_matches = re.findall(r'-H\s+"([^:]+):\s*([^"]*)"', curl_cmd)
    for key, value in header_matches:
        headers[key] = value

    cookie_match = re.search(r"-b\s+'([^']+)'", curl_cmd)
    if cookie_match:
        headers['Cookie'] = cookie_match.group(1)

    return url, headers


def fetch_json(url, headers):
    """Fetch JSON from URL with headers."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"URL: {url}")
        return None


def fetch_messages(qb_token):
    """Fetch all messages from all dialogs using QuickBlox token."""
    headers = {
        'Accept': 'application/json',
        'QB-Token': qb_token,
    }

    print("Fetching dialogs...")
    dialogs_url = f"{QUICKBLOX_API}/chat/Dialog.json?limit=200&sort_desc=last_message_date_sent"
    dialogs = fetch_json(dialogs_url, headers)

    if not dialogs or 'items' not in dialogs:
        print("Failed to fetch dialogs")
        return None

    print(f"Found {len(dialogs['items'])} dialogs")

    all_messages = []

    for dialog in dialogs['items']:
        dialog_id = dialog['_id']
        dialog_name = dialog.get('name', 'Unknown')
        print(f"  Fetching messages from: {dialog_name}")

        messages_url = f"{QUICKBLOX_API}/chat/Message.json?chat_dialog_id={dialog_id}&limit=10000&skip=0&sort_desc=date_sent"
        messages = fetch_json(messages_url, headers)

        if messages and 'items' in messages:
            print(f"    Got {len(messages['items'])} messages")
            # Add dialog name to each message for organizing by kid
            for msg in messages['items']:
                msg['_dialog_name'] = dialog_name
            all_messages.extend(messages['items'])

    print(f"Total messages: {len(all_messages)}")
    return {'items': all_messages, 'skip': 0, 'limit': len(all_messages)}


def fetch_notes(lg_session, x_uid):
    """Fetch all notes for all enrolled children using Learning Genie session."""
    headers = {
        'Accept': 'application/json',
        'x-lg-platform': 'web',
        'x-uid': x_uid,
        'Cookie': f'lg_session={lg_session}',
    }

    print("Fetching enrollments...")
    enrollments = fetch_json(f"{LG_API}/api/v1/Enrollments?parent_id={x_uid}", headers)
    if not enrollments:
        print("Could not fetch enrollments")
        return None

    print(f"Found {len(enrollments)} enrolled child(ren):")
    for e in enrollments:
        name = e.get('display_name') or f"{e.get('first_name', '')} {e.get('last_name', '')}"
        print(f"  - {name}")

    all_notes = []

    for enrollment in enrollments:
        enrollment_id = enrollment.get('id')
        child_name = enrollment.get('display_name') or f"{enrollment.get('first_name', '')} {enrollment.get('last_name', '')}"

        print(f"Fetching notes for {child_name}...")
        notes_url = f"{LG_API}/api/v1/Notes?before_time=2035-01-01%2000:00:00.000&count=10000&enrollment_id={enrollment_id}&note_category=report&video_book=true"

        notes = fetch_json(notes_url, headers)

        if notes:
            print(f"  Got {len(notes)} notes")
            all_notes.extend(notes)

    print(f"Total notes: {len(all_notes)}")
    return all_notes


def main():
    parser = argparse.ArgumentParser(description='Fetch Learning Genie data')
    parser.add_argument('--qb-curl', help='cURL command from QuickBlox (Dialog.json or Message.json)')
    parser.add_argument('--lg-curl', help='cURL command from Learning Genie (Notes or any api2 request)')
    # Direct token arguments (used by login.py)
    parser.add_argument('--qb-token', help='QuickBlox token (alternative to --qb-curl)')
    parser.add_argument('--lg-session', help='Learning Genie session cookie (alternative to --lg-curl)')
    parser.add_argument('--x-uid', help='Learning Genie x-uid header (use with --lg-session)')
    parser.add_argument('--messages-out', default='data/message.json', help='Output file for messages')
    parser.add_argument('--notes-out', default='data/notes.json', help='Output file for notes')
    args = parser.parse_args()

    # Check for either cURL or direct tokens
    has_qb = args.qb_curl or args.qb_token
    has_lg = args.lg_curl or (args.lg_session and args.x_uid)

    if not has_qb and not has_lg:
        parser.print_help()
        print("\nExample:")
        print("  ./fetch.py --qb-curl 'curl https://apilearninggenie.quickblox.com/...'")
        sys.exit(1)

    # Ensure data directory exists
    os.makedirs(SCRIPT_DIR / 'data', exist_ok=True)

    # Fetch messages if QB token available
    qb_token = args.qb_token
    if args.qb_curl and not qb_token:
        url, headers = parse_curl(args.qb_curl)
        qb_token = headers.get('QB-Token')

    if qb_token:
        print(f"Found QB-Token: {qb_token[:50]}...")
        messages = fetch_messages(qb_token)

        if messages and messages['items']:
            with open(args.messages_out, 'w') as f:
                json.dump(messages, f, indent=2)
            print(f"Saved {len(messages['items'])} messages to {args.messages_out}")

    # Fetch notes if LG tokens available
    lg_session = args.lg_session
    x_uid = args.x_uid

    if args.lg_curl and not (lg_session and x_uid):
        url, headers = parse_curl(args.lg_curl)

        cookie = headers.get('Cookie', '')
        session_match = re.search(r'lg_session=([^;]+)', cookie)
        if session_match:
            lg_session = session_match.group(1)

        x_uid = headers.get('x-uid')

    if lg_session and x_uid:
        print(f"Found lg_session: {lg_session[:30]}...")
        print(f"Found x-uid: {x_uid}")

        notes = fetch_notes(lg_session, x_uid)

        if notes and len(notes) > 0:
            with open(args.notes_out, 'w') as f:
                json.dump(notes, f, indent=2)
            print(f"Saved {len(notes)} notes to {args.notes_out}")


if __name__ == '__main__':
    main()
