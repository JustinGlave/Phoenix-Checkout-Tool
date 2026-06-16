# Changelog

All notable changes to **Phoenix Valve Checkout Tool** are documented
in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.8.0] — 2026-06-16

Startup Report export, a single combined report, and a Job → Room → Valve
restructure.

### Added
- **Startup Report export** — generate the Phoenix Startup Report workbook from a
  job's checkouts (Cover + Startup Report tabs). The template is embedded in source
  so it ships through the exe-only auto-updater. Pass/Fail, product line, and valve
  type are mapped per the integration spec; the Notes column wraps and its rows
  auto-fit; a factual Executive Summary (totals + failed valves) is generated and
  editable before export.
- **Export Startup & Checkout Report** — one combined workbook: Cover + Startup
  Report + one sheet per checkout, named
  `{Project Number}_{Project Name}_Startup and Checkout Report.xlsx`. The separate
  Startup Report and per-checkout exports remain.
- **Rooms** — checkouts are organized Job → Room → Valve. Right-click a job to add
  rooms; right-click a room to add / batch-add valves, rename, or delete it. A room
  view lists the room's valves in a table sortable by tag / type / pass-fail / model.
- **Job detail view** — Project Number, Project Name, Project Manager, Building
  Address, Site Name, and Floor are now job-level metadata (the sole source) and
  flow into the Startup Report.

### Changed
- Existing checkout data is auto-migrated to the Room model on first launch (a
  one-time `data.json.pre-rooms.bak` backup is written); valves without a room are
  placed in an "Unassigned" room seeded from their prior location.
- The Startup Report export dialog no longer re-asks for project identity (Project,
  Site Name, Building, Floor, Job Number) — those are sourced from the job; column F
  shows the valve's room name. The per-valve "Location / Room" editor field was
  retired.

### Known
- The GitHub-releases auto-update remains **unsigned** (Ed25519 signing is tracked
  as a follow-up). Project Manager is captured at the job level but not yet rendered
  on the report (Cover-cell follow-up).

## [1.7.1] — 2026-05-30

Release hardening + openpyxl dependency declaration — no functional changes.

### Changed
- **Build pipeline aligned with FROZEN_BUILD_BASELINE** (release
  hardening, 2026-05-29 → merged 2026-05-30). `build.bat` now
  enforces Python 3.12 soft-warn + Step 0 full cleanup
  (`rmdir /s /q dist build`) + `--noupx` + 8× stdlib
  `--exclude-module` (tkinter/tcl/tk/lib2to3/idlelib/turtle/
  turtledemo) at PyInstaller invocation. S1-safe profile per
  ADR-014 / FROZEN_BUILD_BASELINE.md. AppId behavior, install
  path, user-data path, and updater zip naming all preserved.
- **`openpyxl` runtime dependency declared** in `requirements.txt`
  (was previously imported but not pinned). PyInstaller hidden
  import + `--collect-submodules=openpyxl` added so xlsx
  templates load correctly inside the frozen exe. Root-cause of
  prior post-retrofit `ModuleNotFoundError` at startup.

### Added (carried from Phase 3B unreleased work)
- **Phase 3B retrofit (2026-05-19)**: migrated to commons-backed
  pattern per ADR-015 (`phoenix-commons` git submodule + editable
  install). Theme + widgets + `_app_data_path` + updater
  `check_for_update` now facade through `phoenix_commons` rather
  than local duplicates. The split `download_update` / `apply_update`
  API stays local to preserve v1.7.0's threaded-install behaviour
  (per ADR-003 exe-only payload contract). Light theme stays local
  per ADR-011 (commons is dark-only). Visible behaviour preserved
  (< 1% UI change). Local backup of pre-retrofit `phoenix_style.qss`
  kept under `legacy/`. Merged via `--no-ff` to `main` as commit
  `26a4689`. Detailed report in
  `phoenix-commons/docs/ui-platform-baseline-v1/PHASE_3B_POST_REVIEW_AND_MERGE_REPORT.md`.

### Added
- CHANGELOG.md (this file) — Operational Hardening Sprint
  2026-05-19.
- `.github/workflows/ci.yml` — GitHub Actions CI workflow (Python
  3.12 per ADR-014, submodule init, compileall, import smoke).
  Operational Hardening Sprint 2026-05-19.

## [1.7.0] — 2026-05-04

Bug-fix release with auto-updater improvements.

### Fixed
- Wiring label typo: "23 VDC OUT" → "24 VDC OUT".
- Batch export was losing Pass/Fail dropdown — now copies data
  validations and print settings.
- Notes template combo: reset to index 0 so the same snippet can
  be re-inserted.

### Changed
- Threaded update install — auto-updater now downloads in a
  background thread and applies on the main thread (split
  `download_update` + `apply_update` API).

### Added
- None-safety improvements throughout the data layer.
- Notes counter for the free-form notes field.
