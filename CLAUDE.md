# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python tool to download photos and videos from Learning Genie (daycare/school app) with embedded EXIF metadata for importing into photo libraries. Requires user to copy cURL commands from Chrome DevTools to authenticate.

## Commands

```bash
./sync.py                    # Interactive wizard (main entry point)
./fetch.py --lg-curl '...'   # Fetch Home tab data
./fetch.py --qb-curl '...'   # Fetch Chat tab data
./fetch.py --all --lg-curl '...'  # Force full re-fetch (ignore last sync)
./download.py                # Download photos from fetched data
./download.py --home-only    # Download only Home photos
./download.py --chat-only    # Download only Chat photos

# Linting and testing (requires .venv)
ruff check .                 # Lint all Python files
ruff check . --fix           # Auto-fix linting issues
.venv/bin/pytest tests/ -v   # Run tests
```

## Architecture

**Two data sources requiring separate authentication:**
- Home tab: Learning Genie API (`api2.learning-genie.com`) using `lg_session` cookie + `x-uid` header
- Chat tab: QuickBlox API (`apilearninggenie.quickblox.com`) using `QB-Token` header

**Data flow:**
1. `fetch.py` parses cURL commands to extract auth tokens, fetches JSON to `data/notes.json` and `data/message.json`
2. `download.py` orchestrates the two download scripts
3. `scripts/download_home.py` and `scripts/download_chat.py` do parallel downloads and set EXIF metadata via exiftool

**Key patterns:**
- Incremental sync tracked via `.last_sync` JSON (timestamps for each source)
- Photos organized into dated folders (`photos/home/2025-01-13/`, `photos/chat/Kid_Name/2025-01-13/`)
- Location config stored in `config.json`, prompted on first run via `config.py`
- Both download scripts share similar structure: parse JSON, generate unique filenames with date counts, parallel download with ThreadPoolExecutor, set EXIF metadata
