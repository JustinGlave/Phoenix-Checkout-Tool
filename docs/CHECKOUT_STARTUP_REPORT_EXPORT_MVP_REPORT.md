# Phoenix Checkout — Startup Report Export MVP — Implementation Report

**Date:** 2026-06-16
**Scope:** Surgical implementation of the Startup Report export, per the approved decisions in `CHECKOUT_STARTUP_REPORT_FEATURE_AUDIT.md`.
**Status:** ✅ Implemented and validated (source-mode). All 20 tests pass; full project byte-compiles; GUI imports headless; end-to-end sample export verified.

> One clarification was resolved before coding: the approved valve-type mapping omitted Checkout's `GEX` type. Operator confirmed **`GEX → General Exhaust`**. The mapping now covers all 9 Checkout valve types.

---

## 1. Files changed

| File | Status | What |
|---|---|---|
| `startup_report_template.py` | **new** | Embedded Startup Report template (base64). `template_bytes()` / `template_stream()`. Generated artifact (~17 KB). |
| `startup_report_export.py` | **new** | Headless export engine: `StartupReportMeta`, mapping helpers, `prefill_meta()`, `export_startup_report()`, `TooManyValvesError`, `MAX_VALVES`. Qt-free, unit-testable. |
| `checkout_tool_gui.py` | **modified** | Import of the engine (top of file); new `StartupReportDialog` (before `MainWindow`); File-menu action **"Export Startup Report…"**; job context-menu item **"Export Startup Report…"**; handlers `_on_export_startup_report()` + `_export_startup_report(job_id)`. |
| `tests/__init__.py` | **new** | Package marker (no test dir existed previously). |
| `tests/test_startup_report_export.py` | **new** | 20 stdlib-`unittest` tests (Qt-free). |

**Explicitly unchanged:** `updater.py`, `build.bat`, `installer.iss`, `version.py`, `checkout_export.py` (the existing per-checkout export engine is untouched).

---

## 2. Template embedding approach (SR-1)

- The v2.0 template (`PHOENIX STARTUP REPORT_SiteName_v2.0.xlsx`, 12,014 bytes) is base64-encoded into `startup_report_template.py` as `_TEMPLATE_B64`.
- `template_bytes()` decodes it; `template_stream()` returns a `BytesIO` for `openpyxl.load_workbook(...)` — **no temp file, no `_MEIPASS`/`_resource_path` dependency.**
- The generator verified the embedded bytes decode **byte-for-byte identical** to the source and that openpyxl loads both sheets.
- **Why embed (not bundle as data):** the auto-updater is exe-only (`updater.py:183` copies just the exe; `_internal/` is not refreshed). A normal `--add-data` template would be missing on auto-updated installs. Embedding the bytes in source means the template travels *inside the exe*. Same rationale as the embedded-QSS fallback (commit `e7c14d9`). **No `build.bat` change is required** — PyInstaller bundles the new modules automatically because the GUI imports them.

---

## 3. Metadata dialog behavior (SR-3)

`StartupReportDialog` (modal, opened at export time):

- **Pre-filled from the representative checkout record** (editable): Project, Technician, Date of Checkout, ATS Job Number, Description.
- **Pre-filled derived** (editable): Product Line(s) — `CSCP` / `Celeris` / `CSCP & Celeris`, computed from the job's valve types.
- **Collected** (blank by default): Site Name, Building, Floor, Executive Summary (multi-line).
- "Representative record" = the currently selected checkout if it belongs to the job, otherwise the job's first record.
- Any field may be left blank (blank → cell left untouched in the template). Accept button labeled **"Export…"**; Cancel aborts with no file written.

---

## 4. Cell mapping implemented (SR-2)

Writes **only** the `Startup Report` tab, **plain values only**, **never column A**, **never the Cover tab**.

**Metadata block** (`StartupReportMeta` field → cell):

