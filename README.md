# Learning Genie Media Downloader

Download photos and videos from Learning Genie with embedded metadata (dates, location, titles) for easy import into your photo library.

## Quick Start

### 1. Install requirements

```bash
brew install exiftool   # Mac (for embedding photo metadata)
```

### 2. Run the sync tool

```bash
./sync.py --auto   # Automatic login (recommended)
./sync.py          # Manual mode (copy cURL commands)
```

**Automatic mode** logs in via browser automation - just enter your email and password.

**Manual mode** walks you through copying cURL commands from Chrome DevTools.

### That's it!

Photos are saved to folders you can drag into any photo app:
```
photos/
├── home/
│   └── 2025-01-13/              ← dated folder for incremental imports
└── chat/
    ├── Bluey_Heeler/
    │   └── 2025-01-13/          ← dated folder per kid
    └── Bingo_Heeler/
        └── 2025-01-13/
```

---

## Incremental Sync

The scripts automatically track what you've already downloaded:

```bash
# First run: downloads everything
./fetch.py --qb-curl '...' --lg-curl '...'
./download.py

# Later runs: only downloads new photos
./fetch.py --qb-curl '...' --lg-curl '...'  # Only fetches new data
./download.py                                 # Creates new dated folder

# Force full re-download
./fetch.py --all --qb-curl '...' --lg-curl '...'
```

If you run multiple times per day, folders are numbered: `2025-01-13`, `2025-01-13_2`, etc.

---

## Project Structure

```
├── sync.py               # Interactive tool - start here!
├── fetch.py              # Fetches JSON data from Learning Genie
├── download.py           # Downloads photos to dated folders
├── config.json           # Your school's location (auto-generated)
├── .last_sync            # Tracks last sync time (auto-generated)
├── data/
│   ├── notes.json        # Home tab data
│   └── message.json      # Chat tab data
├── photos/
│   ├── home/
│   │   └── 2025-01-13/      # Dated folders
│   └── chat/
│       └── Child_Name/
│           └── 2025-01-13/  # Dated folders per kid
└── scripts/
    ├── download_home.py
    └── download_chat.py
```

---

## What Gets Downloaded

| Source | Tab | Output |
|--------|-----|--------|
| `data/notes.json` | Home | `photos/home/<date>/` |
| `data/message.json` | Chat | `photos/chat/<kid>/<date>/` |

**Embedded metadata:**
- Date/time (photos appear on correct date in timeline)
- GPS location (shows on map)
- Titles and descriptions (searchable)

---

## Location

On first run, you'll be asked to set your school's location. This embeds GPS coordinates so photos show up on the map in your photo app.

To change later, delete `config.json` and run `./sync.py` again, or edit `config.json` directly.

---

## Automatic Login

The `--auto` flag uses browser automation to log in automatically. Your email is saved to `config.json` after the first run.

**Password options** (checked in order):
1. **1Password CLI**: Set up with `op://vault/Learning Genie/password` path
2. **Environment variable**: `export LG_PASSWORD=yourpassword`
3. **Prompt**: Asked each time if neither above is configured

```bash
# First-time setup
.venv/bin/pip install playwright
.venv/bin/playwright install chromium

# Run with auto-login
./sync.py --auto
```

---

## Troubleshooting

### Token expired (manual mode)
If you get auth errors, the tokens have expired. Go back to Learning Genie, refresh, and copy fresh cURL commands.

### Photos not showing correct date
Make sure `exiftool` is installed: `brew install exiftool`

### Want to re-download everything
Use `--all` flag: `./fetch.py --all --qb-curl '...'`

---

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
ruff check .                 # Lint
.venv/bin/pytest tests/ -v   # Test
```
