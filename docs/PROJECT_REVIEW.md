# Phoenix Checkout Tool — Project-Wide Review

**Date:** 2026-06-16
**Reviewed version:** v1.7.0 (`version.py`)
**Method:** Multi-agent review — 6 subsystem mapping agents, 5 review dimensions (security, correctness, robustness, quality, build/packaging), and adversarial verification of every candidate finding (each finding re-checked by an independent agent instructed to *refute* it).
**Results:** 34 candidate findings → **29 confirmed**, **5 rejected as false positives**.

Severity counts (post-verification, corrected ratings): **1 Critical · 3 High · ~12 Medium · ~13 Low**

---

## 1. Executive summary

The codebase is small, well-organized at the module level, and has several genuinely good design choices (atomic JSON saves via `os.replace`, per-record load resilience, a clean export/backend/GUI separation). The risk is concentrated almost entirely in **one subsystem: the GitHub auto-updater and its build/packaging pipeline.**

Two things stand out above everything else:

1. **The unsigned update chain** that your IT department's scanner flagged is real and correctly rated. (Confirmed — see §2.1.)
2. **A second, independent problem the scanner did *not* flag:** the update mechanism replaces *only the .exe* inside a multi-file PyInstaller bundle. This will **silently brick every auto-updated install** the first time a release changes any dependency version. This is a latent time-bomb, not a present-day outage — but it's arguably more certain to bite you than the security issue, because it triggers on a routine `pip` upgrade rather than an attacker. (Confirmed — see §2.2.)

These two are coupled: **the fix for the security issue (signing the update) and the fix for the brick risk (changing what the update ships) touch the same code and the same release artifact.** Doing them together is cheaper than doing them twice. The recommended remediation plan in §5 addresses both.

---

## 2. The auto-update subsystem (highest priority)

### 2.1 — CRITICAL · Unsigned, unverified update chain

**Files:** `updater.py:111-196` · reached from `checkout_tool_gui.py:1015` (startup check) and `:3345` (Install & Restart)

The updater downloads a zip from a GitHub release, extracts an exe, overwrites the running executable, and relaunches it — with **no code-signature check and no hash/checksum verification.** The only validation is a Content-Length byte-count (`updater.py:139`).

Anyone who can serve the bytes for that release asset — a compromised GitHub account or release token, a malicious release, or a tampered CI pipeline — achieves arbitrary code execution as the current user on every machine that auto-updates.

**Calibration note:** the download is HTTPS and `urllib` validates TLS certificates by default, so a casual passive network MITM is harder than a worst-case reading suggests. The realistic vector is **compromise of the release channel** (your personal `JustinGlave` GitHub account is the single point of trust). TLS protects transport; it does not protect *artifact authenticity*. With no signature pinned into the client, one release-pipeline compromise = silent fleet-wide RCE with no second line of defense. **Critical is correct.**

> This matches your IT department's finding exactly. Their analysis was accurate and is not a false positive.

### 2.2 — HIGH · Exe-only update will brick installs on any dependency change

**Files:** `build.bat:27` (`--onedir`), `build.bat:83` (zips exe only), `updater.py:183` (copies exe only); codified in `DEVELOPER.md:281`

`build.bat` builds with `--onedir`, which produces `PhoenixCheckoutTool.exe` **plus an `_internal/` folder** containing the embedded Python runtime, all PySide6/Qt DLLs, and every bundled data file. The auto-update zip contains **only the exe**, and `apply_update` copies **only the exe** over the install — `_internal/` is never touched.

A PyInstaller exe is a thin bootloader **tightly coupled to its `_internal/` payload**: the frozen interpreter, `base_library.zip`, the PySide6 DLL/`.pyd` set, and runtime hooks must all match the version the exe was compiled against. The moment a release bumps PySide6, openpyxl's native deps, the Python minor version, or PyInstaller itself — **and none are pinned** (no `requirements.txt`; `README.md:112` just says `pip install PySide6 openpyxl pyinstaller`) — the freshly-updated exe loads the **stale** `_internal/` DLLs and fails at launch (`DLL load failed` / `ImportError`) before any UI appears.

Because the app can't start, it can never run `check_for_update` again to self-heal. **The install is bricked; the only recovery is a manual reinstall.** Every auto-updated user is affected at once.

