# Changelog

All notable changes to **Phoenix Valve Checkout Tool** are documented
in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
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

## [1.7.0] — 2025

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