| Field | Cell | Field | Cell |
|---|---|---|---|
| project | `C3` | ats_job_number | `C8` |
| site_name | `C4` | date_of_checkout | `C9` |
| building | `C5` | product_lines | `C10` |
| floor | `C6` | description | `C11` |
| technician | `C7` | executive_summary | `G4` |

**Valve rows** (one record per row, from row 15; max 40):

| Col | Source | Notes |
|---|---|---|
| `A` | — | **not written** (template auto-numbers via `=IF(B{r}="","",ROW()-14)`) |
| `B` | `valve_tag` | |
| `C` | derived product line | `CSCP`/`Celeris` from `valve_type` |
| `D` | `model` | |
| `E` | mapped valve type | §5 |
| `F` | — | **blank for v1** (Location/Room — no source) |
| `G` | `pass_fail` → upper | `Pass→PASS`, `Fail→FAIL`, unset→blank |
| `H` | `valve_min_sp` | numeric when parseable, else text; blank if empty |
| `I` | `valve_max_sp` | same |
| `J` | — | **blank for v1** (Face Velocity FPM — not inferred from the Pass/Fail/N/A verification result) |
| `K` | `notes` | |

Blank/unset values are skipped (the template cell stays empty), so the auto-number column and conditional formatting behave correctly for unused fields.

---

## 5. Valve type mapping (SR / approved + GEX confirmation)

Checkout `valve_type` → Startup Report column `E` (allowed dropdown values `Supply / General Exhaust / Fume Hood / PBC`):

| Checkout type | → `E` |
|---|---|
| Fume Hood | Fume Hood |
| CSCP Fume Hood | Fume Hood |
| PBC Room | PBC |
| MAV | Supply |
| GEX | General Exhaust *(operator-confirmed)* |
| Snorkel | General Exhaust |
| Canopy | General Exhaust |
| Draw Down Bench | General Exhaust |
| Gas Cabinet | General Exhaust |

Any unrecognized type → blank `E` (never writes an off-dropdown value). Product line: `CSCP Fume Hood`/`PBC Room` → `CSCP`; all others → `Celeris`.

---

## 6. 40-valve cap behavior (SR-5 decision)