It isn't broken on `main` today (the shipped `_internal/` matches the current exe), which is why this is High rather than Critical — but the trigger is unguarded and effectively inevitable over the life of the project.

### 2.3 — HIGH · `apply_update` can leave a broken exe and silently swallows failure

**File:** `updater.py:176-196`

The update is applied by a generated `.bat` that runs PowerShell to extract the zip and `Copy-Item -Force` the new exe over the live one, then **unconditionally** relaunches the exe and deletes the zip/script. There is no `$ErrorActionPreference='Stop'`, no exit-code check on PowerShell, no verification the copy succeeded, and no backup of the prior exe. And `apply_update` calls `sys.exit(0)` immediately after launching the batch — **so the GUI is already gone and can never detect or report a failure.**

A corrupt zip makes extraction throw *before* the copy (old exe survives — silent failed update); a missing exe-member inside the zip is a non-terminating error (PowerShell continues, exits 0 — silent failed update); only the AV/file-lock/partial-write path genuinely leaves a half-written exe. So the common case degrades to "update silently didn't apply" rather than a brick — hence High, not Critical — but the user gets *no feedback either way*.

### 2.4 — MEDIUM · Download URL trusted without scheme/host validation (SSRF / downgrade)

**File:** `updater.py:99` → fetched at `:121-125`

`check_for_update` stores `zip_asset["browser_download_url"]` verbatim and `download_update` opens it with no check that the scheme is `https` or the host is a GitHub domain. `urllib` also honors `http_proxy`/`https_proxy` env vars by default. A manipulated API response or poisoned proxy could redirect the download to `http://` or an arbitrary host. Secondary to the unsigned-chain issue, but it widens the attack surface and is cheap to close with an allowlist.

### 2.5 — MEDIUM · Download integrity check is too weak

**File:** `updater.py:139-141`

Incompleteness is flagged only when Content-Length is present *and* the file is smaller. A missing/wrong Content-Length, a mid-stream close at a plausible size, or a byte-correct-but-corrupt zip all pass, and the unchecked file goes to `apply_update`. No `zipfile.testzip()`, no check that the exe member is present. (Largely subsumed by the signing fix, which verifies the artifact cryptographically.)

### 2.6 — MEDIUM · Version tags with any non-numeric suffix never trigger an update

**File:** `updater.py:59-64`, gate at `:84`

`_parse_version` does `int(part)` on each dotted component and falls back to `(0,)` on any `ValueError`. So a stable release tagged `v1.7.1-hotfix`, `2.0.0final`, etc. parses to `(0,)`, and `(0,) <= (local)` is always true → the update is **silently never offered**, with no error. This is live, not hypothetical: **you already have a `v1.7.1-rc1` tag.** (Pre-releases are excluded by the `/releases/latest` endpoint, which bounds the impact, but a suffixed *stable* tag would silently disable updates fleet-wide.)

### 2.7 — Lower-severity updater findings

| Sev | Finding | File |
|---|---|---|
| Medium | `QThread.terminate()` on download-cancel leaks the temp zip + socket/handle (found by two dimensions) | `checkout_tool_gui.py:3356` |
| Medium | `_ReleasesFetcher` parented to a short-lived dialog → "QThread destroyed while running" crash if closed mid-fetch | `checkout_tool_gui.py:3257`, `:3289` |
| Low | Local paths interpolated into the generated `.bat` with incomplete escaping (robustness nit; inputs are local, not remote) | `updater.py:176-189` |
| Low | `ExtractToDirectory` of the downloaded zip — zip-slip surface (mitigated on patched .NET; only an issue if the key is compromised) | `updater.py:183` |
| Low | `open()` without `encoding=` — update crashes on non-cp1252 install paths (e.g. non-Latin usernames) | `updater.py:188` |
| Low | Update-check failures are indistinguishable from "up to date" (no error signal, no log handler in frozen builds) | `checkout_tool_gui.py:584` |
| Low | `mkstemp` `.bat`/`.zip` files leak on error paths | `updater.py:173-189` |
| Low | Per-user LocalAppData install (`PrivilegesRequired=lowest`) lets any local user-level process replace the exe — accepted-risk config, but it's *why* the unsigned-update issue is high-impact | `installer.iss:16-30` |

