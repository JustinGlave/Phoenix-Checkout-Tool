# Phoenix Valve Checkout Tool

A Windows desktop application for ATS Inc. field technicians to create, track, and export valve checkout records across all Phoenix Celeris and CSCP product lines.

---

## Features

- **Two product lines supported**
  - **Phoenix Celeris** — Fume Hood, GEX, MAV, Snorkel, Canopy, Draw Down Bench, Gas Cabinet
  - **CSCP (Critical Spaces Control Platform)** — ACM Fume Hood, PBC Room controller
- **Job management** — group checkout sheets by job number and project name; view a live summary of all checkouts when a job is selected
- **Checkout sheets** — per-type wiring panels, configuration setpoints, verification results, and notes for each valve or controller
  - Celeris Fume Hood: Phoenix Air Valve wiring (TB1–TB7) + Black Box wiring + sash sensor
  - Celeris GEX / MAV / Snorkel / Canopy / Draw Down Bench / Gas Cabinet: Phoenix wiring only
  - CSCP ACM Fume Hood: ACM connector wiring (P10–P80) + DHV Black Box wiring + sash sensor
  - CSCP PBC Room: full PBC terminal wiring (TB1 Inputs / DO Relay / DO SSR / UIO + Power / Comm / UIO right panel)
- **Batch creation** — generate multiple checkout sheets at once from a starting valve tag
- **Excel export** — exports to the correct formatted template for each valve type, preserving all cell formatting; one sheet per valve, multi-sheet for whole jobs
- **Points Lists** — quick-access reference tables under **Tools → Points Lists** for ACM, FHD500, PBC, and RPI BACnet point lists
- **Archive / restore** — close out completed jobs without deleting them; restore at any time
- **Auto-update** — checks GitHub Releases on startup and installs updates in one click
- **Dark / light mode** — toggled via View menu, preference saved between sessions

---

## Supported Valve & Controller Types

| Type | Product Line | Template | Wiring | Config/Verify |
|------|-------------|----------|--------|---------------|
| Fume Hood | Celeris | `checkout_template.xlsx` | Phoenix TB1–TB7 + Black Box + Sash Sensor | Yes |
| GEX | Celeris | `template_gex.xlsx` | Phoenix TB1–TB7 | Yes |
| MAV | Celeris | `template_mav.xlsx` | Phoenix TB1–TB7 | Yes |
| Snorkel | Celeris | `checkout_template.xlsx` | Phoenix TB1–TB7 | Yes |
| Canopy | Celeris | `checkout_template.xlsx` | Phoenix TB1–TB7 | Yes |
| Draw Down Bench | Celeris | `checkout_template.xlsx` | Phoenix TB1–TB7 | Yes |
| Gas Cabinet | Celeris | `checkout_template.xlsx` | Phoenix TB1–TB7 | Yes |
| CSCP Fume Hood | CSCP | `template_cscp_fh.xlsx` | ACM P10–P80 + DHV Black Box + Sash Sensor | Yes |
| PBC Room | CSCP | `template_pbc_room.xlsx` | PBC TB1 Inputs / DO Relay / DO SSR / UIO (both panels) | No |

---

## Installation

Download the latest release from the [Releases page](https://github.com/JustinGlave/Phoenix-Checkout-Tool/releases):

- **`PhoenixCheckoutToolSetup.exe`** — recommended installer for new users (no admin required)
- **`PhoenixCheckoutTool_FullInstall.zip`** — manual install, extract and run the exe directly

---

## Usage

### Create a Job
Click **+ New Job** in the sidebar or press `Ctrl+J`. Enter a job number and job name. Selecting a job shows a summary of all its checkout sheets with pass/fail status.

### Add a Checkout Sheet
Select a job, then click **+ New Checkout** or press `Ctrl+N`. Choose the valve type from the dropdown — the wiring panel, config/verify rows, and export template update automatically.

### Batch Add Checkout Sheets
Click **+ Batch Add** or press `Ctrl+B`. Enter a starting tag (e.g. `MAV-1-100`) and a count — the tool generates sheets `MAV-1-100` through `MAV-1-{N}` sharing the same technician, description, and date.

### Export to Excel
Right-click any checkout or job in the sidebar and choose **Export to Excel**, or use the **File** menu. Each valve type exports to its own formatted template.

### Points Lists
Go to **Tools → Points Lists** and select ACM, FHD500, PBC, or RPI to view the BACnet points list in a popup table.

### Archive a Job
Right-click a job and choose **Archive Job**. The job moves to the **Archived Jobs** section. Right-click an archived job to **Restore** or **Delete** it permanently.

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