- `MAX_VALVES = 40` (the template's preformatted rows 15–54).
- The GUI checks the count **before** opening the dialog. If a job has > 40 records, it shows a warning and **does not export**:
  > *"This job has N valves. The Startup Report template supports 40 valves in v1. Split the report or wait for row-extension support."*
- The engine also enforces the cap defensively: `export_startup_report` raises `TooManyValvesError` for > 40. No row-extension logic was added (deferred to fast-follow, per decision #5).

---

## 7. Tests / validation (SR-5 + VALIDATION)

**Automated — `tests/test_startup_report_export.py` (20 tests, all passing):**
- template opens from embedded bytes; both sheets present
- metadata cells `C3`–`C11`, `G4` populated; missing optional fields left blank
- valve rows `B`–`K` populated; **column A never written** (formula intact)
- 0 / 1 / 40 valves handled; **41 raises `TooManyValvesError`**
- PASS/FAIL mapping; unset → blank; blank min/max → blank
- Face Velocity (`J`) never inferred even when verification data exists
- all 9 valve-type mappings + "values always in dropdown" + product-line + mixed `derive_product_lines`
- **Cover tab unchanged** (formulas identical to pristine template, still formulas)
- **template features preserved**: 3 data validations (`C/E/G`), CF on `G15:G54`, merge `G4:K11`, hidden `L`/`AE` outline group, print area `A1:K56`, repeat-header `$14:$14`
- real `ValveCheckout` compatibility (engine attribute names match the dataclass)

**Manual / smoke:**
- `python -m compileall .` → OK (whole project)
- Headless GUI import (`QT_QPA_PLATFORM=offscreen`) → imports clean; both handlers present; `StartupReportDialog` constructs and round-trips metadata
- End-to-end sample export (3 mixed records): `C10="CSCP & Celeris"`; rows mapped correctly (`Fume Hood→Fume Hood/PASS`, `GEX→General Exhaust/PASS`, `PBC Room→PBC/FAIL` with blank H/I); `A15` formula intact; Cover `C6` still a formula; 3 DV + CF + hidden group preserved. **Sample written to `%TEMP%\Phoenix_StartupReport_SAMPLE.xlsx`** for manual inspection in Excel.

> Note: the spec referenced `tests/test_regressions.py`; no such file exists in the repo, so it was not run. The new focused suite is the test coverage for this feature.

**To run the tests:**
```
.venv\Scripts\python.exe -m unittest tests.test_startup_report_export -v
```

---

## 8. Packaging / updater compatibility confirmation

- The template is **embedded in source**, so it ships **inside the exe**. The exe-only auto-updater (`updater.py`) delivers the new exe — which contains the new code *and* the embedded template — to existing auto-updated installs. **No reinstall required.**
- **No new runtime dependency:** the engine uses only stdlib + `openpyxl` (already bundled). This feature does **not** trigger the `PROJECT_REVIEW.md` §2.2 "dependency-bump bricks the install" failure mode.
- **No `build.bat` change needed:** PyInstaller's dependency analysis picks up `startup_report_export.py` and `startup_report_template.py` automatically (imported by the GUI entry point). No `--add-data` entry, no `--hidden-import`.
- The updater contract, build script, and installer are **untouched.**

---

## 9. Remaining limitations (v1)

1. **40-valve cap** — jobs with > 40 valves are blocked with a warning; row-extension deferred.
2. **Location/Room (`F`) and Face Velocity (`J`) always blank** — no structured source in Checkout.
3. **Min/Max CFM source = header `valve_min_sp`/`valve_max_sp`** (the validated numeric header fields), *not* the config-table `*_cfm` values. This was the audit's recommended default; flagged here as an implemented assumption in case the operator prefers the config readings. (PBC Room records have no setpoints → H/I blank.)
4. **Metadata is single-record-prefill + manual edit**, not auto-merged across records. If technician/project/date differ across a job's checkouts, the dialog shows the representative record's values for the operator to adjust; differing values are not concatenated.
5. **Date is written as the record's ISO string** (e.g. `2026-06-16`), not a native Excel date — renders fine per the spec.
6. **openpyxl preserves features but does not recalculate formulas** — the Cover page and column-A numbers populate when the file is opened in Excel (expected; verified the formulas survive the round-trip).

---

## 10. Next-step recommendation

1. **Manual Excel check:** open `%TEMP%\Phoenix_StartupReport_SAMPLE.xlsx` and confirm the Cover page fills in, dropdowns/coloring work, and printing looks right.
2. **Frozen-build smoke:** build a test exe and export once from the frozen app to confirm the embedded template loads in `sys.frozen` mode (it should — it's pure in-memory bytes, no resource-path lookup).
3. **Ship normally:** a standard release delivers the feature to auto-updated clients (code + embedded template both ride in the exe).
4. **Fast-follow candidates:** >40-valve row-extension; optional numeric Face Velocity field in Checkout; a Location/Room field; and (if desired) switching H/I to the config CFM source.

**Recommendation: ready to ship as v1** after the manual Excel check + frozen-build smoke. No blockers.

---

## 11. Confirmation

- ✅ **No `updater.py` change; updater contract untouched.**
- ✅ **No `build.bat` change** (embedding made it unnecessary).
- ✅ **No `installer.iss` change.**
- ✅ **No `version.py` change.**
- ✅ **No release, tag, asset upload, or publish.**
- ✅ Existing export system (`checkout_export.py`) not rewritten; Cover tab never written; workbook styling not rebuilt; no >40-row support added.
- ✅ Change set limited to: `startup_report_export.py` (new), `startup_report_template.py` (new), `tests/` (new), and additive edits to `checkout_tool_gui.py`.