---

## 3. Findings outside the updater

### 3.1 — HIGH · `CheckoutStore._save()` has no error handling → autosave crash

**File:** `checkout_tool_backend.py:119-131`; hot path at `checkout_tool_gui.py:3109`

`_save()` writes `data.json.tmp` then `os.replace()` with no `try/except`. Any failure (permission denied, disk full, OneDrive/AV lock on `%APPDATA%`) propagates out of **every** add/update/delete — most damagingly out of the 350ms debounced autosave (`_on_any_change → _save_timer → _save_current`), which is a `QTimer` callback with no guard. PySide6 aborts the process on an unhandled exception from an event-loop slot. There is no `sys.excepthook` / `QApplication.notify` safety net anywhere.

**Worse:** `_save_current` sets `self._loading = True` at line 3073 and only resets it at line 3140 — *after* the throwing `update()` at 3109. So even a caught exception would leave `_loading` stuck `True`, **silently disabling all future autosaves** for the session. (The atomic `os.replace` does protect the *existing* file from corruption — only the new write is lost — which is why this is High, not Critical.)

### 3.2 — MEDIUM · Loading a record can silently overwrite its saved Model

**File:** `checkout_tool_gui.py:2841`, `:2878-2879`, `:3038-3041`

`_load_record` resets `_model_user_modified = False`, sets the Model field, then sets the valve type — which fires `_update_fume_hood_widgets` (not signal-blocked, no `_loading` guard). Its tail re-evaluates Model: if `not _model_user_modified and current in MODEL_DEFAULTS.values()`, it overwrites with the type's default. For a record whose stored Model is one default string but doesn't match *its* type's default (e.g. a CSCP Fume Hood manually set to `CELERIS 2`), the displayed value silently diverges from disk and the next edit re-saves the wrong value. **Silent data corruption** of legitimately-saved data, no warning. Fix: guard the auto-fill with `if not self._loading:`.

### 3.3 — MEDIUM · `_load` silently discards corrupt data, then overwrites it

**File:** `checkout_tool_backend.py:92-117`

A corrupt/unreadable `data.json` is swallowed (`except (OSError, ValueError): return`) leaving an empty store; bad individual records are dropped (`except Exception: pass`). No log, no backup, no user notice — the app looks brand-new, and the next save overwrites whatever was salvageable. Fix: rename the bad file to `data.corrupt-<timestamp>.json` and surface a one-time warning.

### 3.4 — Quality / maintainability (all Medium or Low)

| Sev | Finding | File |
|---|---|---|
| Medium | 3,606-line GUI monolith mixing UI, embedded reference data, network workers, dialogs, and themes — highest-leverage refactor is mechanical extraction (`wiring_data.py`, `points_data.py`, `theme.py`, `update_workers.py`, `dialogs.py`) | `checkout_tool_gui.py` |
| Medium | Wiring-key string contract (`p_{i}_w`, `acm_{i}_w`, `{key}_cfm`, …) is duplicated across **three** modules with no single source of truth; a typo silently yields blank Excel cells | `checkout_export.py` ↔ `checkout_tool_gui.py` |
| Medium | ~290-line `_create_test_data` QA fixture shipped to end users via the Tools menu, with no debug guard; re-hand-types the wiring-key scheme | `checkout_tool_gui.py:2321-2608` |
| Medium | Bundled Excel templates go stale on exe-only updates — a future template-layout change paired with row-map edits would write to new coordinates in old sheets, silently misaligning exports | `checkout_export.py` |
| Low | GitHub-fetch logic duplicated between `updater.py` and `_ReleasesFetcher` (User-Agent has **already** drifted: `PhoenixCheckoutTool` vs `PhoenixCheckoutTool.exe`) | `checkout_tool_gui.py:593-618` |
| Low | Dead `_app_data_path` copy in the GUI; `_resource_path` duplicated byte-for-byte in two files | `checkout_tool_gui.py:495-506` |
| Low | App-identity / support-email / QSettings org strings repeated as literals (7+ sites), with one already inconsistent | `checkout_tool_gui.py` |
| Low | Inconsistent lazy-import aliasing and error-handling conventions across modules | `checkout_tool_gui.py`, `checkout_tool_backend.py` |

