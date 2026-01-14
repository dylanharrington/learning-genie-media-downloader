#!/usr/bin/env python3
"""
Build script for creating a standalone macOS app bundle.

This script:
1. Copies exiftool into the bundle
2. Runs PyInstaller to create the app
3. Chromium is downloaded on first run via Playwright

Usage:
    python build_app.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BUILD_DIR = SCRIPT_DIR / 'build'
DIST_DIR = SCRIPT_DIR / 'dist'
BUNDLE_DIR = BUILD_DIR / 'bundle_data'


def find_exiftool():
    """Find the exiftool installation."""
    result = subprocess.run(['which', 'exiftool'], capture_output=True, text=True)
    if result.returncode != 0:
        print("Error: exiftool not found. Install with: brew install exiftool")
        sys.exit(1)

    exiftool_path = Path(result.stdout.strip())
    # Resolve symlink to get actual path
    exiftool_real = exiftool_path.resolve()
    # Get the Cellar directory (contains lib/ with Perl modules)
    exiftool_dir = exiftool_real.parent.parent
    print(f"Found exiftool: {exiftool_dir}")
    return exiftool_dir


def copy_exiftool(exiftool_dir, dest):
    """Copy exiftool to bundle."""
    dest_exiftool = dest / 'exiftool'
    if dest_exiftool.exists():
        shutil.rmtree(dest_exiftool)

    print(f"Copying exiftool to {dest_exiftool}...")

    # Copy bin and lib directories
    dest_exiftool.mkdir(parents=True)
    shutil.copytree(exiftool_dir / 'bin', dest_exiftool / 'bin')
    shutil.copytree(exiftool_dir / 'libexec', dest_exiftool / 'libexec')

    return dest_exiftool


def create_wrapper_script():
    """Create a wrapper script that sets up paths before running the app."""
    wrapper = SCRIPT_DIR / 'app_main.py'
    wrapper.write_text('''#!/usr/bin/env python3
"""
Main entry point for the bundled app.
Sets up paths for bundled exiftool and ensures Chromium is installed.
"""

import os
import subprocess
import sys
from pathlib import Path


def get_bundle_dir():
    """Get the directory where bundled data is stored."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent / 'build' / 'bundle_data'


def get_data_dir():
    """Get the data directory for user files (config, photos, etc)."""
    if getattr(sys, 'frozen', False):
        # Use ~/Documents/Learning Genie for user data
        data_dir = Path.home() / 'Documents' / 'Learning Genie'
    else:
        data_dir = Path(__file__).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def setup_environment():
    """Set up environment for bundled dependencies."""
    bundle_dir = get_bundle_dir()
    data_dir = get_data_dir()

    # Add exiftool to PATH
    exiftool_bin = bundle_dir / 'exiftool' / 'bin'
    if exiftool_bin.exists():
        os.environ['PATH'] = str(exiftool_bin) + os.pathsep + os.environ.get('PATH', '')

    # Set working directory to data dir for config/photos
    os.chdir(data_dir)

    return data_dir


def ensure_chromium():
    """Ensure Playwright Chromium is installed."""
    try:
        from playwright.sync_api import sync_playwright
        # Quick check if browser works
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                return True
            except Exception:
                pass
    except ImportError:
        pass

    print("Installing Chromium browser (first run only)...")
    print("This may take a few minutes...\\n")

    try:
        subprocess.run(
            [sys.executable, '-m', 'playwright', 'install', 'chromium'],
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        print("\\nError: Could not install Chromium.")
        print("Please run manually: playwright install chromium")
        return False


def main():
    # Quick exit for --help
    if '--help' in sys.argv or '-h' in sys.argv:
        print("Learning Genie Downloader")
        print()
        print("Usage: Learning Genie Downloader [--manual]")
        print()
        print("Options:")
        print("  --manual    Use manual cURL copying instead of browser automation")
        print("  --help      Show this help message")
        print()
        print("On first run, Chromium browser will be downloaded (~150MB).")
        print("Photos are saved to ~/Documents/Learning Genie/")
        return

    data_dir = setup_environment()

    print(f"Data directory: {data_dir}")
    print()

    # Ensure Chromium is available (skip for manual mode)
    if '--manual' not in sys.argv:
        if not ensure_chromium():
            sys.exit(1)

    # Import and run the actual sync
    bundle_dir = get_bundle_dir()
    sys.path.insert(0, str(bundle_dir))
    sys.path.insert(0, str(bundle_dir / 'scripts'))

    from sync import main as sync_main
    sync_main()


if __name__ == '__main__':
    main()
''')
    print(f"Created wrapper script: {wrapper}")
    return wrapper


def run_pyinstaller(wrapper_script):
    """Run PyInstaller to create the app bundle."""
    print("\\nRunning PyInstaller...")

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', 'Learning Genie Downloader',
        '--onefile',
        '--console',  # Keep console for now so we can see output
        '--add-data', f'{BUNDLE_DIR / "exiftool"}:exiftool',
        '--add-data', 'config.py:.',
        '--add-data', 'fetch.py:.',
        '--add-data', 'download.py:.',
        '--add-data', 'login.py:.',
        '--add-data', 'sync.py:.',
        '--add-data', 'scripts:scripts',
        '--hidden-import', 'playwright',
        '--hidden-import', 'playwright.sync_api',
        '--collect-all', 'playwright',
        '--noconfirm',
        str(wrapper_script),
    ]

    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print("PyInstaller failed!")
        sys.exit(1)

    print("\\nBuild complete!")
    print(f"Executable: {DIST_DIR / 'Learning Genie Downloader'}")


def main():
    print("="*60)
    print("Building Learning Genie Downloader")
    print("="*60 + "\\n")

    # Find exiftool
    exiftool_dir = find_exiftool()

    # Create bundle directory
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    # Copy exiftool
    copy_exiftool(exiftool_dir, BUNDLE_DIR)

    # Create wrapper script
    wrapper = create_wrapper_script()

    # Run PyInstaller
    run_pyinstaller(wrapper)


if __name__ == '__main__':
    main()
