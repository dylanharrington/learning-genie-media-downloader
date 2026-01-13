# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python tool to download photos and videos from Learning Genie (daycare/school app) with embedded EXIF metadata for importing into photo libraries. Supports automatic browser-based login or manual cURL token extraction.

## Commands

```bash
./sync.py --auto             # Auto-login via browser (recommended)
./sync.py                    # Manual mode (copy cURL commands)
./login.py                   # Just the auto-login step
./login.py --no-headless     # Show browser window (debugging)

./fetch.py --lg-curl '...'   # Fetch Home tab data (manual)
./fetch.py --qb-curl '...'   # Fetch Chat tab data (manual)
./fetch.py --all --lg-curl '...'  # Force full re-fetch
./download.py                # Download photos from fetched data

# Linting and testing (requires .venv)
ruff check .                 # Lint
.venv/bin/pytest tests/ -v   # Test
```

## Architecture

**Two data sources requiring separate authentication:**
- Home tab: Learning Genie API (`api2.learning-genie.com`) using `lg_session` cookie + `x-uid` header
- Chat tab: QuickBlox API (`apilearninggenie.quickblox.com`) using `QB-Token` header

**Data flow:**
1. `login.py` uses Playwright to automate browser login and capture auth tokens (or user provides cURL commands manually)
2. `fetch.py` uses tokens to fetch JSON to `data/notes.json` and `data/message.json`
3. `download.py` orchestrates the two download scripts
4. `scripts/download_home.py` and `scripts/download_chat.py` do parallel downloads and set EXIF metadata via exiftool

**Key patterns:**
- Incremental sync tracked via `.last_sync` JSON (timestamps for each source)
- Photos organized into dated folders (`photos/home/2025-01-13/`, `photos/chat/Kid_Name/2025-01-13/`)
- Config stored in `config.json`: location, email, 1Password path
- Password resolution: 1Password CLI (`op read`) → `LG_PASSWORD` env var → interactive prompt
- Both download scripts share similar structure: parse JSON, generate unique filenames with date counts, parallel download with ThreadPoolExecutor, set EXIF metadata
