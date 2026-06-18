# Phoenix Valve Checkout Tool — Handover

> For continuing this project in **Claude Cowork**. Self-contained: assumes only
> the repo + a working dev venv. All state below was **verified live on
> 2026-06-17** against git, GitHub, and the installed app — not from memory.
>
> Companion docs already in the repo: `CLAUDE.md` (AI primer + do-not-touch list),
> `DEVELOPER.md` (human onboarding), `CHANGELOG.md`.

---

## 1. TL;DR — state as of 2026-06-17

| Thing | State |
|-------|-------|
| `main` HEAD | `c55d2b3` — pushed, clean working tree (only untracked docs, see §9) |
| App version | **1.8.0** (`version.py`) |
| GitHub release | **v1.8.0 published & live** — `/releases/latest` returns v1.8.0, **single asset `PhoenixCheckoutTool_FullInstall.zip`**, not draft, not prerelease, tag → `3e3d98f` |
| Auto-updater | **Full-bundle swap, hardened** (`updater.py`). The exe-only design that bricked is gone. |
| Tests | **63 pass** (`python -m unittest discover -s tests`) |
| Operator's own machine | Reinstalled to hardened v1.8.0, boots clean. Old install backup already removed. |
| Biggest open risk | `CheckoutStore._save()` has **no error handling** → can crash the GUI on autosave (§6 #1). |

**The one rule that keeps everyone un-bricked:** a v1.8.0 GitHub release must carry
**only** `PhoenixCheckoutTool_FullInstall.zip`. **Never** attach an asset named
`PhoenixCheckoutTool.zip` — every deployed v1.0.0–v1.7.1 client matches that exact
name and would attempt the brick-prone exe-only update. See §4.

---

## 2. What this is

Windows desktop app (PySide6/Qt) for ATS field technicians to create, track, and
export valve **checkout records** across Phoenix Celeris (Fume Hood, GEX, MAV,
Snorkel, Canopy, Draw Down Bench, Gas Cabinet) and CSCP (ACM Fume Hood, PBC Room)
product lines. Data model is **Job → Room → Valve**. Exports to `.xlsx` via openpyxl
(per-valve checkout sheets + a job-level "Startup Report" + a combined report).
Ships as a PyInstaller `--onedir` build, installed under
`%LOCALAPPDATA%\ATS Inc\Phoenix Valve Checkout Tool`, auto-updating from GitHub
Releases on the maintainer's `JustinGlave/Phoenix-Checkout-Tool` repo.

---

## 3. Get it running (dev)

```powershell
git submodule update --init --recursive          # phoenix-commons submodule is MANDATORY
py -3.12 -m venv .venv                            # Python 3.12 is the canonical build venv (ADR-014)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt   # resolves -e ./commons
.\.venv\Scripts\python.exe checkout_tool_gui.py   # run from source
.\.venv\Scripts\python.exe -m unittest discover -s tests -v     # 63 tests
```

User data (do **not** touch in any swap): `%APPDATA%\ATS Inc\Phoenix Valve Checkout Tool\data.json`
(Roaming — a *different* tree from the Local install dir).

---

## 4. The auto-updater story — READ BEFORE TOUCHING `updater.py` OR CUTTING A RELEASE

### What happened
v1.8.0 was first shipped with the **exe-only** auto-updater (the update zip and
`apply_update` replaced only `PhoenixCheckoutTool.exe`, leaving the deployed
`_internal/` runtime in place). The dev build used a different PyInstaller toolchain
than what built the deployed v1.7.1 `_internal`, so the new bootloader exe couldn't
start against the stale runtime → **"Failed to start embedded python interpreter!"**
The operator's machine bricked on auto-update. (This was the exact §2.2 risk called
out in `docs/PROJECT_REVIEW.md`.)

### The fix (current architecture)
Re-architected to a **full-bundle swap**. Commits: `861c304` (full-bundle) →
`3e3d98f` (hardening) → `c55d2b3` (pin PyInstaller).

