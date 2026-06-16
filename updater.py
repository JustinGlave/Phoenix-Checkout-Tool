"""
updater.py — Phoenix Valve Checkout Tool auto-updater (Phase 3B retrofit).

How it works
------------
1. On startup the GUI calls check_for_update() in a background thread.
2. That function hits the GitHub Releases API and compares the latest tag
   against the local __version__ string.
3. If a newer version exists it returns an UpdateInfo object; the GUI shows
   a banner with an "Install & Restart" button.
4. When the user clicks the button, the GUI calls download_update() in a
   background thread (with a progress callback), then apply_update() on the
   main thread once the download is complete.

Phase 3B retrofit notes
-----------------------
- ``check_for_update`` now facades to
  ``phoenix_commons.updater.check_for_update``. The zero-arg local
  signature is preserved.
- ``UpdateInfo`` is re-imported from commons so types match across the
  facade boundary (callers' ``Optional[updater.UpdateInfo]`` annotations
  resolve to the same class).
- ``download_update`` / ``apply_update`` STAY LOCAL — commons has no
  split download/apply API; Checkout's threaded-install behavior (added
  in v1.7.0) depends on the split. Per
  MIGRATION_RULES.md § "Delete duplication, not behaviour", preserving
  the threaded-install behavior takes precedence over consuming commons
  symmetry. The split pattern is documented as a future commons-API
  candidate in Phase 3B's post-retrofit report.
- ``download_and_apply`` (the convenience wrapper around
  download_update + apply_update) is kept local to maintain the existing
  module's complete public surface. The GUI does NOT call this wrapper;
  it uses the split API directly.
- Updater payload contract (CHANGED in v1.8.0): **full-bundle**. apply_update
  now downloads the FULL build zip (the whole onedir folder: exe + _internal)
  and swaps the entire install folder, replacing the prior exe-only contract.
  Rationale: an exe-only update leaves the deployed _internal in place, so a
  build-toolchain change (PyInstaller / Python patch) produces a new bootloader
  exe that can't start against the stale runtime ("Failed to start embedded
  python interpreter"). Swapping the whole folder makes updates robust to
  toolchain drift. (Supersedes the ADR-003 exe-only / expected_internal=False
  note in the comments below.)

Configuration
-------------
Set GITHUB_OWNER and GITHUB_REPO to match your GitHub account and repository.
Set ZIP_ASSET_NAME to the FULL-INSTALL zip uploaded to the GitHub release
(produced by build.bat as PhoenixCheckoutTool_FullInstall.zip), and
BUNDLE_DIR_NAME to the top-level folder inside it.
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
import logging
from typing import Optional
from pathlib import Path
import urllib.request
import urllib.error

from version import __version__

from phoenix_commons.updater import (
    UpdateInfo,
    check_for_update as _commons_check_for_update,
)

logger = logging.getLogger(__name__)

# ── CHANGE THESE ──────────────────────────────────────────────────────────────
GITHUB_OWNER   = "JustinGlave"
GITHUB_REPO    = "Phoenix-Checkout-Tool"
# Full-bundle auto-update (v1.8.0+): the updater downloads the FULL build zip
# (the whole onedir folder: exe + _internal) and swaps the entire install folder,
# so a build-toolchain change can never leave a new bootloader exe on a stale
# _internal runtime (the failure mode exe-only updates were prone to).
#   ZIP_ASSET_NAME  — the full-install zip asset attached to the GitHub release.
#   BUNDLE_DIR_NAME — the top-level folder inside that zip (Compress-Archive of
#                     dist\PhoenixCheckoutTool puts everything under this folder).
ZIP_ASSET_NAME  = "PhoenixCheckoutTool_FullInstall.zip"
BUNDLE_DIR_NAME = "PhoenixCheckoutTool"
EXE_NAME        = "PhoenixCheckoutTool.exe"
# ──────────────────────────────────────────────────────────────────────────────


def check_for_update() -> Optional[UpdateInfo]:
    """Query the GitHub Releases API for ``Phoenix-Checkout-Tool``.

    Returns :class:`UpdateInfo` if a newer release is available, otherwise
    ``None``. Safe to call from a background thread — never raises (network
    failures + payload-parse errors are logged inside the commons
    implementation, never propagated).

    Phase 3B retrofit: facade over
    :func:`phoenix_commons.updater.check_for_update`. The zero-arg local
    signature is preserved; the 4 config constants above are passed through.
    """
    return _commons_check_for_update(
        owner=GITHUB_OWNER,
        repo=GITHUB_REPO,
        current_version=__version__,
        zip_asset_name=ZIP_ASSET_NAME,
    )


def download_update(info: UpdateInfo, tmp_zip: Path,
                    progress_callback=None) -> None:
    """
    Download the new zip into tmp_zip.

    progress_callback(bytes_done, total_bytes) is called during download.
    Raises RuntimeError on failure so the caller can show an error dialog.
    Safe to call from a background thread.

    Phase 3B note: kept LOCAL (not a commons facade). Commons exposes only
    the combined ``download_and_apply`` — splitting download from apply
    is Checkout-specific (v1.7.0 threaded-install behavior).
    ``expected_internal=False`` semantics: no zip-content validation here;
    the apply step extracts ``EXE_NAME`` directly via PowerShell.
    """
    try:
        req = urllib.request.Request(
            info.download_url,
            headers={"User-Agent": EXE_NAME},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done  = 0
            chunk = 64 * 1024
            with open(tmp_zip, "wb") as fh:
                while True:
                    block = resp.read(chunk)
                    if not block:
                        break
                    fh.write(block)
                    done += len(block)
                    if progress_callback:
                        progress_callback(done, total)

        if total > 0 and tmp_zip.stat().st_size < total:
            tmp_zip.unlink(missing_ok=True)
            raise RuntimeError("Download incomplete. Please try again.")

    except RuntimeError:
        raise
    except Exception as exc:
        tmp_zip.unlink(missing_ok=True)
        raise RuntimeError(f"Download failed: {exc}") from exc


def _apply_bat_content(exe_str: str, inst_str: str, zip_str: str, pid: int) -> str:
    """Build the updater batch script (full-bundle swap). Extracted for testing.

    The script: waits for the running process (``pid``) to exit; extracts the
    full-build zip; renames the old install folder aside; moves the new bundle
    into place (a same-volume rename — effectively atomic); verifies the new exe
    exists and rolls back to the old folder if not; relaunches; cleans up. Swapping
    exe + _internal together avoids the stale-runtime brick of exe-only updates.
    """
    zip_ps = zip_str.replace("'", "''")
    return f"""@echo off
