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
| `emer_min`, `valve_min_sp`, `valve_max_sp` | str | CFM setpoints (hidden for PBC Room) |
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

---

## Valve Type Behavior Matrix

| Valve Type | Wiring Stack Page | BB Panel | Sash Sensor | Wiring Tab | Config/Verify Tab | SP Fields |
|------------|:-----------------:|:--------:|:-----------:|:----------:|:-----------------:|:---------:|
| Fume Hood | 0 — Celeris | Visible | Visible | Yes | Yes | Yes |
| GEX / MAV / Snorkel / Canopy / Draw Down Bench / Gas Cabinet | 0 — Celeris | Hidden | Hidden | Yes | Yes | Yes |
| CSCP Fume Hood | 1 — CSCP | — | DHV panel | Yes | Yes | Yes |
| PBC Room | 2 — PBC | — | Hidden | Yes | Hidden | Hidden |

---

## Main UI Structure

```
QMainWindow
└── Central QWidget (QHBoxLayout)
    ├── Sidebar (fixed 270px)
    │   ├── + New Job / + New Checkout / + Batch Add buttons
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
        │   │   └── Tab 3: Notes
        │   ├── Page 2: Archived job summary panel (read-only checkout list)
        │   └── Page 3: Active job summary panel (live checkout list)
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
