# DEVELOPER.md — Phoenix Valve Checkout Tool

---

## Tech Stack

- **Python 3** with **PySide6** (Qt for Python) for the UI
- **openpyxl** for template-based Excel export
- **PyInstaller** (`--onedir --windowed`) to package as a Windows exe
- **Inno Setup 6** to build the installer (`installer.iss`)
- **GitHub Releases** for distribution and auto-updates (`updater.py`)

---

## File Structure

```
checkout_tool_gui.py       — Main UI (MainWindow, dialogs, themes)
checkout_tool_backend.py   — Data model and storage (Job / ValveCheckout / CheckoutStore)
checkout_export.py         — Excel export engine (template-based via openpyxl)
updater.py                 — Auto-update system
version.py                 — Version number (bump before every release)
build.bat                  — Builds exe + installer + zips
installer.iss              — Inno Setup installer script

checkout_template.xlsx     — Celeris Fume Hood / fallback template (12-col)
template_gex.xlsx          — Celeris GEX template (6-col)
template_mav.xlsx          — Celeris MAV template (6-col)
template_cscp_fh.xlsx      — CSCP ACM Fume Hood template (12-col)
template_pbc_room.xlsx     — CSCP PBC Room template (12-col)

PTT_Normal_green.ico       — App icon (exe + installer)
PTT_Transparent_green.png  — Watermark / background logo
```

---

## Data Model

### Job
| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID |
| `job_number` | str | ATS job number |
| `job_name` | str | Project / job name |
| `archived` | bool | `True` = shown in archived section, not active |

### ValveCheckout
| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID |
| `job_id` | str | Parent `Job.id` |
| `valve_tag` | str | Valve/controller identifier, shown in sidebar |
| `project`, `ats_job_number`, `technician`, `description`, `model`, `date` | str | Header fields |
| `valve_type` | str | See valve type table below — drives wiring panels, tab visibility, and export template |
| `pass_fail` | str | `"Pass"` / `"Fail"` / `""` |
| `emer_min`, `valve_min_sp`, `valve_max_sp` | str | CFM setpoints (hidden for PBC Room; validated as integers 0–99999) |
| `wiring` | dict | Keyed by prefix + index + field — see wiring key scheme below |
| `sash_sensor_mounted` | bool | Sash sensor mounting checkbox (Fume Hood types only) |
| `config` | dict | `{key}_cfm` and `{key}_notes` for each CONFIG_ROWS entry |
| `verification` | dict | `{key}_result` and `{key}_notes` for each VERIFY_ROWS entry |
| `notes` | str | Free-form notes |

### Wiring Key Scheme (`record.wiring`)
| Prefix | Panel | Checkbox columns |
|--------|-------|-----------------|
| `p_{i}_{i/w}` | Celeris Phoenix Air Valve | Install / Wired |
| `b_{i}_{i/w}` | Celeris Black Box | Install / Wired |
| `acm_{i}_{i/w}` | CSCP ACM (Actuator Control Module) | Install / Wired |
| `dhv_{i}_{i/w}` | CSCP DHV Black Box | Install / Wired |
| `pbc_l_{i}_{i/w}` | CSCP PBC Left panel (TB1 Inputs / DO / UIO) | Install / Wired |
| `pbc_r_{i}_{i/w}` | CSCP PBC Right panel (Power / Comm / UIO) | Install / Wired |

All wiring dicts for all panel types are saved on every record regardless of current valve type, so switching types never loses data.

Data is persisted at `%APPDATA%\ATS Inc\Phoenix Valve Checkout Tool\data.json`.

### Data Safety
- `_save()` writes to a `.tmp` file first, then `os.replace()` atomically renames it — prevents corruption on crash.
- `_load()` skips individual bad records rather than failing the entire load, using per-record `try/except` and `__dataclass_fields__` filtering.
- JSON schema versioning via `"version": 1` key for future migration support.

---

## Valve Type Behavior Matrix

| Valve Type | Wiring Stack Page | BB Panel | Sash Sensor | Wiring Tab | Config/Verify Tab | SP Fields |
|------------|:-----------------:|:--------:|:-----------:|:----------:|:-----------------:|:---------:|
| Fume Hood | 0 — Celeris | Visible | Visible | Yes | Yes | Yes |
| GEX / MAV / Snorkel / Canopy / Draw Down Bench / Gas Cabinet | 0 — Celeris | Hidden | Hidden | Yes | Yes | Yes |
| CSCP Fume Hood | 1 — CSCP | — | DHV panel | Yes | Yes | Yes |
| PBC Room | 2 — PBC | — | Hidden | Yes | Hidden | Hidden |

### Verification row visibility
| Row key | Visible for |
|---------|-------------|
| `face_velocity`, `sash_height_alarm`, `sash_sensor_output`, `emergency_exhaust` | Fume Hood types only (Celeris FH + CSCP FH) |
| `mute_function` | Celeris Fume Hood only |
| `low_flow_alarm`, `jam_alarm` | All types (except hidden for PBC Room via tab) |

