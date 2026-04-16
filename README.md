# Phoenix Valve Checkout Tool

A Windows desktop application for ATS Inc. field technicians to create, track, and export Phoenix Celeris valve checkout records.

---

## Features

- **Job management** — group checkout sheets by job number and project name
- **Checkout sheets** — track wiring (Phoenix Air Valve + Black Box), configuration setpoints, verification results, and notes for each valve
- **Batch creation** — generate multiple checkout sheets at once from a starting valve tag (e.g. MAV-1-100 through MAV-1-119)
- **Excel export** — export any checkout sheet or entire job to a formatted `.xlsx` file that matches the standard ATS checkout template exactly
- **Archive / restore** — close out completed jobs without deleting them; restore at any time
- **Auto-update** — the app checks GitHub Releases on startup and can install updates in one click
- **Dark / light mode** — toggled via View menu, preference saved between sessions

---

## Installation

Download the latest release from the [Releases page](https://github.com/JustinGlave/Phoenix-Checkout-Tool/releases):

- **`PhoenixCheckoutToolSetup.exe`** — recommended installer for new users (no admin required)
- **`PhoenixCheckoutTool_FullInstall.zip`** — manual install, extract and run the exe directly

---

## Usage

### Create a Job
Click **+ New Job** in the sidebar or press `Ctrl+J`. Enter a job number and job name. A job groups all checkout sheets for one project.

### Add a Checkout Sheet
Select a job, then click **+ New Checkout** or press `Ctrl+N`. Fill in the valve tag and other fields. The sheet saves automatically as you type.

### Batch Add Checkout Sheets
Click **+ Batch Add** or press `Ctrl+B`. Enter a starting tag (e.g. `MAV-1-100`) and a count — the tool generates sheets `MAV-1-100` through `MAV-1-{N}` sharing the same technician, description, and date.

### Export to Excel
Right-click any checkout or job in the sidebar and choose **Export to Excel**, or use the **File** menu. Exports use the standard ATS checkout template with all formatting preserved.

### Archive a Job
Right-click a job and choose **Archive Job**. The job moves to the **Archived Jobs** section at the bottom of the sidebar. All checkout data is preserved. Right-click an archived job to **Restore** or **Delete** it permanently.

---

## Data Storage

All data is saved automatically to:
```
%APPDATA%\ATS Inc\Phoenix Valve Checkout Tool\data.json
```

The uninstaller will ask whether to delete this data before removing the app.

---

## Building from Source

**Requirements:**
- Python 3.11+
- `pip install PySide6 openpyxl pyinstaller`
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)

**Build:**
```
build.bat
```

This produces:
- `dist\PhoenixCheckoutTool\PhoenixCheckoutTool.exe` — test this first
- `dist\PhoenixCheckoutToolSetup.exe` — installer
- `dist\PhoenixCheckoutTool.zip` — auto-updater asset
- `dist\PhoenixCheckoutTool_FullInstall.zip` — manual install zip

See `DEVELOPER.md` for the full release workflow.

---

## License

MIT — see [LICENSE](LICENSE)