- `download_update` pulls the **whole onedir bundle** zip (exe + `_internal`).
- `apply_update` (`updater.py:209`) → `_apply_bat_content` (`updater.py:154`) generates
  a batch that swaps the **entire install folder**, so a toolchain change can never
  leave a new bootloader on a stale `_internal`.
- **Hardening (`3e3d98f`, `updater.py:154–206`):**
  - Extracts into a staging dir that is a **sibling of the install dir**
    (`<install-parent>\pct_update_<pid>`) → guaranteed same volume → both moves are
    **atomic NTFS renames**, not cross-volume copies (closes the partial-copy brick).
  - **`errorlevel`-guarded** moves: failed move-aside relaunches the untouched old
    install; failed move-in **rolls back** to `<inst>.bak-<pid>`.
  - **Integrity gate**: the swap is only accepted (and the backup discarded) if both
    `EXE_NAME` **and** `_internal` exist afterward; otherwise it rolls back.
- Tested end-to-end against the **real** rebuilt zip + synthetic rollback cases
  (`tests/test_updater_apply.py`, included in the 63 passing tests).

### Config contract (`updater.py:73–86`) — do not casually change
```
GITHUB_OWNER    = "JustinGlave"
GITHUB_REPO     = "Phoenix-Checkout-Tool"
ZIP_ASSET_NAME  = "PhoenixCheckoutTool_FullInstall.zip"   # full-bundle asset
BUNDLE_DIR_NAME = "PhoenixCheckoutTool"                    # top folder inside the zip
EXE_NAME        = "PhoenixCheckoutTool.exe"
```
`check_for_update` facades to `phoenix_commons.updater.check_for_update`, which finds
the release asset by **exact, case-insensitive name match** (verified: `==`, no
substring/first-asset/zipball fallback).

### Rollout state (important for §6 #4)
- **Existing v1.7.1 (and older) clients will NOT auto-update** to this v1.8.0 — by
  design. Their shipped updater searches for the old asset name `PhoenixCheckoutTool.zip`,
  which is **not** attached → returns "no update" → no banner, no download, **no brick**.
  They stay safely on v1.7.1.
- To get any machine onto the hardened updater it needs **one manual full install**
  from `PhoenixCheckoutTool_FullInstall.zip` (or a Setup.exe). After that, v1.9.0+
  auto-updates use the robust full-bundle swap.
- The operator's machine has already been manually reinstalled and is on the hardened
  updater.

### NEVER do this
- Do **not** attach `PhoenixCheckoutTool.zip` to any release (would make old clients
  attempt the exe-only update again).
- `build.bat` no longer produces an exe-only zip — keep it that way.

---

## 5. Architecture map (key files)

Monolithic by design (`CLAUDE.md` "Phase 3B scope discipline" — do **not** extract
classes "while we're here").

