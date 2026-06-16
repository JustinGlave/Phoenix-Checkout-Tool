# Phoenix Checkout — Startup Report Export — Main-Sync / Re-Integration Report

**Date:** 2026-06-16
**Integration branch:** `feature/startup-report-export-main-sync`
**Based on:** current `main` = `a4fe4b2` (origin/main; v1.7.1, commons-backed)
**Status:** Re-integrated onto current main and re-validated. **No merge performed; awaiting operator approval.**

---

## 1. Why re-integration was needed

The Startup Report export MVP was built and validated on branch `claude/pedantic-euler-0e7317`, whose base was `2e03df6` (v1.7.0). At the merge gate it was discovered that `main` had advanced **20 commits** beyond that base — a major **"commons-backed" refactor (Phase 3B)** plus **v1.7.1 release hardening**:

- `checkout_tool_gui.py` rewritten **+36 / −174** (inline widgets → `phoenix_commons` re-exports, `_EMBEDDED_QSS` removed, theme retrofit).
- New `phoenix-commons` git submodule + editable install (`-e ./commons`), `requirements.txt` (declares `openpyxl==3.1.5`, `PySide6==6.11.0`).
- `updater.py` reworked to a facade; `build.bat` hardened; `version.py` → v1.7.1.

Merging the stale branch directly would have **conflicted** in `checkout_tool_gui.py` and re-introduced deleted code. Per operator direction, the feature was re-applied onto current `main` with **current main authoritative** — main wins for the refactor, hardening, updater/installer/build, and `version.py`; the feature contributes only its additive pieces.

## 2. Current main commit used

`a4fe4b2` — *"gitignore: ignore .venv/ … (post-release housekeeping)"*, tip of `origin/main`, on top of `274b0a8 v1.7.1 — release hardening + openpyxl dependency declared`. The integration branch `feature/startup-report-export-main-sync` was cut directly from it.

## 3. Files ported unchanged

These standalone artifacts were carried over **byte-for-byte** (verified compatible with current main — `ValveCheckout` fields are unchanged, and the engine is Qt-/commons-agnostic, duck-typing record attributes):

- `startup_report_template.py` (embedded base64 template)
- `startup_report_export.py` (export engine)
- `tests/test_startup_report_export.py` + `tests/__init__.py` (20 tests)

## 4. GUI wiring re-applied

`checkout_tool_gui.py` on current main retained the exact structure the feature hooks into (the refactor was internal), so the five additive edits re-applied cleanly against current anchors (**+142 lines, additive only**):

1. Import `from startup_report_export import (...)` after the `checkout_export` import.
2. `StartupReportDialog` inline class before `class MainWindow` (dialogs are still inline classes on main).
3. File-menu action **"Export Startup Report…"** after "Export All Checkouts in Job…".
4. Job context-menu item **"Export Startup Report…"** + dispatch (`_export_startup_report(id_)`).
5. Handlers `_on_export_startup_report()` / `_export_startup_report(job_id)` after `_on_export_job`.

`QPlainTextEdit`, `QDialog`, `QDialogButtonBox`, `QFormLayout`, `QFileDialog`, `_selected_job_id`, `_current_id`, `_export_job`, `_check_export_issues` all exist unchanged on main.

## 5. Conflicts resolved

**No textual merge conflicts** — the divergence was avoided rather than merged: the stale branch's `checkout_tool_gui.py` modification was **discarded** (`git restore`), the branch was re-cut from `a4fe4b2`, and the wiring was **re-applied** against current main's file. Compatibility points checked:

- `ValveCheckout` fields (`valve_tag`, `valve_type`, `pass_fail`, `valve_min_sp`, `valve_max_sp`, `notes`) unchanged → engine + tests pass.
- `phoenix_commons` resolves via the venv editable install → main's commons-backed GUI imports cleanly in the integration tree.
- The embedded-template approach (Option C) needs no submodule/data file, so the commons refactor does not affect it.

## 6. Validation results (on `a4fe4b2` + feature)

| Check | Result |
|---|---|
| Scope: files changed vs `a4fe4b2` | **only `checkout_tool_gui.py`** (+142, additive); untracked: 2 modules + `tests/` + `docs/` |
| `version.py`, `updater.py`, `build.bat`, `installer.iss`, `checkout_export.py`, `checkout_tool_backend.py` | **byte-identical to main** (verified `git diff --quiet` each) |
| `python -m py_compile` (changed/new) | OK |
| `python -m unittest tests.test_startup_report_export` | **20/20 pass** |
| GUI import + dialog + handlers (commons-backed, offscreen) | OK |
| Fresh sample export (mixed job) | OK — `C10="CSCP & Celeris"`; Fume Hood/General Exhaust/PBC; PASS/PASS/FAIL; H=120/200/blank(PBC); col-A formula intact; Cover formula intact; 3 DV; CF G15:G54 |
| Existing-export regression (`export_records`, single + batch) | OK — single `['A1']`; batch `['Summary','A1','B1']`, Summary present |
| Frozen `--onefile` harness (embedded template, `sys.frozen=True`) | OK — valid workbook, both sheets, 3 DV, Cover formula |

Approved decisions preserved unchanged: GEX→General Exhaust; H/I = `valve_min_sp`/`valve_max_sp`; Location/Room blank; Face Velocity blank; ≤40 valves (block + warn above 40); embedded template for exe-only updater compatibility.

## 7. Confirmation

- ✅ **Current main hardening preserved** — commons refactor, build hardening, `requirements.txt`/openpyxl declaration, updater facade, installer behavior all untouched (current main authoritative).
- ✅ **`updater.py` unchanged** — updater contract (exe-only) intact.
- ✅ **`version.py` unchanged** (stays at main's v1.7.1).
- ✅ **`build.bat` unchanged.**
- ✅ **`installer.iss` unchanged.**
- ✅ **No release, tag, asset upload, or publish.**
- ✅ Feature contribution limited to: `startup_report_export.py`, `startup_report_template.py`, `tests/`, additive `checkout_tool_gui.py` wiring, and feature docs.

---

## Verdict

**Re-integrated onto current `main` (`a4fe4b2`, v1.7.1, commons-backed) and fully re-validated — merge-ready.** No `version`/`updater`/`build`/`installer` changes; current-main hardening preserved. **Not merged — awaiting operator approval.**

Recommended operator visual smokes before public release (unchanged from the merge-gate report, not merge blockers): open a generated workbook in Excel; launch the packaged GUI on a desktop and run one export.
