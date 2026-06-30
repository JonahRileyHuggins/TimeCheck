# TimeCheck

Personal time tracking built around a simple hierarchy: **areas → projects → tasks → log**. Data is stored as TSV files on your machine. A desktop app handles day-to-day entry; a Python API is available if you want to script or extend it.

Inspired by this [Google Sheet workflow](https://docs.google.com/spreadsheets/d/1Tlhj378cqieScJ_cXmFGz7GoQKWdbP_mkyMPY1mJUAA/edit).

## Install the desktop app (Windows)

**Recommended for most users.** No Python install required.

1. Download **[TimeCheck-v0.1.0-windows.zip](https://github.com/JonahRileyHuggins/TimeCheck/raw/v0.1.0/releases/TimeCheck-v0.1.0-windows.zip)** from the [`v0.1.0`](https://github.com/JonahRileyHuggins/TimeCheck/releases/tag/v0.1.0) release, or pick up the latest build under **[Releases](https://github.com/JonahRileyHuggins/TimeCheck/releases)**.
2. Unzip anywhere (e.g. `Documents\TimeCheck`).
3. Run **`TimeCheck.exe`**.

The app includes tabs matching the original spreadsheet: **Daily**, **Tasks**, **Projects**, **Areas**, **TimeSheet**, and **Summary**.

### First run

1. **Areas** — add categories (PhD, Business, …) and optional weekly hour limits.
2. **Projects** — assign each project to an area.
3. **Tasks** — assign each task to a project.
4. **TimeSheet** — choose which areas appear on the daily timesheet.
5. **Daily** — pick a task, enter minutes worked, add notes, click **Log Entry**.

You can also **File → Import Google Sheet (.xlsx)...** after exporting your spreadsheet from Google Sheets.

### Where your data lives

By default the app creates a profile folder on first use. For backup across devices, store that folder inside OneDrive, iCloud Drive, or similar—the app reads and writes plain TSV files that sync clients handle normally.

**Do not commit personal time data to a public git repository.** Logs and notes can contain private details.

Profile location mappings are stored locally at `%APPDATA%\TimeCheck\profiles.json` (Windows) or `~/.timecheck/profiles.json` (macOS/Linux).

---

## Python API (developers)

Requires Python 3.10+ and pandas.

```bash
git clone https://github.com/JonahRileyHuggins/TimeCheck.git
cd TimeCheck
pip install -e ".[import]"   # optional: openpyxl for Google Sheet import
```

```python
from pathlib import Path
from timecheck import TimeCheck

# Register a cloud-synced data folder once
tc = TimeCheck(data_root=Path.home() / "OneDrive" / "TimeCheck", name="Jonah")

# Later sessions
tc = TimeCheck(name="Jonah")

tc.log_entry("Draft outline", notes="Section 1 done")
tc.save()
```

Launch the GUI from source:

```bash
timecheck-gui --name Jonah
```

### Data model

| Table       | File            | Role                          |
|-------------|-----------------|-------------------------------|
| `areas`     | `areas.tsv`     | Top-level categories          |
| `projects`  | `projects.tsv`  | Projects within an area       |
| `tasks`     | `tasks.tsv`     | Work items you log time against |
| `log`       | `log.tsv`       | Timestamped sessions          |
| `timesheet` | `timesheet.tsv` | Daily rollups by area         |

### Automatic rollups (triggers)

When you use `tc.add()`, `tc.update()`, `tc.delete()`, or `tc.log_entry()`:

- Log entries update task, project, and area **time log** totals.
- Configured timesheet areas get daily and 7-day rollups.
- Weekly hour limits can fire **alerts** (see `tc.check_alerts()`).

Enable timesheet areas:

```python
tc.set_timesheet_areas(["PhD", "Business"])
```

### Metrics and alerts

```python
for area in tc.metrics.areas():
    print(area.name, area.time_log)

weekly = tc.metrics.weekly()
alerts = tc.check_alerts(dispatch=True)
```

### Build the Windows executable yourself

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name TimeCheck src/gui/entrypoint.py
# Output: dist/TimeCheck.exe
```

See `TimeCheck.spec` for the current PyInstaller configuration.

---

## Project layout

```
TimeCheck/
├── releases/           # tagged release binaries
├── src/timecheck/      # Python library
├── src/gui/            # Tkinter app
└── TimeCheck.spec      # PyInstaller config
```

Schema definitions: `src/timecheck/registry.py`.

## About

This project started as Jonah Huggins' spreadsheet for tracking time, then became a testbed for AI-assisted scaffolding. The core CRUD layer is hand-written; triggers, metrics, alerts, GUI, and most documentation were built with **Composer** (Cursor). Treat as prototype code—review before relying on it for anything critical.

License: see [BSL.txt](BSL.txt).
