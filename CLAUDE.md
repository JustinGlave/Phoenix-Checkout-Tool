# CLAUDE.md — Phoenix Valve Checkout Tool

> AI-context primer. Companion to `DEVELOPER.md` (deeper human-onboarding).
> Canonical platform doctrine lives in the `phoenix-commons` submodule
> under `commons/docs/ui-platform-baseline-v1/`.

## Purpose

Windows desktop application for ATS field technicians to create,
track, and export valve checkout records across Phoenix Celeris
(Fume Hood, GEX, MAV, Snorkel, Canopy, Draw Down Bench, Gas Cabinet)
and CSCP (ACM Fume Hood, PBC Room controller) product lines.

## Operational entrypoints

```powershell
git submodule update --init --recursive
py -3.12 -m venv .venv                         # ADR-014 canonical
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe checkout_tool_gui.py
```

`pip install` resolves `-e ./commons` (phoenix-commons editable
install). Submodule init is mandatory on a fresh clone.

## Retrofit state

**Commons-backed** since Phase 3B (merged 2026-05-19, commit `26a4689`
on `main`). Architecture is **monolithic** — `checkout_tool_gui.py`
is ~3,468 lines, intentionally preserved. Retrofit used the inline-
import pattern per `MIGRATION_RULES.md § 11`; widget classes are
re-exports from `phoenix_commons.widgets`.

| Subsystem | Source |
|-----------|--------|
| `apply_dark_theme` | commons facade |
| `PrimaryButton` / `SecondaryButton` / `TertiaryButton` / `_PhoenixTable` | commons re-exports |
| `_app_data_path` | commons facade |
| `updater.check_for_update` | commons facade |
| `updater.download_update` + `apply_update` | **local** (split for v1.7.0 threaded install) |
| `apply_light_theme` | **local** (ADR-011: commons is dark-only) |

## CI

`.github/workflows/ci.yml` — windows-latest, Python 3.12, submodule
init recursive, compileall, import smoke. Added in the Operational
Hardening Sprint 2026-05-19.

## Do NOT change casually

| Item | Reason |
|------|--------|
| Updater zip payload contract | **Exe-only** per ADR-003 — zip contains `PhoenixCheckoutTool.exe` only, no `_internal/`. `apply_update` PowerShell extracts only the exe. |
| `GITHUB_OWNER` / `GITHUB_REPO` / `ZIP_ASSET_NAME` / `EXE_NAME` in `updater.py` | Auto-updater contract — changing strands existing users |
| Install path `{localappdata}\ATS Inc\Phoenix Valve Checkout Tool` | Inno Setup upgrade-detection identity |
| `legacy/phoenix_style.qss.preretrofit` | Pre-retrofit QSS backup per `MIGRATION_RULES.md § Local backup QSS strategy` — leave for ~30 days post-merge |
| Split `download_update` + `apply_update` API | v1.7.0 threaded-install behaviour depends on the split |
| Monolithic `checkout_tool_gui.py` structure | Intentional per Phase 3B scope discipline — do not extract classes "while we're here" |

## Canonical references

- `commons/docs/ui-platform-baseline-v1/MIGRATION_RULES.md`
- `commons/docs/ui-platform-baseline-v1/PHASE_3B_PHOENIX_CHECKOUT_REPORT.md`
- `commons/docs/ui-platform-baseline-v1/PHASE_3B_POST_REVIEW_AND_MERGE_REPORT.md`
- `commons/docs/ui-platform-baseline-v1/RETROFIT_PLAYBOOK.md`
- `DEVELOPER.md` (deeper walkthrough)
- `CHANGELOG.md`
