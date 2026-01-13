#!/usr/bin/env python3
"""
Configuration management for Learning Genie downloader.
"""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / 'config.json'

DEFAULT_CONFIG = {
    'location': None,  # Will be set on first run
    'email': None,     # Learning Genie login email
    'op_path': None,   # 1Password path for password (e.g., "op://Private/Learning Genie/password")
}


def load_config():
    """Load config from file, or return defaults."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                return {**DEFAULT_CONFIG, **config}
        except (OSError, json.JSONDecodeError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save config to file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_location():
    """Get configured location, or None if not set."""
    config = load_config()
    return config.get('location')


def get_email():
    """Get configured email, or None if not set."""
    config = load_config()
    return config.get('email')


def set_email(email):
    """Set the login email."""
    config = load_config()
    config['email'] = email
    save_config(config)
    return email


def get_op_path():
    """Get 1Password path for password, or None if not set."""
    config = load_config()
    return config.get('op_path')


def set_op_path(op_path):
    """Set the 1Password path for password retrieval."""
    config = load_config()
    config['op_path'] = op_path
    save_config(config)
    return op_path


def set_location(name, address, city, state, country, latitude, longitude):
    """Set the school location."""
    config = load_config()
    config['location'] = {
        'name': name,
        'address': address,
        'city': city,
        'state': state,
        'country': country,
        'latitude': latitude,
        'longitude': longitude,
    }
    save_config(config)
    return config['location']


DE_ANZA_LOCATION = {
    'name': 'De Anza Child Development Center',
    'address': '21250 Stevens Creek Blvd',
    'city': 'Cupertino',
    'state': 'California',
    'country': 'United States',
    'latitude': 37.3195,
    'longitude': -122.0448,
}


def prompt_for_location():
    """Interactive prompt to configure location."""
    print("\n" + "="*60)
    print("  Location Setup")
    print("="*60)
    print("""
Photos can be tagged with your school's GPS location so they
show up on the map in your photo app.

Which school?
  [1] De Anza Child Development Center (Cupertino, CA)
  [2] Other school (enter your own)
  [3] Skip - don't add location to photos
""")

    choice = input("Enter 1, 2, or 3: ").strip()

    if choice == '1':
        # De Anza preset
        config = load_config()
        config['location'] = DE_ANZA_LOCATION
        save_config(config)
        print(f"\n✓ Location set: {DE_ANZA_LOCATION['name']}")
        return DE_ANZA_LOCATION

    if choice == '3' or choice.lower() in ('skip', 's', 'n', 'no', ''):
        print("\nSkipping location. Photos won't have GPS coordinates.")
        config = load_config()
        config['location'] = False  # Explicitly disabled
        save_config(config)
        return None

    # Custom location
    print("\nEnter your school's information:\n")

    name = input("School name: ").strip()
    if not name:
        print("No name entered. Skipping location setup.")
        config = load_config()
        config['location'] = False
        save_config(config)
        return None

    address = input("Street address: ").strip()
    city = input("City: ").strip()
    state = input("State/Province: ").strip()
    country = input("Country [United States]: ").strip() or "United States"

    # Get coordinates
    print("\nTo get GPS coordinates:")
    print("  1. Go to Google Maps and search for your school")
    print("  2. Right-click on the school's location")
    print("  3. Click the coordinates at the top of the menu (e.g., 37.3195, -122.0448)")
    print("  4. They're now copied - paste them below")
    coords = input("\nPaste coordinates (or press Enter to skip GPS): ").strip()

    latitude = None
    longitude = None
    if coords:
        try:
            parts = coords.replace(',', ' ').split()
            latitude = float(parts[0])
            longitude = float(parts[1])
        except (ValueError, IndexError):
            print("Couldn't parse coordinates. GPS will be skipped.")

    location = set_location(name, address, city, state, country, latitude, longitude)

    print(f"\n✓ Location saved: {name}")
    if latitude and longitude:
        print(f"  GPS: {latitude}, {longitude}")

    return location
