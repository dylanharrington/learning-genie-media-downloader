#!/usr/bin/env python3
"""
Fetch Learning Genie data using tokens extracted from cURL commands.

Usage:
    ./fetch.py --qb-curl 'curl ...'      # Fetch Chat messages (incremental)
    ./fetch.py --lg-curl 'curl ...'      # Fetch Home notes (incremental)
    ./fetch.py --all --qb-curl '...'     # Fetch ALL data (ignore last sync)

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
from datetime import datetime
from pathlib import Path

QUICKBLOX_API = 'https://apilearninggenie.quickblox.com'
LG_API = 'https://api2.learning-genie.com'
SCRIPT_DIR = Path(__file__).parent
LAST_SYNC_FILE = SCRIPT_DIR / '.last_sync'


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


def load_last_sync():
    """Load last sync timestamps from file."""
    if LAST_SYNC_FILE.exists():
        try:
            with open(LAST_SYNC_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_last_sync(data):
    """Save sync timestamps to file."""
    existing = load_last_sync()
    existing.update(data)
    with open(LAST_SYNC_FILE, 'w') as f:
        json.dump(existing, f, indent=2)


def fetch_messages(qb_token, since_timestamp=None):
    """Fetch messages from all dialogs using QuickBlox token."""
    headers = {
        'Accept': 'application/json',
        'QB-Token': qb_token,
    }

    print("Fetching dialogs...")
    dialogs_url = f"{QUICKBLOX_API}/chat/Dialog.json?limit=200&sort_desc=last_message_date_sent"
    dialogs = fetch_json(dialogs_url, headers)

    if not dialogs or 'items' not in dialogs:
        print("Failed to fetch dialogs")
        return None, None

    print(f"Found {len(dialogs['items'])} dialogs")

    all_messages = []
    latest_timestamp = None

    for dialog in dialogs['items']:
        dialog_id = dialog['_id']
        dialog_name = dialog.get('name', 'Unknown')
        print(f"  Fetching messages from: {dialog_name}")

        # Build URL with optional since filter
        messages_url = f"{QUICKBLOX_API}/chat/Message.json?chat_dialog_id={dialog_id}&limit=10000&skip=0&sort_desc=date_sent"
        if since_timestamp:
            # QuickBlox uses Unix timestamp for date_sent
            messages_url += f"&date_sent[gt]={since_timestamp}"

        messages = fetch_json(messages_url, headers)

        if messages and 'items' in messages:
            print(f"    Got {len(messages['items'])} messages")
            # Add dialog name to each message for organizing by kid
            for msg in messages['items']:
                msg['_dialog_name'] = dialog_name
            all_messages.extend(messages['items'])

            # Track latest timestamp
            for msg in messages['items']:
                msg_ts = msg.get('date_sent', 0)
                if msg_ts and (latest_timestamp is None or msg_ts > latest_timestamp):
                    latest_timestamp = msg_ts

    print(f"Total messages: {len(all_messages)}")
    return {'items': all_messages, 'skip': 0, 'limit': len(all_messages)}, latest_timestamp


def fetch_notes(lg_session, x_uid, enrollment_id=None, since_time=None):
    """Fetch notes using Learning Genie session."""
    headers = {
        'Accept': 'application/json',
        'x-lg-platform': 'web',
        'x-uid': x_uid,
        'Cookie': f'lg_session={lg_session}',
    }

    if not enrollment_id:
        print("Fetching user profile to find enrollment ID...")
        profile = fetch_json(f"{LG_API}/api/v1/Users/me", headers)
        if profile and 'familyEnrollments' in profile:
            enrollments = profile['familyEnrollments']
            if enrollments:
                enrollment_id = enrollments[0].get('id') or enrollments[0].get('_id')
                child_name = f"{enrollments[0].get('childFirstName', '')} {enrollments[0].get('childLastName', '')}"
                print(f"Found enrollment: {child_name} (ID: {enrollment_id})")

                if len(enrollments) > 1:
                    print("Multiple children found:")
                    for i, e in enumerate(enrollments):
                        eid = e.get('id') or e.get('_id')
                        name = f"{e.get('childFirstName', '')} {e.get('childLastName', '')}"
                        print(f"  {i+1}. {name} (ID: {eid})")
                    print("Using first child. Edit enrollment_id in script for others.")

    if not enrollment_id:
        print("Could not find enrollment ID")
        return None, None

    print("Fetching notes...")
    notes_url = f"{LG_API}/api/v1/Notes?before_time=2035-01-01%2000:00:00.000&count=10000&enrollment_id={enrollment_id}&note_category=report&video_book=true"

    # Add after_time filter if we have a since_time
    if since_time:
        notes_url += f"&after_time={urllib.parse.quote(since_time)}"

    notes = fetch_json(notes_url, headers)

    latest_time = None
    if notes:
        print(f"Fetched {len(notes)} notes")
        # Find the latest note timestamp
        for note in notes:
            for media in note.get('media', []):
                created = media.get('createAtUtc', '')
                if created and (latest_time is None or created > latest_time):
                    latest_time = created

    return notes, latest_time


def main():
    parser = argparse.ArgumentParser(description='Fetch Learning Genie data from cURL commands')
    parser.add_argument('--qb-curl', help='cURL command from QuickBlox (Dialog.json or Message.json)')
    parser.add_argument('--lg-curl', help='cURL command from Learning Genie (Notes or any api2 request)')
    parser.add_argument('--messages-out', default='data/message.json', help='Output file for messages')
    parser.add_argument('--notes-out', default='data/notes.json', help='Output file for notes')
    parser.add_argument('--all', action='store_true', help='Fetch all data (ignore last sync time)')
    args = parser.parse_args()

    if not args.qb_curl and not args.lg_curl:
        parser.print_help()
        print("\nExample:")
        print("  ./fetch.py --qb-curl 'curl https://apilearninggenie.quickblox.com/...'")
        sys.exit(1)

    # Load last sync times
    last_sync = load_last_sync() if not args.all else {}
    new_sync = {}

    if args.all:
        print("Fetching ALL data (ignoring last sync time)\n")
    elif last_sync:
        print("Incremental fetch since last sync")
        if 'messages' in last_sync:
            print(f"  Messages: since {datetime.fromtimestamp(last_sync['messages']).isoformat()}")
        if 'notes' in last_sync:
            print(f"  Notes: since {last_sync['notes']}")
        print()

    # Ensure data directory exists
    os.makedirs(SCRIPT_DIR / 'data', exist_ok=True)

    # Fetch messages if QB cURL provided
    if args.qb_curl:
        url, headers = parse_curl(args.qb_curl)
        qb_token = headers.get('QB-Token')

        if not qb_token:
            print("Error: Could not find QB-Token in cURL command")
            sys.exit(1)

        print(f"Found QB-Token: {qb_token[:50]}...")
        since_ts = last_sync.get('messages') if not args.all else None
        messages, latest_ts = fetch_messages(qb_token, since_ts)

        if messages and messages['items']:
            with open(args.messages_out, 'w') as f:
                json.dump(messages, f, indent=2)
            print(f"Saved {len(messages['items'])} messages to {args.messages_out}")
            if latest_ts:
                new_sync['messages'] = latest_ts
        elif messages:
            print("No new messages since last sync")

    # Fetch notes if LG cURL provided
    if args.lg_curl:
        url, headers = parse_curl(args.lg_curl)

        lg_session = None
        cookie = headers.get('Cookie', '')
        session_match = re.search(r'lg_session=([^;]+)', cookie)
        if session_match:
            lg_session = session_match.group(1)

        x_uid = headers.get('x-uid')

        enrollment_id = None
        if url:
            enroll_match = re.search(r'enrollment_id=([^&]+)', url)
            if enroll_match:
                enrollment_id = enroll_match.group(1)

        if not lg_session:
            print("Error: Could not find lg_session cookie in cURL command")
            sys.exit(1)
        if not x_uid:
            print("Error: Could not find x-uid header in cURL command")
            sys.exit(1)

        print(f"Found lg_session: {lg_session[:30]}...")
        print(f"Found x-uid: {x_uid}")

        since_time = last_sync.get('notes') if not args.all else None
        notes, latest_time = fetch_notes(lg_session, x_uid, enrollment_id, since_time)

        if notes and len(notes) > 0:
            with open(args.notes_out, 'w') as f:
                json.dump(notes, f, indent=2)
            print(f"Saved {len(notes)} notes to {args.notes_out}")
            if latest_time:
                new_sync['notes'] = latest_time
        elif notes is not None:
            print("No new notes since last sync")

    # Save new sync timestamps
    if new_sync:
        save_last_sync(new_sync)
        print("\nUpdated .last_sync")


if __name__ == '__main__':
    main()
