# Phoenix Checkout — Startup Report Export — Merge Report

**Date:** 2026-06-16
**Result:** Startup Report Export MVP **merged and pushed to `main`.** Release/version work remains separate.

---

## 1. Merge commit

- **`bd38526`** — *"Merge Startup Report export MVP"* (`--no-ff` merge commit on `main`).
- Pushed to origin: `a4fe4b2..bd38526  main -> main`. `origin/main` is now `bd38526`.
- History: `bd38526` (merge) → `12402b1` (feature) → `a4fe4b2` (prior `main` tip, v1.7.1).

## 2. Feature branch

- **`feature/startup-report-export-main-sync`** — single commit `12402b1`, cut from current `main` (`a4fe4b2`, v1.7.1, commons-backed) during the main-sync re-integration. Pushed to origin (`* [new branch]`).

## 3. Files merged

8 files, **+1232 insertions, additive only**:

| File | |
|---|---|
| `checkout_tool_gui.py` | +142 (additive wiring: dialog, menu items, handlers) |
| `startup_report_export.py` | new — Qt-free export engine |
| `startup_report_template.py` | new — embedded base64 template |
| `tests/__init__.py`, `tests/test_startup_report_export.py` | new — 20 unit tests |
| `docs/CHECKOUT_STARTUP_REPORT_EXPORT_MVP_REPORT.md` | new |
| `docs/CHECKOUT_STARTUP_REPORT_EXPORT_MERGE_GATE_REPORT.md` | new (banner: superseded by main-sync) |
| `docs/CHECKOUT_STARTUP_REPORT_EXPORT_MAIN_SYNC_REPORT.md` | new |

No `commons/`, `version.py`, `updater.py`, `build.bat`, `installer.iss`, `checkout_export.py`, or `checkout_tool_backend.py` changes. No build/dist artifacts tracked.

## 4. Validation results (post-merge, on `main`)

| Check | Result |
|---|---|
| Diff scope `a4fe4b2..bd38526` | only the 8 feature files |
| Constraint files changed by merge | **none** (`version`/`updater`/`build`/`installer`/`checkout_export`/`backend` unchanged) |
| `py_compile` (changed/new) | OK |
| `python -m unittest tests.test_startup_report_export` | **20/20 pass** |
| GUI import smoke (commons-backed, offscreen) | OK — `_export_startup_report` handler present |
| Updater contract | exe-only intact (`build.bat` zips only the exe; `updater.py` copies only `EXE_NAME`) |
| Merge conflicts | none |

> Note: `tests/test_regressions.py` does not exist in this repo; per instruction this is not a failure. The available suite (`tests/test_startup_report_export.py`) was run. Existing-export regression was verified during re-integration (single + batch-with-Summary still produced correctly).

## 5. Startup Report export summary

A job-level **"Export Startup Report…"** entry (File menu + job context menu) opens a small metadata dialog (pre-filled from the selected checkout: Project, Technician, Date, ATS Job #, Description; collected: Site, Building, Floor, Executive Summary; derived: Product Line(s)). It loads the embedded template, writes **only** the `Startup Report` tab (plain values; metadata `C3`–`C11`, `G4`; valve rows `B`–`K` from row 15), never the Cover tab or column A, and saves a job-specific `.xlsx`. Template styling, dropdowns, conditional formatting, and print setup are preserved by openpyxl round-trip.

## 6. H/I source-field decision

`H`/`I` (Valve Min/Max CFM) → Checkout **`valve_min_sp` / `valve_max_sp`**. Confirmed best available source (direct + adversarial review): these are validated integer CFM (validator named `_cfm_validator`), equal to the config `*_cfm` values in practice, and are what the existing export already treats as the headline Valve Min/Max; the config `*_cfm` cells are unvalidated free-text duplicates. No more-accurate source exists; no STOP triggered.

## 7. Template embedding confirmation

The template is embedded as base64 in `startup_report_template.py` and loaded via `BytesIO` — no external data file. A frozen `--onefile` PyInstaller harness confirmed it loads with `sys.frozen=True` and produces a valid workbook. No `--add-data` entry and **no `build.bat` change** were needed.

## 8. Updater compatibility confirmation

The exe-only auto-update contract is **unchanged**. Because the template rides inside the exe (embedding) and no new runtime dependency was added (openpyxl already declared/bundled on v1.7.1), the feature reaches auto-updated clients via the existing exe-only update with no reinstall and without the `PROJECT_REVIEW.md` §2.2 dependency-bump risk.

## 9. Remaining intentional limitations (v1)

- >40 valves: blocked with a warning (no row-extension).
- Location/Room (`F`) and Face Velocity FPM (`J`): blank (no structured source; Face Velocity not inferred from the Pass/Fail/N/A verification result).
- Metadata is single-record-prefill + manual edit in the dialog (not auto-merged across records).
- Date written as the record's ISO string (renders fine).

## 10. Recommended release follow-up (separate from this merge)

- Operator visual smokes: open a generated workbook in Excel (Cover auto-fill, dropdowns/coloring, print layout); launch the packaged GUI on a desktop and run one export.
- At release time (separate task): bump `version.py`, build, and publish per the normal v1.7.x release process.
- Deferred fast-follows: >40-valve row-extension; optional numeric Face Velocity field; Location/Room field.

## 11. Confirmation

- ✅ **No `version.py` change** (stays v1.7.1).
- ✅ **No `updater.py` change** (exe-only contract intact).
- ✅ **No `build.bat` / `installer.iss` change.**
- ✅ **No release, tag, or asset publish.** (Branch + main pushes only.)
- ✅ Current-main hardening/commons refactor preserved; existing export behavior unchanged; no row-extension added.

---

**Startup Report Export MVP merged and pushed to `main` (`bd38526`). Release/version work remains separate.**
