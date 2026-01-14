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
BUILD_DIR = SCRIPT_DIR / "build"
DIST_DIR = SCRIPT_DIR / "dist"
BUNDLE_DIR = BUILD_DIR / "bundle_data"


def find_exiftool():
    """Find the exiftool installation."""
    result = subprocess.run(["which", "exiftool"], capture_output=True, text=True)
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
    dest_exiftool = dest / "exiftool"
    if dest_exiftool.exists():
        shutil.rmtree(dest_exiftool)

    print(f"Copying exiftool to {dest_exiftool}...")

    # Copy bin and lib directories
    dest_exiftool.mkdir(parents=True)
    shutil.copytree(exiftool_dir / "bin", dest_exiftool / "bin")
    shutil.copytree(exiftool_dir / "libexec", dest_exiftool / "libexec")

    return dest_exiftool


def create_wrapper_script():
    """Create a wrapper script that sets up paths before running the app."""
    wrapper = SCRIPT_DIR / "app_main.py"
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
        # Use ~/Documents/LearningGenie for user data
        data_dir = Path.home() / 'Documents' / 'LearningGenie'
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

    # Point Playwright to standard system location (not PyInstaller temp dir)
    if getattr(sys, 'frozen', False):
        # Use the default Playwright cache location so pre-installed browsers work
        browsers_dir = Path.home() / 'Library' / 'Caches' / 'ms-playwright'
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browsers_dir)

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
            except Exception as e:
                browser_error = str(e)
    except ImportError:
        browser_error = "playwright not available"

    # Browser not available - try to install
    print("Chromium browser not found. Attempting to install...")
    print("This may take a few minutes...\\n")

    # In frozen mode, we need to use npx playwright or direct download
    if getattr(sys, 'frozen', False):
        # Try npx playwright (if Node.js is installed)
        import shutil
        npx_path = shutil.which('npx')
        if npx_path:
            try:
                print("Trying: npx playwright install chromium")
                subprocess.run(
                    [npx_path, 'playwright', 'install', 'chromium'],
                    check=True
                )
                return True
            except subprocess.CalledProcessError:
                pass

        # Give user clear instructions
        print("\\n" + "="*60)
        print("CHROMIUM INSTALLATION REQUIRED")
        print("="*60)
        print("\\nThe auto-login feature requires Chromium browser.")
        print("\\nPlease install it by running ONE of these commands:")
        print("\\n  Option 1 (if you have Node.js):")
        print("    npx playwright install chromium")
        print("\\n  Option 2 (if you have Python):")
        print("    pip3 install playwright && python3 -m playwright install chromium")
        print("\\n  Option 3: Use manual mode (no browser needed):")
        print("    Run this app with --manual flag")
        print("\\n" + "="*60)
        return False
    else:
        # Not frozen - use sys.executable
        try:
            subprocess.run(
                [sys.executable, '-m', 'playwright', 'install', 'chromium'],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            print("\\nError: Could not install Chromium.")
            print("Please run manually: python3 -m playwright install chromium")
            return False


def main():
    # Quick exit for --help
    if '--help' in sys.argv or '-h' in sys.argv:
        print("LearningGenie Downloader")
        print()
        print("Usage: LearningGenie Downloader [--manual]")
        print()
        print("Options:")
        print("  --manual    Use manual cURL copying instead of browser automation")
        print("  --help      Show this help message")
        print()
        print("On first run, Chromium browser will be downloaded (~150MB).")
        print("Photos are saved to ~/Documents/LearningGenie/")
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
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "LearningGenie Downloader",
        "--onefile",
        "--console",  # Keep console for now so we can see output
        "--add-data",
        f"{BUNDLE_DIR / 'exiftool'}:exiftool",
        "--add-data",
        "config.py:.",
        "--add-data",
        "fetch.py:.",
        "--add-data",
        "download.py:.",
        "--add-data",
        "login.py:.",
        "--add-data",
        "sync.py:.",
        "--add-data",
        "scripts:scripts",
        "--hidden-import",
        "playwright",
        "--hidden-import",
        "playwright.sync_api",
        "--collect-all",
        "playwright",
        "--noconfirm",
        str(wrapper_script),
    ]

    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print("PyInstaller failed!")
        sys.exit(1)

    print("\\nBuild complete!")
    print(f"Executable: {DIST_DIR / 'LearningGenie Downloader'}")


def main():
    print("=" * 60)
    print("Building LearningGenie Downloader")
    print("=" * 60 + "\\n")

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


if __name__ == "__main__":
    main()