### 3.5 — Build / packaging (besides §2.2)

| Sev | Finding | File |
|---|---|---|
| Medium | No reproducibility or supply-chain controls: unpinned deps, no `requirements.txt`/lock, no SBOM, unsigned exe/installer (SmartScreen "unknown publisher") | `build.bat`, `installer.iss` |
| Low | `findstr`-based version parsing is format-coupled (breaks if spacing/quotes change; unanchored substring match; no validation before it flows to the installer and the updater comparison) | `build.bat:17` |
| Low | Watermark `PTT_Transparent_green.png` is documented + referenced but not bundled; renders today only because `green.png` is tried first — latent asset-naming drift across build/runtime/docs | `build.bat:33`, `checkout_tool_gui.py:520`, `DEVELOPER.md:33` |

---

## 4. False positives rejected by the adversarial pass

Worth recording what is **not** a real issue, so it doesn't get re-raised:

1. **"1.7 vs 1.7.0 spurious update offer"** — unreachable: local `__version__` is fixed 3-component and the spurious direction can't occur.
2. **"Duplicate valve tags abort the export"** — false premise: openpyxl 3.1.5 *auto-renames* duplicate sheet titles (verified empirically end-to-end). Export succeeds.
3. **"Workbook file-handle leak on every export"** — false: default (eager) `load_workbook` closes the underlying handle before returning; `.close()` is a no-op outside read/write-only modes.
4. **"QSS red-vs-green install-button divergence proves a broken update model"** — fabricated via a misread: the "green" button is the separate *light theme* (`apply_light_theme`), not the QSS file. The QSS file and the embedded fallback are identical (`#dc2626`).
5. **"Inno Setup uninstall/auto-update race"** — self-refuting: the update batch waits for the app PID to exit before touching files, and the downloaded zip lives in `%TEMP%`, not `{app}`.

---

## 5. Remediation plan — Ed25519 update signing (Option #3)

This is the free, code-only fix we scoped: generate an Ed25519 keypair once, embed the **public** key in the app, sign the update artifact at release time with the **private** key (kept off-repo), and verify the signature in `apply_update` **before** anything is extracted or executed. It defends against the exact threat in §2.1 because an attacker who compromises the GitHub release channel still can't produce a valid signature without the private key.

### 5.1 — Files that change

| File | Change |
|---|---|
| `updater.py` | Add `verify_update(artifact, signature)` using `Ed25519PublicKey.from_public_bytes(...).verify(...)`, raising on `InvalidSignature`. Call it at the **top** of `apply_update` (after the frozen check, before the `.bat` is built). Add embedded public key(s), extend `UpdateInfo` with `signature_url`, locate the `.sig` asset in `check_for_update`, and add the https/host allowlist (closes §2.4). |
| `checkout_tool_gui.py` | `_UpdateDownloader` also downloads the detached signature and passes it through the `ready` signal; the existing `except RuntimeError` in `_on_ready` surfaces a clear "signature could not be verified — not installing" dialog. |
| `build.bat` | After the update-zip step, invoke `python sign_release.py <artifact>` (private key from an env var / off-repo path) to emit `<artifact>.sig`; update the upload checklist to require the `.sig`. |
| `sign_release.py` *(new, dev-only, not shipped)* | Loads the private key off-repo, signs the artifact, writes `.sig`. Plus a one-time `keygen` mode that prints the base64 public key. |
| `README.md` | Add `cryptography` to the install line; add a short "Release signing" section. |

### 5.2 — New dependency

`cryptography` (pure Python API for Ed25519). PyInstaller has a maintained hook and *usually* bundles it (`_cffi_backend` + OpenSSL) automatically — **but this must be confirmed with a test frozen build** before relying on it; add `--hidden-import`/`--collect-submodules cryptography` only if the test build fails to import it.

### 5.3 — My recommendations on the three open decisions

You asked to review the report first, so here's where I land and why — react to these and I'll implement:

