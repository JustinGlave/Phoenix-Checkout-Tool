# Phoenix Valve Checkout Tool

A Windows desktop application for ATS Inc. field technicians to create, track, and export valve checkout records across all Phoenix Celeris and CSCP product lines.

---

## Features

- **Two product lines supported**
  - **Phoenix Celeris** — Fume Hood, GEX, MAV, Snorkel, Canopy, Draw Down Bench, Gas Cabinet
  - **CSCP (Critical Spaces Control Platform)** — ACM Fume Hood, PBC Room controller
- **Job management** — group checkout sheets by job number and project name; view a live summary of all checkouts when a job is selected, including a completion progress bar
- **Checkout sheets** — per-type wiring panels, configuration setpoints, verification results, and notes for each valve or controller
  - Celeris Fume Hood: Phoenix Air Valve wiring (TB1–TB7) + Black Box wiring + sash sensor
  - Celeris GEX / MAV / Snorkel / Canopy / Draw Down Bench / Gas Cabinet: Phoenix wiring only
  - CSCP ACM Fume Hood: ACM connector wiring (P10–P80) + DHV Black Box wiring + sash sensor
  - CSCP PBC Room: full PBC terminal wiring (TB1 Inputs / DO Relay / DO SSR / UIO + Power / Comm / UIO right panel)
- **Wiring Check All / Clear All** — quickly check or clear all non-factory wiring rows in any panel with a single debounced save
- **Search / filter** — live search box above the job tree; matches valve tag, technician name, description, and valve type
- **Batch creation** — generate multiple checkout sheets at once from a starting valve tag; zero-padding is preserved and extended automatically for large counts
- **Excel export** — exports to the correct formatted template for each valve type, preserving all cell formatting; one sheet per valve, multi-sheet for whole jobs (includes a Summary sheet)
- **Export validation** — warns before export if any record is missing required fields or has oversized notes
- **CFM / setpoint validation** — Emer. Min, Valve Min SP, and Valve Max SP fields accept numbers only
- **Notes templates** — quick-insert dropdown with common commissioning note snippets
- **Points Lists** — fully embedded BACnet point reference tables under **Tools → Points Lists** for ACM, FHD500, PBC, and RPI — no external files required
- **Archive / restore** — close out completed jobs without deleting them; restore at any time
- **Backup Data** — one-click backup of your data file via **File → Backup Data**
- **Auto-update** — checks GitHub Releases on startup and installs updates in one click
- **Dark / light mode** — toggled via View menu, preference saved between sessions
- **Window geometry** — size and position are saved and restored between sessions

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
Click **+ New Job** in the sidebar or press `Ctrl+J`. Enter a job number and job name. Selecting a job shows a summary of all its checkout sheets with pass/fail status and a completion progress bar.

### Add a Checkout Sheet
Select a job, then click **+ New Checkout** or press `Ctrl+N`. Choose the valve type from the dropdown — the wiring panel, config/verify rows, and export template update automatically.

### Batch Add Checkout Sheets
Click **+ Batch Add** or press `Ctrl+B`. Enter a starting tag (e.g. `MAV-1-100`) and a count — the tool generates sheets `MAV-1-100` through `MAV-1-{N}` sharing the same technician, description, and date. If the starting tag uses zero-padding (e.g. `FH-001`), padding is extended automatically to accommodate the full range.

### Search / Filter
Type in the search box above the job tree to instantly filter checkouts. The search matches valve tag, technician name, description, and valve type. Jobs with no matching children are hidden automatically.

### Wiring Panels
Use **Check All** / **Clear All** at the top of each wiring panel to quickly mark or clear all non-factory wiring rows.

### Notes Templates
On the **Notes** tab, use the dropdown to insert common commissioning snippets. The selected snippet is appended to any existing notes.

### Export to Excel
Right-click any checkout or job in the sidebar and choose **Export to Excel**, or use the **File** menu. The tool warns you if any records have missing fields before writing. Job exports include a **Summary** sheet listing all checkouts.

### Points Lists
Go to **Tools → Points Lists** and select ACM, FHD500, PBC, or RPI to view the BACnet points list in a popup table. No external files are required — all data is built into the application.

### Archive a Job
Right-click a job and choose **Archive Job**. The job moves to the **Archived Jobs** section. Right-click an archived job to **Restore** or **Delete** it permanently.

### Backup Data
Go to **File → Backup Data** to save a timestamped copy of your data file to any location.

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
