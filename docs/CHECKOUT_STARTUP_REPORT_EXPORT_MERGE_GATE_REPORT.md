# Phoenix Checkout — Startup Report Export — Merge Gate Report

**Date:** 2026-06-16
**Branch:** `claude/pedantic-euler-0e7317`
**Scope:** Final validation before merge of the Startup Report export MVP. No merge performed.

> **⚠️ Superseded for the current integration.** This report validated the feature against the **stale base `2e03df6` (v1.7.0)**. Before merge it was discovered that `main` had advanced 20 commits (commons-backed refactor + v1.7.1 hardening). The feature was re-integrated onto current `main` on branch `feature/startup-report-export-main-sync` and re-validated there. **See [`CHECKOUT_STARTUP_REPORT_EXPORT_MAIN_SYNC_REPORT.md`](CHECKOUT_STARTUP_REPORT_EXPORT_MAIN_SYNC_REPORT.md) for the authoritative current-main validation.** The findings below (mappings, H/I decision, embedding, cap, preservation) all carried forward unchanged; only line numbers and the base commit differ.

---

## 1. Implementation summary

Adds a job-level "Export Startup Report" feature that fills the embedded `PHOENIX STARTUP REPORT_SiteName_v2.0.xlsx` template from checkout data and saves a job-specific `.xlsx`.

Change set (verified by `git status`):

| File | Status |
|---|---|
| `startup_report_template.py` | new — template embedded as base64; `template_bytes()`/`template_stream()` |
| `startup_report_export.py` | new — Qt-free engine: `StartupReportMeta`, mapping helpers, `prefill_meta()`, `export_startup_report()`, `MAX_VALVES=40`, `TooManyValvesError` |
| `checkout_tool_gui.py` | modified — `StartupReportDialog`, File-menu + job-context "Export Startup Report…", handlers `_on_export_startup_report()` / `_export_startup_report()` |
| `tests/__init__.py`, `tests/test_startup_report_export.py` | new — 20 stdlib-`unittest` tests |

Writes only the `Startup Report` tab, plain values only, never column A, never the Cover tab. Build artifacts (`dist/`, `build/`, `*.spec`) produced during validation were removed; they are gitignored regardless.

---

## 2. H/I source-field decision (gated item)

**Question:** Startup Report `H`/`I` = "Valve Min/Max (CFM)". The implementation uses the Checkout header fields `valve_min_sp`/`valve_max_sp`. Are those the intended/best CFM source, or is `config['valve_min_cfm']`/`['valve_max_cfm']` more accurate?

**Decision: keep `valve_min_sp`/`valve_max_sp`. No code change. STOP condition NOT triggered.**

This was confirmed two ways — direct inspection and an independent adversarial reviewer instructed to refute it. The refutation failed. Evidence:

- The SP fields are validated integer CFM — their validator is literally `_cfm_validator = QIntValidator(0, 99999)` (`checkout_tool_gui.py:1576-1603`); the config CFM cells are plain `QLineEdit` with **no validator** (free text).
- SP is saved stripped; config `*_cfm` is saved with a bare `.text()` (unstripped) — SP is the cleaner store.
- In **every** seed record the two are the *same physical value* (e.g. `valve_min_sp="200"` ↔ `"valve_min_cfm":"200"`; `150/600`, `100/500`, `120/450`, `180/700`).
- The **existing** Checkout export already treats `valve_min_sp`/`valve_max_sp` as the headline "Valve Min"/"Valve Max" (`checkout_export.py:178-179`, `248-249`, `354-355`); config CFM lives in the detailed config sub-table.
- PBC Room records have neither (SP fields hidden, config/verify tab hidden) → `H`/`I` correctly blank for PBC.

**Conclusion:** the header SP fields are the best available CFM source (validated, canonical, equal-or-cleaner than config). Documented as an intentional mapping; no more-accurate source exists.

---

## 3. Excel review result

Verified **programmatically** (openpyxl 3.1.5) against the spec cell-map — an independent audit agent ran 42 checks on a freshly generated export; **all 42 passed, zero anomalies**. Highlights:

- **Cover tab unchanged** — `C6`–`C13`, `B16` are still the template's formulas referencing `'Startup Report'` (no literals written).
- **Metadata** `C3`–`C11`, `G4` populated correctly; mixed-product-line job derived `C10 = "CSCP & Celeris"`.
- **Valve rows** `B`–`K` correct; `E`: Fume Hood→`Fume Hood`, GEX→`General Exhaust`, PBC Room→`PBC`; `G`: PASS/FAIL; `H`=120 (int)/900; PBC row `H`/`I` blank.
- **Column A** keeps `=IF(B15="","",ROW()-14)` (never written).
- `F` (Location) and `J` (Face Velocity) blank for v1.
- **Preserved:** 3 data validations with correct lists (`CSCP,Celeris` / `Supply,General Exhaust,Fume Hood,PBC` / `PASS,FAIL`), conditional formatting on `G15:G54`, merge `G4:K11`, hidden `L`/`AE` outline group, print area `A1:K56`, repeat-header `$14:$14`.

