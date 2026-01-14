# Learning Genie Media Downloader

Download photos and videos from Learning Genie with embedded metadata (dates, location, titles) for easy import into your photo library.

## Quick Start

### 1. Install dependencies (macOS)

```bash
brew install exiftool
pip3 install playwright && playwright install chromium
```

### 2. Run sync

```bash
./sync.py
```

That's it! The tool will:
1. Open a browser and log in to Learning Genie
2. Fetch your photos from the Home and Chat tabs
3. Download everything with embedded metadata (dates, GPS, titles)

<details>
<summary>Manual mode (if browser automation doesn't work)</summary>

If you can't use browser automation, run `./sync.py --manual` and follow the prompts to copy cURL commands from Chrome DevTools.

</details>

Photos are organized and deduplicated automatically:
```
photos/
├── new/                    ← NEW files from last sync (import these!)
│   ├── home/
│   └── chat/
│       ├── Bluey_Heeler/
│       └── Bingo_Heeler/
├── home/                   ← All Home tab photos
└── chat/
    ├── Bluey_Heeler/
    └── Bingo_Heeler/
```

After each sync, import from `photos/new/` - it mirrors the folder structure so you can add each to separate albums.

---

## Project Structure

```
├── sync.py               # Interactive tool - start here!
├── login.py              # Browser automation for --auto mode
├── fetch.py              # Fetches JSON data from Learning Genie
├── download.py           # Downloads photos to dated folders
├── config.json           # Your settings (auto-generated)
├── data/
│   ├── notes.json        # Home tab data
│   └── message.json      # Chat tab data
├── photos/
│   ├── new/                 # New files from last sync (mirrors structure below)
│   ├── home/                # All Home tab photos
│   └── chat/
│       └── Child_Name/      # Chat photos per kid
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

## Password Options

Your email is saved to `config.json` after the first run. For the password, the tool checks (in order):

1. **1Password CLI**: Set up with `op://vault/Learning Genie/password` path
2. **Environment variable**: `export LG_PASSWORD=yourpassword`
3. **Prompt**: Asked each time if neither above is configured

---

## Troubleshooting

### Photos not showing correct date
Make sure `exiftool` is installed: `brew install exiftool`

### Want to re-download everything
Delete the photos folder and run sync again.

---

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
ruff check .                 # Lint
.venv/bin/pytest tests/ -v   # Test
```
