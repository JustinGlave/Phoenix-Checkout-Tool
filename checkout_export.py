"""
checkout_export.py — Export ValveCheckout records to Excel.

Loads checkout_template.xlsx (bundled with the app), fills in data from one
or more ValveCheckout records (one sheet per record), and saves to a new file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from checkout_tool_backend import ValveCheckout


# ── Template location ──────────────────────────────────────────────────────────

TEMPLATE_NAME = "checkout_template.xlsx"

CHECK = "\u2714"   # ✔  (same character used in the template's factory rows)


def _resource_path(filename: str) -> str:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", ""))
    else:
        base = Path(__file__).parent
    return str(base / filename)


# ── Wiring row maps ────────────────────────────────────────────────────────────
# Maps the wiring-list index (same index stored in record.wiring keys)
# to the Excel row number where that terminal row lives in the template.

# Phoenix Air Valve (columns A–F; Install=col D=4, Wired=col E=5)
_PHOENIX_ROW: dict[int, int] = {
    # TB1 — INPUTS  (rows 11-18)
    0: 11, 1: 12, 2: 13, 3: 14, 4: 15, 5: 16, 6: 17, 7: 18,
    # TB2 — OUTPUTS  (rows 20-26)
    8: 20, 9: 21, 10: 22, 11: 23, 12: 24, 13: 25, 14: 26,
    # TB3 — INTERNAL factory rows (28-32) → no checkboxes written
    # TB4 — POWER  (rows 34-36)
    20: 34, 21: 35, 22: 36,
    # TB6 — COMM  (rows 38-39)
    23: 38, 24: 39,
    # TB7 — ACTUATOR factory rows (41-42) → no checkboxes written
}

# Black Box (columns G–L; Install=col J=10, Wired=col K=11)
_BB_ROW: dict[int, int] = {
    # TB1 — POWER IN  (rows 11-13)
    0: 11, 1: 12, 2: 13,
    # TB2 — OUTPUTS  (rows 15-16)
    3: 15, 4: 16,
    # TB3 — INPUTS  (rows 18-19)
    5: 18, 6: 19,
    # FHM Sentry — Fume Hood Monitor  (rows 21-24)
    7: 21, 8: 22, 9: 23, 10: 24,
}

# Configuration (key → row; CFM=col I=9, Notes=col J=10)
_CONFIG_ROW: dict[str, int] = {
    "valve_min":     30,
    "valve_max":     31,
    "sched_min":     32,
    "sched_max":     33,
    "hood_sash_min": 34,
    "hood_sash_max": 35,
}

# Verification (key → row; Result=col I=9, Notes=col J=10)
_VERIFY_ROW: dict[str, int] = {
    "face_velocity":      37,
    "sash_height_alarm":  38,
    "sash_sensor_output": 39,
    "low_flow_alarm":     40,
    "jam_alarm":          41,
    "emergency_exhaust":  42,
    "mute_function":      43,
}

# Notes rows (rows 45-49, 5 lines; each row is A:L merged)
_NOTE_ROWS = [45, 46, 47, 48, 49]


# ── Sheet filler ──────────────────────────────────────────────────────────────

def _w(ws: Worksheet, row: int, col: int, value) -> None:
    """Write value to cell without disturbing its existing formatting."""
    ws.cell(row=row, column=col).value = value


def fill_sheet(ws: Worksheet, record: ValveCheckout) -> None:
    """Populate worksheet ws with data from record (template already loaded)."""

    # ── Header fields ──────────────────────────────────────────────────────────
    _w(ws, 2,  3, record.project)
    _w(ws, 2,  9, record.ats_job_number)
    _w(ws, 3,  3, record.valve_tag)
    _w(ws, 3,  9, record.date)
    _w(ws, 4,  3, record.technician)
    _w(ws, 4,  9, record.description)
    _w(ws, 5,  3, record.model or "CELERIS 2")
    # Row 7: value cells for Pass/Fail, Emer. Min, Valve Min SP, Valve Max SP
    _w(ws, 7,  1, record.pass_fail)
    _w(ws, 7,  3, record.emer_min)
    _w(ws, 7,  5, record.valve_min_sp)
    _w(ws, 7,  8, record.valve_max_sp)

    # ── Wiring checkboxes ──────────────────────────────────────────────────────
    w = record.wiring
    for idx, row in _PHOENIX_ROW.items():
        _w(ws, row, 4, CHECK if w.get(f"p_{idx}_i") else "")
        _w(ws, row, 5, CHECK if w.get(f"p_{idx}_w") else "")
    for idx, row in _BB_ROW.items():
        _w(ws, row, 10, CHECK if w.get(f"b_{idx}_i") else "")
        _w(ws, row, 11, CHECK if w.get(f"b_{idx}_w") else "")

    # ── Sash sensor mounting ───────────────────────────────────────────────────
    # Template has a "SASH SENSOR MOUNTING" header at G27:L27.
    # The blank merged area G25:L26 directly above it is the data cell.
    _w(ws, 25, 7, (CHECK + "  Mounting Complete") if record.sash_sensor_mounted else "")

    # ── Configuration ──────────────────────────────────────────────────────────
    cfg = record.config
    for key, row in _CONFIG_ROW.items():
        _w(ws, row, 9,  cfg.get(f"{key}_cfm",   ""))
        _w(ws, row, 10, cfg.get(f"{key}_notes",  ""))

    # ── Verification ───────────────────────────────────────────────────────────
    vfy = record.verification
    for key, row in _VERIFY_ROW.items():
        _w(ws, row, 9,  vfy.get(f"{key}_result", ""))
        _w(ws, row, 10, vfy.get(f"{key}_notes",  ""))

    # ── Notes ──────────────────────────────────────────────────────────────────
    lines = (record.notes or "").split("\n")
    for i, note_row in enumerate(_NOTE_ROWS):
        _w(ws, note_row, 1, lines[i] if i < len(lines) else "")

    # Sheet tab name = valve tag (Excel tab names max 31 chars)
    safe_title = (record.valve_tag or "Checkout")[:31]
    # Strip characters Excel forbids in sheet names
    for ch in r"\/?*[]":
        safe_title = safe_title.replace(ch, "_")
    ws.title = safe_title or "Checkout"


# ── Public export entry point ─────────────────────────────────────────────────

def export_records(records: list[ValveCheckout], output_path: str) -> None:
    """
    Export one or more records to output_path (.xlsx).
    Produces one worksheet per record, each formatted like the template.
    """
    if not records:
        raise ValueError("No records provided for export.")

    template_path = _resource_path(TEMPLATE_NAME)
    wb = load_workbook(template_path)
    template_ws = wb.active

    # The first record fills the template sheet directly.
    # Additional records get a copy of the unfilled template sheet.
    sheets = [template_ws]
    for _ in records[1:]:
        sheets.append(wb.copy_worksheet(template_ws))

    for ws, record in zip(sheets, records):
        fill_sheet(ws, record)

    wb.save(output_path)