---

## Main UI Structure

```
QMainWindow
└── Central QWidget (QHBoxLayout)
    ├── Sidebar (fixed 270px)
    │   ├── + New Job / + New Checkout / + Batch Add buttons
    │   ├── Search/filter QLineEdit (matches tag, technician, description, valve type)
    │   └── QTreeWidget
    │       ├── Active jobs (bold) with checkout children (colored by pass/fail)
    │       └── Archived Jobs separator + archived job entries (gray italic)
    └── Main area (_BgWidget — floating logo watermark)
        ├── QStackedWidget (4 pages)
        │   ├── Page 0: Welcome / instructions panel (startup / nothing selected)
        │   ├── Page 1: Header panel + QTabWidget (checkout editor)
        │   │   ├── Tab 0: General (fields + valve type dropdown)
        │   │   ├── Tab 1: Wiring (QStackedWidget — 3 panel sets, see below)
        │   │   ├── Tab 2: Config & Verification
        │   │   └── Tab 3: Notes (template snippet dropdown + plain text edit)
        │   ├── Page 2: Archived job summary panel (read-only checkout list)
        │   └── Page 3: Active job summary panel (live checkout list + progress bar)
        └── Update banner (hidden until update available)
```

### Main stack page switching
| Condition | Page |
|-----------|------|
| Nothing selected / tree empty | 0 — Welcome |
| Active checkout selected | 1 — Checkout editor |
| Active job selected | 3 — Active job summary |
| Archived job selected | 2 — Archived job summary |

### Wiring tab stack (inside Tab 1)
| Index | Contents | Used for |
|-------|----------|----------|
| 0 | Celeris splitter: Phoenix panel (left) + Black Box panel (right) | Fume Hood, GEX, MAV, Snorkel, Canopy, Draw Down Bench, Gas Cabinet |
| 1 | CSCP splitter: ACM panel (left) + DHV Black Box panel (right) | CSCP Fume Hood |
| 2 | PBC splitter: TB1/DO/UIO left + Power/Comm/UIO right | PBC Room |

Each wiring panel has **Check All** / **Clear All** buttons at the top. These guard `_loading = True` around all checkbox mutations, then fire a single `_on_any_change()` — no N debounce restarts.

---

## Key Patterns

### Save debounce
`_on_any_change()` → `_save_timer.start(350ms)` → `_save_current()`. When switching records in the tree, `_on_tree_changed` flushes any pending save before loading the new record:
```python
if self._save_timer.isActive():
    self._save_timer.stop()
    self._save_current()
```

### Load guard
`_load_record` sets `self._loading = True` before writing to any widget and `False` when done. `_on_any_change()` returns immediately if `_loading` is set, preventing save-on-load loops. All wiring checkboxes additionally use `blockSignals(True/False)` during load.

### Wiring boards helper
`_wiring_boards()` returns a list of `(checkbox_dict, key_prefix)` tuples for all six wiring panels. Used by both `_load_record` and `_save_current` to eliminate repetition:
```python
for cbs, prefix in self._wiring_boards():
    for (idx, fld), cb in cbs.items():
        cb.blockSignals(True)
        cb.setChecked(w.get(f"{prefix}_{idx}_{fld}", False))
        cb.blockSignals(False)
```

### Checkout panel helper
`_build_checkouts_panel(records, show_type=False)` builds the shared row list widget used by both `_populate_archived_panel` (archived summary) and `_populate_job_panel` (active job summary). The only difference is `show_type=True` for the active job view adds a valve type column.

---

## Export Engine (`checkout_export.py`)

Each valve type has its own fill function and row-map dicts:

| Fill function | Template | Used for |
|---------------|----------|----------|
| `fill_sheet()` | `checkout_template.xlsx` | Celeris Fume Hood + fallback types |
| `fill_sheet_gex_mav()` | `template_gex.xlsx` / `template_mav.xlsx` | GEX, MAV |
| `fill_sheet_cscp_fh()` | `template_cscp_fh.xlsx` | CSCP Fume Hood |
| `fill_sheet_pbc_room()` | `template_pbc_room.xlsx` | PBC Room |

Row-map dicts (enumerate index → Excel row number):
- `_PHOENIX_ROW` / `_BB_ROW` — Celeris Phoenix and Black Box wiring rows
- `_ACM_ROW` / `_DHV_ROW` — CSCP ACM and DHV wiring rows (col F and col L)
- `_PBC_L_ROW` / `_PBC_R_ROW` — PBC left (cols D/E) and right (cols J/K) wiring rows

All fill functions use `_w(ws, row, col, value)` which writes to a cell without touching its formatting (preserves template styles).

### Summary sheet
`export_records(records, path, summary_title="")` — when `summary_title` is provided and more than one record is exported, a **Summary** sheet is inserted as the first sheet listing all records with valve tag, type, pass/fail, technician, date, and first line of notes.

