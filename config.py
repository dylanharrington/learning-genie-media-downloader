#!/usr/bin/env python3
"""
Configuration management for Learning Genie downloader.
"""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / 'config.json'

DEFAULT_CONFIG = {
    'location': None  # Will be set on first run
}


def load_config():
    """Load config from file, or return defaults."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                return {**DEFAULT_CONFIG, **config}
        except (json.JSONDecodeError, IOError):
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


def prompt_for_location():
    """Interactive prompt to configure location."""
    print("\n" + "="*60)
    print("  Location Setup")
    print("="*60)
    print("""
Photos can be tagged with your school's GPS location so they
show up on the map in your photo app.
""")

    response = input("Do you want to set your school's location? [Y/n] ").strip().lower()

    if response in ('n', 'no'):
        print("\nSkipping location. Photos won't have GPS coordinates.")
        config = load_config()
        config['location'] = False  # Explicitly disabled
        save_config(config)
        return None

    print("\nEnter your school's information:\n")

    name = input("School name: ").strip()
    if not name:
        print("No name entered. Skipping location setup.")
        return None

    address = input("Street address: ").strip()
    city = input("City: ").strip()
    state = input("State/Province: ").strip()
    country = input("Country [United States]: ").strip() or "United States"

    # Get coordinates
    print("\nFor GPS coordinates, you can look up your school on Google Maps,")
    print("right-click, and copy the coordinates (e.g., 37.3195, -122.0448)")
    coords = input("\nCoordinates (lat, lng) or press Enter to skip GPS: ").strip()

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