:wait
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait
)
set "PKG=%TEMP%\\pct_update_{pid}"
if exist "%PKG%" rmdir /s /q "%PKG%"
powershell -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('{zip_ps}', '%PKG%')"
if not exist "%PKG%\\{BUNDLE_DIR_NAME}\\{EXE_NAME}" goto relaunch
if exist "{inst_str}.bak-{pid}" rmdir /s /q "{inst_str}.bak-{pid}"
move "{inst_str}" "{inst_str}.bak-{pid}" >nul
move "%PKG%\\{BUNDLE_DIR_NAME}" "{inst_str}" >nul
if exist "{inst_str}\\{EXE_NAME}" goto ok
if exist "{inst_str}" rmdir /s /q "{inst_str}"
move "{inst_str}.bak-{pid}" "{inst_str}" >nul
goto relaunch
:ok
rmdir /s /q "{inst_str}.bak-{pid}" >nul 2>nul
:relaunch
if exist "%PKG%" rmdir /s /q "%PKG%" >nul 2>nul
del "{zip_str}" >nul 2>nul
start "" "{exe_str}"
del "%~f0"
"""


def apply_update(info: UpdateInfo, tmp_zip: Path) -> None:
    """
    Replace the entire install folder (exe + _internal) with the downloaded
    full-build bundle via a batch script, then exit.

    Full-bundle update (v1.8.0+): the downloaded zip is the complete onedir build
    (``BUNDLE_DIR_NAME``/ holding the exe + _internal). The batch waits for this
    process to exit, extracts the bundle, renames the old install folder aside,
    moves the new bundle into place (a same-volume rename, effectively atomic),
    verifies the new exe and rolls back on failure, relaunches, and deletes the old
    copy. Swapping exe + _internal together means a build-toolchain change can never
    leave a new bootloader on a stale runtime.

    Must be called from the compiled exe (sys.frozen). Never returns normally — it
    launches the batch and calls sys.exit(0). Raises RuntimeError if run from source.
    """
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "Update can only be applied to a compiled build.\n"
            "You're running from source — pull the latest code from GitHub instead."
        )

    exe      = Path(sys.executable).resolve()
    exe_str  = str(exe)
    inst_str = str(exe.parent)   # the install folder (exe + _internal live here)
    zip_str  = str(tmp_zip)

    bat_fd, bat_path_str = tempfile.mkstemp(suffix=".bat")
    os.close(bat_fd)
    with open(bat_path_str, "w") as fh:
        fh.write(_apply_bat_content(exe_str, inst_str, zip_str, os.getpid()))

    subprocess.Popen(
        ["cmd.exe", "/c", bat_path_str],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )
    sys.exit(0)


def download_and_apply(info: UpdateInfo, progress_callback=None) -> None:
    """
    Download the new zip, extract the exe over the current install, and restart.

    Convenience wrapper around download_update() + apply_update().
    Raises RuntimeError on failure so the caller can show an error dialog.

    Phase 3B note: kept LOCAL. The GUI does NOT call this wrapper — it
    uses the split download_update + apply_update pattern (threaded-install).
    Retained as a public convenience for any external caller.
    """
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "Update can only be applied to a compiled build.\n"
            "You're running from source — pull the latest code from GitHub instead."
        )

    tmp_fd, tmp_zip_str = tempfile.mkstemp(suffix=".zip")
    os.close(tmp_fd)
    tmp_zip = Path(tmp_zip_str)

    try:
        download_update(info, tmp_zip, progress_callback)
    except Exception:
        tmp_zip.unlink(missing_ok=True)
        raise

    apply_update(info, tmp_zip)


__all__ = [
    # Tool-specific config (used by GUI via `updater.GITHUB_OWNER` etc.)
    "GITHUB_OWNER", "GITHUB_REPO", "ZIP_ASSET_NAME", "EXE_NAME",
    # Public UpdateInfo dataclass — re-exported from commons.
    "UpdateInfo",
    # Public API.
    "check_for_update",
    "download_update",
    "apply_update",
    "download_and_apply",
]