| File | Role |
|------|------|
| `checkout_tool_gui.py` (~3.5k lines) | The whole GUI. 3-level tree (job→room→valve), job detail view, room view (sortable), dialogs (NewCheckout, Batch, `StartupReportDialog`), update banner wiring. |
| `checkout_tool_backend.py` | `Job` / `Room` / `ValveCheckout` dataclasses; `CheckoutStore` (CRUD + JSON persistence at `_save`/`_load`); idempotent Job→Room migration. `_DATA_VERSION = 2`. |
| `checkout_export.py` | Per-valve checkout `.xlsx` export. |
| `startup_report_export.py` | Job-level Startup Report + combined report; `prefill_meta` sources project identity from the Job. |
| `startup_report_template.py` | Embedded base64 v2.0 xlsx template. |
| `updater.py` | Auto-updater (§4). `check_for_update` = commons facade; `download_update`/`apply_update` are **local** (threaded-install split — keep). |
| `version.py` | `__version__`. |
| `build.bat` | PyInstaller `--onedir` build → `dist\PhoenixCheckoutTool\` + `PhoenixCheckoutTool_FullInstall.zip`. Has an interactive `pause` + an Inno Setup step (**Inno is NOT installed on the dev box** → Setup.exe is skipped there). |
| `installer.iss` | Inno Setup config; installs to `{localappdata}\ATS Inc\Phoenix Valve Checkout Tool`. |
| `commons/` | `phoenix-commons` **git submodule** (editable `-e ./commons`): theme, widgets, `_app_data_path`, `updater.check_for_update`. |
| `requirements.txt` | `PySide6==6.11.0`, `openpyxl==3.1.5`, **`pyinstaller==6.20.0`** (pinned in `c55d2b3` — see §6), `-e ./commons`. |

Data model: `Job` (id, job_number=Project Number, job_name=Project Name,
project_manager, building_address, site_name, floor, archived) → `Room` (id, job_id,
name) → `ValveCheckout` (has `room_id`; `location_room` retired, kept only as a
load/migration fallback).

---

## 6. Open work — prioritized

### #1 — `_save` crash (HIGH, verified present) — recommended first
`CheckoutStore._save()` (`checkout_tool_backend.py:169`) has **no error handling**.
It is called from **13 mutation sites** (lines 167, 244, 250, 258, 265, 272, 286, 292,
299, 318, 324, 329). A failed write — disk full, a permission/AV/OneDrive lock on
`data.json` in Roaming (plausible on corporate machines) — raises straight into the
GUI autosave path and can **crash the app and lose the in-flight edit**. (`_load`
right above it *is* defensively wrapped; `_save` is not.)
Related: GUI blocks toggle `self._loading` (`checkout_tool_gui.py:3519`→`3586`, also
`1951`/`3286`) **without `try/finally`**; the autosave guard is
`if self._loading or self._current_id is None: return` (`gui:3509`), so an exception
mid-block can leave autosave **silently disabled** for the session.
**Fix:** wrap `_save` (surface a clear, non-fatal error; never leave state half-set);
put the `_loading` toggles in `try/finally`. Add a test that `_save` failure doesn't
propagate. Small, high-value.

### #2 — Prove the auto-update path for real (HIGH, given the brick history)
Everything in §4 is verified by unit tests + a synthetic apply + a boot smoke, but the
**full real path** (a v1.8.0 client detecting a newer release → download → swap →
relaunch) has not run in production since the brick. **Now is the ideal time: only the
operator's machine is on v1.8.0, so blast radius = 1.** Cut a throwaway v1.8.1 (or a
pre-release on a test channel), watch that machine auto-update once end-to-end, then
roll others. Converts "verified by construction" into "observed working."

### #3 — Render Project Manager on the Startup Report (feature gap)
`project_manager` is captured at the Job level and on the job detail view, but there is
**no template cell** for it on the Startup Report yet — so it never prints. Needs a
Cover-cell addition in `startup_report_template.py` + wiring in
`startup_report_export.py`. (Tracked in the `rooms-restructure` memory note.)

### #4 — Roll v1.8.0 to the other technicians (operational)
Each existing v1.7.1 machine needs **one manual reinstall** of
`PhoenixCheckoutTool_FullInstall.zip` to get onto the hardened updater (§4 rollout).
Build a **Setup.exe** for brand-new users on a machine that has **Inno Setup 6**
(the dev box doesn't) — `build.bat` already wires the Inno step.

### #5 — Housekeeping (low)
- Local branch `feature/startup-report-refinements` is merged into `main` (merge
  `aaaada7`) but still present — safe to delete.
- Stray `v1.7.1-rc1` tag exists (harmless; its embedded version is `1.7.1`).
- `dist/` build artifacts are on disk (gitignored build output).

### Deferred / operator-deprioritized — do NOT raise unless the operator does
- **Ed25519 update signing.** IT flagged the unsigned update chain
  (`docs/PROJECT_REVIEW.md` §, `auto-updater-security-work` memory). The operator has
  **explicitly deprioritized** this for now. Recorded here for completeness only —
  do not bring it up unprompted.

---

## 7. Landmines / do-NOT-change casually (from `CLAUDE.md` + this work)

| Item | Why |
|------|-----|
| Release asset name `PhoenixCheckoutTool_FullInstall.zip` (and never `PhoenixCheckoutTool.zip`) | §4 — old clients brick on the old name; new updater needs the new name. |
| `GITHUB_OWNER`/`GITHUB_REPO`/`ZIP_ASSET_NAME`/`BUNDLE_DIR_NAME`/`EXE_NAME` in `updater.py` | Auto-updater contract — changing strands existing users. |
| Install path `{localappdata}\ATS Inc\Phoenix Valve Checkout Tool` | Inno upgrade-detection identity. |
| Split `download_update` + `apply_update` API | v1.7.0 threaded-install behavior depends on it. |
| Monolithic `checkout_tool_gui.py` | Intentional per Phase 3B — don't refactor into modules opportunistically. |
| PyInstaller pin `==6.20.0` | Frozen-build reproducibility; bump deliberately, then rebuild + boot-test. |
| `commons/` submodule + `-e ./commons` | Submodule init is mandatory on a fresh clone before `pip install`. |

---

## 8. Build / release / verify cheat-sheet

```powershell
# Build (on a machine with the canonical venv; Inno optional for Setup.exe):
.\build.bat                       # -> dist\PhoenixCheckoutTool\ + PhoenixCheckoutTool_FullInstall.zip