### Export validation
`_check_export_issues(records)` returns a list of warning strings for:
- Missing valve tag
- No pass/fail result
- No technician name
- Notes exceeding `NOTES_MAX_LINES` (will be truncated in template)

All field access uses `(field or "").strip()` guards to handle `None` safely. Called before the file dialog in `_export_checkout` and `_export_job`; user can proceed or cancel.

---

## Embedded Points Lists

BACnet point reference data is embedded directly in `checkout_tool_gui.py` — no external files required. Structure:

```python
_POINTS_LIST_DATA: dict[str, tuple[list[str], list[tuple]]] = {
    "ACM Points List":    (_POINTS_HEADERS,     [...]),
    "FHD500 Points List": (_POINTS_HEADERS,     [...]),
    "PBC Points List":    (_PBC_POINTS_HEADERS, _PBC_ROWS),
    "RPI Points List":    (_POINTS_HEADERS,     _RPI_ROWS),
}
```

- `_POINTS_HEADERS = ["Type", "ID", "Name", "Unit", "Function", "Access"]` — used by ACM, FHD500, RPI
- `_PBC_POINTS_HEADERS = ["Type", "ID", "Name", "Category", "Unit", "Access"]` — PBC has a "Category" grouping column ("Lab Zone", "LoSEA Valve", etc.) in place of "Function"

`_open_points_list(title)` looks up `(headers, rows)` from the dict and builds a read-only `QTableWidget` dialog directly — no file I/O, no openpyxl dependency for this feature.

To add or update a points list, edit the relevant constant in the `# ── Embedded BACnet points list data ──` section near the top of `checkout_tool_gui.py`.

---

## Settings (QSettings)

All settings use `QSettings("ATS Inc", APP_NAME)`:

| Key | Type | Purpose |
|-----|------|---------|
| `darkMode` | bool | Dark/light theme preference |
| `geometry` | QByteArray | Window size and position |

Settings are read at startup in `_restore_settings()` and written in `_toggle_dark_mode()` and `closeEvent()`.

---

## Design System

### Accent Color
`#487cff` — selection highlights, hover states, numbered badges.

### Font
`Segoe UI, Arial, sans-serif` at `11pt` base.

### Themes
Two themes toggled via **View > Dark Mode**, saved in `QSettings("ATS Inc", APP_NAME)`.
Both use the **Fusion** Qt style, then override the palette and apply a full QSS stylesheet.

### Named Widget IDs (`setObjectName`)
| Name | Purpose |
|------|---------|
| `Panel` | Section containers / cards |
| `ProjectTitle` | 14pt bold heading |
| `ProjectSubtitle` | 10pt muted subtitle |
| `SectionTitle` | 12pt section heading |
| `UpdateBanner` | Auto-update banner |
| `UpdateMsg` | Label inside update banner |
| `InstallBtn` | Green install button |
| `RestoreBtn` | Amber restore button on archived job panel |

---

## Auto-Updater

`updater.py` checks this repo's releases on startup:
```python
GITHUB_OWNER   = "JustinGlave"
GITHUB_REPO    = "Phoenix-Checkout-Tool"
ZIP_ASSET_NAME = "PhoenixCheckoutTool.zip"
EXE_NAME       = "PhoenixCheckoutTool.exe"
```

- `check_for_update()` — safe to call from a background thread; catches all exceptions and returns `None` on failure
- `download_and_apply()` — downloads to a temp file, verifies size against `Content-Length`, then launches a batch script that waits for the process to exit before overwriting the exe and restarting
- The `_UpdateChecker` QThread is joined with `wait(2000)` in `closeEvent` to prevent orphaned threads on quit

The zip must contain only the exe (not the full folder). `build.bat` produces this correctly.

---

## Build & Release Workflow

1. Edit code and test manually
2. Bump `version.py`
3. Update `README.md` and `DEVELOPER.md` if needed
4. Commit and push: `git add . && git commit -m "..." && git push`
5. Run `build.bat`
6. Test `dist\PhoenixCheckoutTool\PhoenixCheckoutTool.exe`
7. Create GitHub release and upload assets:
   ```
   gh release create v1.x.x --title "v1.x.x" --notes "Release notes here"
   gh release upload v1.x.x dist/PhoenixCheckoutToolSetup.exe dist/PhoenixCheckoutTool.zip dist/PhoenixCheckoutTool_FullInstall.zip
   ```

---

## Installer Notes

- `PrivilegesRequired=lowest` — no admin required
- Installs to `{localappdata}\ATS Inc\Phoenix Valve Checkout Tool\`
- User data lives in `{userappdata}\ATS Inc\Phoenix Valve Checkout Tool\`
- Uninstaller prompts before deleting user data
- Excel templates are bundled in the exe via PyInstaller `datas` list in `PhoenixCheckoutTool.spec`
