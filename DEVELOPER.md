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
checkout_tool_gui.py      — Main UI (MainWindow, dialogs, themes)
checkout_tool_backend.py  — Data model and storage (Job / ValveCheckout / CheckoutStore)
checkout_export.py        — Excel export engine (template-based via openpyxl)
updater.py                — Auto-update system
version.py                — Version number (bump before every release)
build.bat                 — Builds exe + installer + zips
installer.iss             — Inno Setup installer script
checkout_template.xlsx    — Bundled Excel template
PTT_Normal_green.ico      — App icon (exe + installer)
PTT_Transparent_green.png — Watermark / background logo
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
| `valve_tag` | str | Valve identifier, shown in sidebar |
| `project`, `ats_job_number`, `technician`, `description`, `model`, `date` | str | Header fields |
| `pass_fail` | str | `"Pass"` or `"Fail"` or `""` |
| `emer_min`, `valve_min_sp`, `valve_max_sp` | str | CFM setpoints |
| `wiring` | dict | `p_{i}_{i/w}` = Phoenix rows, `b_{i}_{i/w}` = Black Box rows |
| `sash_sensor_mounted` | bool | Sash sensor mounting checkbox |
| `config` | dict | `{key}_cfm` and `{key}_notes` for each CONFIG_ROWS entry |
| `verification` | dict | `{key}_result` and `{key}_notes` for each VERIFY_ROWS entry |
| `notes` | str | Free-form notes |

Data is persisted at `%APPDATA%\ATS Inc\Phoenix Valve Checkout Tool\data.json`.

---

## Main UI Structure

```
QMainWindow
└── Central QWidget (QHBoxLayout)
    ├── Sidebar (fixed 270px)
    │   ├── + New Job / + New Checkout buttons
    │   ├── + Batch Add button
    │   └── QTreeWidget
    │       ├── Active jobs (bold) with checkout children
    │       └── Archived Jobs separator + archived job entries (gray italic)
    └── Main area (_BgWidget — floating logo watermark)
        ├── QStackedWidget
        │   ├── Page 0: Welcome / instructions panel (startup / nothing selected)
        │   ├── Page 1: Header panel + tab widget (checkout editor)
        │   └── Page 2: Archived job summary panel (read-only list of checkouts)
        └── Update banner (hidden until update available)
```

### Stack page switching
| Condition | Page |
|-----------|------|
| Nothing selected / tree empty | 0 - Welcome |
| Active job selected | 1 - Checkout editor (tabs disabled) |
| Checkout selected | 1 - Checkout editor (tabs enabled) |
| Archived job selected | 2 - Archived job summary |

---

## Design System

### Accent Color
`#487cff` — selection highlights, hover states, numbered badges.

### Font
`Segoe UI, Arial, sans-serif` at `11pt` base.

### Themes
Two themes toggled via **View > Dark Mode**, saved in `QSettings("ATS Inc", APP_NAME)`.
Both use the **Fusion** Qt style, then override the palette and apply a full QSS stylesheet.

### Named Widget IDs (setObjectName)
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
3. Commit and push: `git add . && git commit -m "..." && git push`
4. Run `build.bat`
5. Test `dist\PhoenixCheckoutTool\PhoenixCheckoutTool.exe`
6. Create GitHub release and upload assets:
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
