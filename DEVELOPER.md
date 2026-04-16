# DEVELOPER.md — Phoenix Valve Checkout Tool

This project uses the same design system, build pipeline, and auto-updater as the
**Project Tracking Tool** (github.com/JustinGlave/project-tracking-tool).

---

## Tech Stack

- **Python 3** with **PySide6** (Qt for Python) for the UI
- **PyInstaller** (`--onedir --windowed`) to package as a Windows exe
- **Inno Setup 6** to build the installer (`installer.iss`)
- **GitHub Releases** for distribution and auto-updates (`updater.py`)

---

## File Structure

```
checkout_tool_gui.py      — Main UI
checkout_tool_backend.py  — Data and storage logic (ValveCheckout / CheckoutStore)
updater.py                — Auto-update system (GITHUB_REPO = Phoenix-Checkout-Tool)
version.py                — Version number (bump before every release)
build.bat                 — Builds exe + installer + zips
installer.iss             — Inno Setup installer script
PTT_Normal.ico            — App icon
PTT_Transparent.png       — Watermark/logo
```

---

## Data Model

### Job
- `id` — unique UUID
- `job_number` — ATS job number string
- `job_name` — project/job name string

### ValveCheckout
- `id` — unique UUID
- `job_id` — parent `Job.id`
- `valve_tag` — valve tag / identifier (shown in sidebar)
- `project`, `ats_job_number`, `technician`, `description`, `model`, `date`
- `pass_fail` — `"Pass"` | `"Fail"` | `""`
- `emer_min`, `valve_min_sp`, `valve_max_sp` — CFM setpoints
- `wiring` — dict of checkbox states (`p_{i}_{i|w}` for Phoenix, `b_{i}_{i|w}` for Black Box)
- `sash_sensor_mounted` — bool
- `config` — dict of `{key}_cfm` and `{key}_notes` for each CONFIG_ROWS entry
- `verification` — dict of `{key}_result` and `{key}_notes` for each VERIFY_ROWS entry
- `notes` — free-form notes string

Data is stored at `%APPDATA%\ATS Inc\Phoenix Valve Checkout Tool\data.json`.

---

## Design System

### Accent Color
`#487cff` — used for selection highlights, hover states, menu item hover, and the install button.

### Font
`Segoe UI, Arial, sans-serif` at `11pt` base. All widgets inherit this.

### Themes
Two themes toggled via **View → Dark Mode**. Preference saved in `QSettings`.

Both themes use the **Fusion** Qt style as a base, then override the palette
and apply a full QSS stylesheet.

#### Dark Theme palette (key values)
| Role | Value |
|------|-------|
| Window | `#1c1c1c` |
| Base (inputs/lists) | `#121212` |
| Button | `#2d2d2d` |
| Text | `#e6e6e6` |
| Highlight | `#487cff` |

#### Light Theme palette (key values)
| Role | Value |
|------|-------|
| Window | `rgb(210, 212, 218)` |
| Base (inputs/lists) | `rgb(225, 227, 232)` |
| Button | `rgb(195, 198, 206)` |
| Text | `rgb(25, 25, 25)` |
| Highlight | `#487cff` |

### Widget Styling Conventions
| Widget | Style |
|--------|-------|
| Panels / cards | `border-radius: 14px`, semi-transparent background, 1px border |
| Buttons | `border-radius: 10px`, `padding: 6px 16px` |
| Inputs | `border-radius: 10px`, `padding: 8px` |
| Tables / lists | `border-radius: 10px`, transparent background |
| List items | `border-radius: 10px`, `padding: 10px`, `margin: 2px 0` |

### Named Widget IDs (setObjectName)
| Name | Used for |
|------|----------|
| `Panel` | Section containers / cards |
| `StatCard` | Small stat display cards |
| `ProjectTitle` | 14pt bold heading |
| `ProjectSubtitle` | 10pt muted subtitle |
| `SectionTitle` | 12pt section heading |
| `StatTitle` | 7pt muted label above a stat value |
| `StatValue` | 10pt bold stat value |
| `MetaCaption` | 9pt bold field label |
| `MetaValue` | 9pt field value |
| `ResizeHandle` | Drag handle between panels |
| `UpdateBanner` | Auto-update banner at bottom of window |
| `UpdateMsg` | Label inside the update banner |
| `InstallBtn` | Green install button inside update banner |

---

## Layout Pattern

```
QMainWindow
└── Central QWidget (QHBoxLayout)
    ├── Left sidebar (QListWidget, fixed ~220px width)
    │   ├── "+ New Checkout" button at top
    │   └── Checkout record list
    └── Right main area (QWidget, stretch)
        ├── Header area (valve tag title, meta fields)
        ├── Content area (checkout details / table)
        └── Update banner (hidden until update available)
```

---

## Path Helpers

```python
def _resource_path(filename: str) -> str:
    """Path to a bundled asset. Works from source and exe."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", ""))
    else:
        base = Path(__file__).parent
    return str(base / filename)

def _app_data_path(filename: str) -> str:
    """Path to user data in %APPDATA%\\ATS Inc\\Phoenix Valve Checkout Tool\\."""
    base = Path(os.environ.get("APPDATA", Path.home())) / "ATS Inc" / "Phoenix Valve Checkout Tool"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / filename)
```

---

## Auto-Updater

`updater.py` is pre-configured for this repo:
```python
GITHUB_OWNER   = "JustinGlave"
GITHUB_REPO    = "Phoenix-Checkout-Tool"
ZIP_ASSET_NAME = "PhoenixCheckoutTool.zip"
EXE_NAME       = "PhoenixCheckoutTool.exe"
```

---

## Build & Release Workflow

1. Edit code
2. Bump version in `version.py`
3. Run `build.bat` — produces:
   - `dist\PhoenixCheckoutTool\PhoenixCheckoutTool.exe` — test this first
   - `dist\PhoenixCheckoutToolSetup.exe` — installer for new users
   - `dist\PhoenixCheckoutTool.zip` — auto-updater asset
4. Test the exe and installer
5. `git add . && git commit -m "v1.x.x - description" && git push`
6. `gh release create v1.x.x --title "v1.x.x" --notes "..."`
7. `gh release upload v1.x.x dist/PhoenixCheckoutToolSetup.exe dist/PhoenixCheckoutTool.zip`

---

## Installer Notes

- `PrivilegesRequired=lowest` — no admin required
- Installs to `{localappdata}\ATS Inc\Phoenix Valve Checkout Tool\`
- User data goes to `{userappdata}\ATS Inc\Phoenix Valve Checkout Tool\` (separate from app files)
- Uninstaller asks whether to delete user data before removing it