A sample workbook is at **`%TEMP%\Phoenix_StartupReport_SAMPLE.xlsx`** for human inspection.

> **Honest caveat:** this was structural/content verification via openpyxl, **not** a human opening the file in Excel. Visual rendering (how it *looks* and prints) is governed by the template's preserved print setup and styles, but a final human eyeball in Excel is recommended pre-release (see §8). It is not a merge blocker.

---

## 4. Frozen-build smoke result

PyInstaller 6.20.0 under Python 3.12. (`build.bat` ends with an interactive `pause` and an Inno Setup step — Inno isn't installed and `pause` would hang — so its **exact PyInstaller `--onedir` invocation** was run verbatim instead. No build.bat edit.)

- **Build succeeds:** exit 0; `dist/PhoenixCheckoutTool/PhoenixCheckoutTool.exe` produced.
- **Modules bundled:** both `startup_report_export` and `startup_report_template` appear in the build dependency xref → compiled into the PYZ inside the exe.
- **openpyxl:** bundled (already used by the existing export). The only "missing module" warnings are openpyxl's optional/conditional deps (PIL, lxml, defusedxml, numpy) — pre-existing and benign; openpyxl runs without them.
- **Embedded template loads frozen + export works frozen:** a minimal `--onefile` harness (importing the engine + embedded template) was frozen and run; it reported `frozen=True` and produced a valid workbook. Reopened output confirmed: both sheets, metadata, correct mappings, column-A formula intact, Cover formula intact, 3 data validations, CF on G15:G54, hidden L group. **No external template file needed; no openpyxl issue.**

> **Not done headless:** launching the actual *windowed GUI* exe (needs a desktop session). Recommended as a quick operator smoke (see §8); the engine's frozen behavior — the only frozen-specific risk — is proven above.

---

## 5. Updater / template packaging confirmation

- **`updater.py` untouched — contract remains exe-only.** Confirmed by `git status` (only `checkout_tool_gui.py` modified; the rest are new files). No `build.bat`, `installer.iss`, or `version.py` change.
- **Template ships inside the exe** (embedded base64), so it reaches existing auto-updated installs via the exe-only updater — the reason Option C was chosen. No `--add-data`, no `_internal/` dependency, no reinstall required.
- **No new runtime dependency** (openpyxl already bundled), so this feature does not trigger the `PROJECT_REVIEW.md` §2.2 dependency-bump brick risk.

---

## 6. Test results

| Check | Result |
|---|---|
| `python -m unittest tests.test_startup_report_export` | **20/20 pass** |
| `python -m compileall .` (whole project) | OK |
| Headless GUI import (`QT_QPA_PLATFORM=offscreen`) | OK; handlers present; dialog round-trips |
| Independent workbook audit (42 checks) | **42/42 pass**, 0 anomalies |
| Existing-export regression (4 template families, single + batch) | **pass** — no regression; Summary sheet still correct |
| End-to-end sample + frozen-harness export | pass |

---

## 7. Merge readiness

All automated and structural validation passes. The H/I source decision is confirmed (no change needed). No code defect or required fix was found. The only outstanding items are two **operator-side visual smokes** (Excel eyeball, GUI launch on a desktop) that cannot be performed headless and are **release-prep, not merge blockers**.

---

## 8. Release recommendation

1. **Operator visual smokes before public release** (not before merge):
   - Open `%TEMP%\Phoenix_StartupReport_SAMPLE.xlsx` in Excel — confirm the Cover page auto-fills, dropdowns/coloring work, and print layout looks right.
   - Launch the packaged GUI on a desktop and run one "Export Startup Report…" end-to-end.
2. **Ship via a normal release.** The exe-only auto-update delivers both the new code and the embedded template to existing clients. (A `version.py` bump is part of the normal release process and is intentionally **not** done here.)
3. **Fast-follow (deferred, not blocking):** >40-valve row-extension; optional numeric Face Velocity field; Location/Room field.

---

## 9. Confirmation

- ✅ **No updater contract change** (`updater.py` untouched; remains exe-only).
- ✅ **No `build.bat` / `installer.iss` change.**
- ✅ **No `version.py` change.**
- ✅ **No release, tag, asset upload, or publish.**
- ✅ Change set limited to: `startup_report_export.py` (new), `startup_report_template.py` (new), `tests/` (new), additive edits to `checkout_tool_gui.py`. Build artifacts cleaned (gitignored).

---

## Verdict

# A. Merge-ready

All validation passed; no fix required. The two remaining operator-side visual smokes (Excel + GUI launch) are recommended pre-release confirmations, not merge blockers. **Do not merge yet — awaiting operator go-ahead, per instructions.**