**1. Update model → recommend "Full-bundle update + sign it."**
The §2.1 (security) and §2.2 (brick) fixes touch the same artifact. If we sign the exe-only zip, we lock in the brick time-bomb *and* sign it. Switching the updater to ship/extract the whole `--onedir` folder (extract to a sibling temp dir, then atomic directory swap) and signing **that** zip kills both problems in one coherent change. `--onefile` is the simpler alternative and is self-consistent for signing, but it pays a startup cost (the exe unpacks to temp every launch) and is a bigger behavioral change to a working install model. **Full-bundle update is the best balance.**

**2. Rollout → recommend "Tolerant first, then mandatory."**
Already-deployed v1.7.0 clients have no public key and no verification code; they'll keep using the old path no matter what. The danger is the *first* signed release. Ship verification in release N as **tolerant** (`ALLOW_UNSIGNED` flag — installs with or without a sig) so users upgrade to a verifying build first, then flip to **mandatory** in N+1. Going straight to mandatory means one forgotten `.sig` upload blocks all updates fleet-wide.

**3. Key trust → recommend "Small list of trusted keys."**
Embed an array of public keys; verification passes if any matches. It costs almost nothing now and is painful to retrofit. With a single key, losing or compromising the private key strands every existing client (manual reinstall). A trusted-list lets you rotate keys later without stranding anyone built before the rotation.

### 5.4 — Key management (non-negotiable)

The 32-byte **private** key is the crown jewel: generate it once on a trusted machine, store it **outside** the git repo (password manager, or a gitignored path with restrictive ACLs), never commit it, never put it in `build.bat`/`sign_release.py` source, never upload it. `sign_release.py` reads it from an env var (`PHOENIX_UPDATE_PRIVKEY`) at release time only. **Back it up** — losing it (with a single-key design) means you can never ship a verifiable update to deployed clients again. The public key is non-secret and gets embedded in the app.

### 5.5 — Suggested sequencing

1. Land the **High-severity, low-risk safety fixes** first, independent of signing — they're small and reduce live risk immediately:
   - `_save()` error handling + the stuck-`_loading` flag (§3.1)
   - `apply_update` exit-code check + exe backup/rollback + surfacing failures (§2.3)
   - `_parse_version` suffix handling (§2.6) — you have a suffixed tag *now*
2. Then the **signing + full-bundle update** change (§5.1–5.4), folding in the host allowlist (§2.4), zip-validation (§2.5), and zip-slip member restriction (§2.7) since they live in the same functions.
3. Add a **pinned `requirements.txt`** (§3.5) as part of the build change — it's a prerequisite for the brick fix to stay fixed.
4. Quality/refactor items (§3.4) are independent and can be scheduled whenever.

> **Scope note for IT:** signing the update artifact addresses the *download/update* RCE they flagged. It does **not** make the installed exe tamper-proof against local malware (that needs Authenticode code-signing of the exe itself, which costs money — see the earlier cost breakdown). The two are complementary; Option #3 is the free half that closes the specific finding.

---

## Appendix — Subsystem map

- **`checkout_tool_gui.py`** (3,606 lines) — `MainWindow` god-object: UI construction, job/checkout tree, 4-page stacked editor, per-valve-type wiring/config/verification panels, debounced autosave, snippets, theming, and the update flow. Also hosts embedded wiring/BACnet reference data and the three network `QThread` workers.
- **`checkout_tool_backend.py`** (206 lines) — `Job`/`ValveCheckout` dataclasses + `CheckoutStore` JSON persistence under `%APPDATA%\ATS Inc\Phoenix Valve Checkout Tool\`. Atomic saves; full-file rewrite per mutation; no concurrency control or schema migration.
- **`checkout_export.py`** (553 lines) — openpyxl export. One fill function per template family (Celeris FH / GEX-MAV / CSCP ACM / PBC Room), driven by hand-audited cell-coordinate maps; multi-record batches transplant sheets via `_copy_ws_into`.
- **`updater.py`** (222 lines) — GitHub-releases auto-updater: `check_for_update` / `download_update` / `apply_update`. The subsystem carrying nearly all the risk in this review.
- **`build.bat` / `installer.iss` / `version.py`** — PyInstaller `--onedir` build, Inno Setup per-user installer, two zip artifacts. `version.py` is the single version source, read by both the build and the running app.