# Verify the release is in the safe state (read-only):
gh api repos/JustinGlave/Phoenix-Checkout-Tool/releases/latest --jq '{tag:.tag_name, draft:.draft, prerelease:.prerelease, assets:[.assets[].name]}'
#   expect: {"tag":"v1.8.0","draft":false,"prerelease":false,"assets":["PhoenixCheckoutTool_FullInstall.zip"]}

# Cut the NEXT release (example v1.9.0) AFTER bumping version.py + CHANGELOG and rebuilding:
#   1) tag the release commit, push the tag
#   2) gh release create v1.9.0 "dist\PhoenixCheckoutTool_FullInstall.zip" --title "..." --notes-file <notes> --latest
#   3) attach ONLY the FullInstall zip (Setup.exe optional/harmless). NEVER PhoenixCheckoutTool.zip.
#   4) gh release create reuses an EXISTING tag as-is and will NOT retarget it — fix the tag first if it's stale.
```
`CHANGELOG.md` `[Unreleased]` already has the PyInstaller-pin entry staged for the
next release.

---

## 9. Reference docs & memory

In-repo `docs/` (committed alongside this handover):
- `docs/PROJECT_REVIEW.md` — 46-agent project-wide review (origin of the §2.2 brick warning).
- `docs/CHECKOUT_STARTUP_REPORT_FEATURE_AUDIT.md` — Startup Report feature audit.
- `docs/CHECKOUT_STARTUP_REPORT_EXPORT_CLEANUP_REPORT.md` — export cleanup report.
- plus the Startup Report MVP/merge/refinements reports.
- `Code Review - checkout_tool_gui.docx` (repo root) — external code review (binary, left untracked on purpose).

Auto-memory (local to this machine, `~/.claude/.../memory/`, may not travel to Cowork —
key facts are inlined above so this handover stands alone):
- `auto-updater-security-work.md` — the brick incident + fix + republish (now ✅).
- `checkout-store-save-crash.md` — the §6 #1 bug.
- `rooms-restructure.md` — the Job→Room→Valve restructure + the PM-on-report gap.
- `startup-report-export-feature.md` — Startup Report feature history.

Canonical platform doctrine: `commons/docs/ui-platform-baseline-v1/` (MIGRATION_RULES,
RETROFIT_PLAYBOOK, Phase 3B reports).
