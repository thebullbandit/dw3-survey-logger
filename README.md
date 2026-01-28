# DW3 Survey Logger BETA

THIS IS A BETA BUILD!

Logger for **Elite Dangerous** survey runs
(DW3-style), built to run for long sessions and keep your data safe.

It watches your Elite Dangerous **journal files**, detects relevant
events, scores "Earth-like" candidates, and stores everything in
**crash-safe SQLite (WAL)**. Includes an **Observer overlay** for extra
human notes and **drift guardrails** to help keep survey legs straight.

> Current build shown in code: **v0.9.1 BETA**

------------------------------------------------------------------------

## Features

-   **Auto-detects Elite Dangerous journals**
    -   Default journal path (Windows):
        `Saved Games/Frontier Developments/Elite Dangerous`
-   **Crash-safe local storage**
    -   SQLite with **WAL** for durability during long runs
-   **Candidate scoring & classification**
    -   Built-in A/B/C style rating thresholds (temperature, gravity,
        distance, etc.)
-   **Observer overlay (notes)**
    -   Quick popup window to log extra context (flags, confidence,
        sampling method, notes)
-   **Drift Guardrail helpers**
    -   Math utilities for "leg guidance" to reduce sideways drift on
        long survey lines
-   **Export to CSV (timestamped)**
    -   Exports never overwrite old files (timestamped naming)
-   **Hotkey support**
    -   Tries to register a **global hotkey** via `pynput`
    -   Falls back to in-app hotkey if global registration isn't
        available

------------------------------------------------------------------------

## Quick Start (Run from Source)

### Requirements

-   Python 3.x (Windows recommended)
-   Tkinter (included with most Python Windows installs)
-   Optional:
    -   `pynput` for global hotkeys
    -   `pyyaml` if you use YAML config loader
    -   `pywin32` for certain Windows focus helpers (if enabled/used)

### Run

``` bash
python main.py
```

------------------------------------------------------------------------

## Where Your Data Lives

By default the app writes to:

`%USERPROFILE%/Documents/DW3/Earth2/`

Typical files: - `DW3_Earth2.db` (candidates database) -
`DW3_Earth2_Observations.db` (observer notes database) -
`DW3_Earth2_Logger.log` (app log) - `exports/` (timestamped CSV
exports) - `settings.json` (optional settings overrides)

### Settings override (optional)

If this file exists it can override export location: - `settings.json`
supports: - `export_dir`: custom folder for exports

Example:

``` json
{
  "export_dir": "D:/DW3/exports"
}
```

------------------------------------------------------------------------

## Exports

The app can export candidates to CSV, using **timestamped filenames** to
avoid overwriting previous runs.

Exports go to: - default: `Documents/DW3/Earth2/exports/` - or whatever
you set as `export_dir` in `settings.json`

------------------------------------------------------------------------

## Hotkeys

Default observer hotkey behavior: - Attempts global: **Ctrl + Alt +
O** - Falls back to in-app: **Ctrl + O** (works when the app has focus)

If global hotkey registration fails, the app prints/logs a reason and
continues safely.

------------------------------------------------------------------------

## Architecture (For Devs)

This project follows an MVP-ish split plus dedicated services:

-   `model.py`\
    Business logic (no UI), calculations, rules
-   `view.py`\
    Tkinter UI components only
-   `presenter.py`\
    Coordinates model + view, handles UI actions
-   `journal_monitor.py`\
    Journal polling, file rotation, event parsing/routing
-   `earth2_database.py`\
    SQLite persistence for candidates (WAL, schema, inserts)
-   `observer_overlay.py` / `observer_storage.py`\
    Notes UI + persistence
-   `data_manager.py`\
    Higher-level DB operations + export/import helpers

The goal is: **stable long runs** + **diagnosable failures** (log
instead of silently dying).

------------------------------------------------------------------------

## Troubleshooting

**Nothing happens / no data logged** - Verify Elite Dangerous is writing
journals - Check journal folder exists:
`%USERPROFILE%/Saved Games/Frontier Developments/Elite Dangerous`

**Global hotkey doesn't work** - Install optional dependency:
`bash   pip install pynput` - Some environments restrict global hooks;
app will fallback automatically.

**Exports not showing up** - Check: `Documents/DW3/Earth2/exports/` - If
using `settings.json`, confirm `export_dir` path exists or is writable.

------------------------------------------------------------------------

## Status

This is a **beta** project intended for real expedition runs. Expect
iteration, but the storage layer is designed to be durable and safe for
long sessions.

------------------------------------------------------------------------

## License
