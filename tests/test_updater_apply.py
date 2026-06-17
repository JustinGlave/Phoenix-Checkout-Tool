"""
Tests for the full-bundle updater apply step (updater._apply_bat_content).

Runs the ACTUAL generated batch against a fake install folder + a fake full-build
zip and verifies the whole install folder (exe + _internal) is swapped — the
behaviour that replaces the brittle exe-only update. Windows-only (cmd batch).

    .venv\\Scripts\\python.exe -m unittest tests.test_updater_apply -v
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import updater

# A tiny, harmless real exe to stand in for PhoenixCheckoutTool.exe so the
# batch's final `start "" exe` relaunch is a no-op that exits immediately.
_HARMLESS_EXE = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "hostname.exe")


class BatContentTests(unittest.TestCase):
    def test_targets_full_bundle_asset(self):
        self.assertEqual(updater.ZIP_ASSET_NAME, "PhoenixCheckoutTool_FullInstall.zip")
        self.assertEqual(updater.BUNDLE_DIR_NAME, "PhoenixCheckoutTool")

    def test_bat_has_swap_rollback_relaunch(self):
        bat = updater._apply_bat_content(
            r"C:\App\PhoenixCheckoutTool.exe", r"C:\App", r"C:\t\u.zip", 4242)
        self.assertIn(".bak-4242", bat)                 # rename-old-aside
        self.assertIn(updater.BUNDLE_DIR_NAME, bat)      # extract inner folder
        self.assertIn('move ', bat)                       # folder swap
        self.assertIn('start "" "C:\\App\\PhoenixCheckoutTool.exe"', bat)  # relaunch
        self.assertNotIn("Copy-Item", bat)               # no longer exe-only copy
        # Hardened swap: every move is errorlevel-guarded with a rollback branch
        # and the swap is gated on exe AND _internal before the backup is dropped.
        self.assertIn("errorlevel", bat)                 # guarded moves
        self.assertIn(":rollback", bat)                  # rollback branch
        self.assertIn("_internal", bat)                  # integrity gate (not just exe)
        # Staging dir is a SIBLING of the install dir (parent of C:\App is C:\),
        # guaranteeing the same volume so both moves are atomic renames — NOT %TEMP%
        # (which could be on a different volume and degrade move to a partial copy).
        self.assertIn(r"C:\pct_update_4242", bat)
        self.assertNotIn("%TEMP%", bat)


@unittest.skipUnless(sys.platform.startswith("win"), "updater batch is Windows-only")
class FullBundleSwapTests(unittest.TestCase):
    def test_end_to_end_folder_swap(self):
        work = tempfile.mkdtemp(prefix="upd_apply_")
        try:
            # ── fake CURRENT install (exe + _internal/old.txt) ──────────────────
            install = os.path.join(work, "App")
            os.makedirs(os.path.join(install, "_internal"))
            shutil.copy(_HARMLESS_EXE, os.path.join(install, updater.EXE_NAME))
            with open(os.path.join(install, "_internal", "old.txt"), "w") as f:
                f.write("OLD RUNTIME")

            # ── fake NEW full-build bundle, zipped with the BUNDLE_DIR_NAME root ─
            bundle_root = os.path.join(work, "bundle")
            inner = os.path.join(bundle_root, updater.BUNDLE_DIR_NAME)
            os.makedirs(os.path.join(inner, "_internal"))
            shutil.copy(_HARMLESS_EXE, os.path.join(inner, updater.EXE_NAME))
            with open(os.path.join(inner, "_internal", "new.txt"), "w") as f:
                f.write("NEW RUNTIME")
            zip_path = os.path.join(work, "PhoenixCheckoutTool_FullInstall.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                for root, _dirs, files in os.walk(inner):
                    for fn in files:
                        full = os.path.join(root, fn)
                        arc = os.path.relpath(full, bundle_root).replace(os.sep, "/")
                        z.write(full, arc)

            # ── run the ACTUAL generated batch (pid 999999 is not running) ──────
            exe = os.path.join(install, updater.EXE_NAME)
            bat_path = os.path.join(work, "apply.bat")
            with open(bat_path, "w") as f:
                f.write(updater._apply_bat_content(exe, install, zip_path, 999999))
            subprocess.run(["cmd.exe", "/c", bat_path], timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # ── verify the WHOLE folder swapped (exe + _internal) ───────────────
            self.assertTrue(os.path.exists(os.path.join(install, "_internal", "new.txt")),
                            "new _internal not swapped in")
            self.assertFalse(os.path.exists(os.path.join(install, "_internal", "old.txt")),
                             "stale _internal not replaced (this is the brick cause)")
            self.assertTrue(os.path.exists(os.path.join(install, updater.EXE_NAME)),
                            "exe missing after swap")
            self.assertFalse(os.path.exists(install + ".bak-999999"), "backup not cleaned up")
            self.assertFalse(os.path.exists(zip_path), "downloaded zip not cleaned up")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_rollback_when_bundle_missing_exe(self):
        # If the extracted bundle has no exe, the old install must be left intact.
        work = tempfile.mkdtemp(prefix="upd_rb_")
        try:
            install = os.path.join(work, "App")
            os.makedirs(os.path.join(install, "_internal"))
            shutil.copy(_HARMLESS_EXE, os.path.join(install, updater.EXE_NAME))
            with open(os.path.join(install, "_internal", "old.txt"), "w") as f:
                f.write("OLD")
            # bundle WITHOUT the exe
            bundle_root = os.path.join(work, "bundle")
            inner = os.path.join(bundle_root, updater.BUNDLE_DIR_NAME)
            os.makedirs(inner)
            with open(os.path.join(inner, "junk.txt"), "w") as f:
                f.write("x")
            zip_path = os.path.join(work, "PhoenixCheckoutTool_FullInstall.zip")
            with zipfile.ZipFile(zip_path, "w") as z:
                z.write(os.path.join(inner, "junk.txt"),
                        f"{updater.BUNDLE_DIR_NAME}/junk.txt")
            exe = os.path.join(install, updater.EXE_NAME)
            bat_path = os.path.join(work, "apply.bat")
            with open(bat_path, "w") as f:
                f.write(updater._apply_bat_content(exe, install, zip_path, 999998))
            subprocess.run(["cmd.exe", "/c", bat_path], timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # old install must still be intact (no brick from a bad bundle)
            self.assertTrue(os.path.exists(os.path.join(install, updater.EXE_NAME)),
                            "exe lost on bad-bundle update")
            self.assertTrue(os.path.exists(os.path.join(install, "_internal", "old.txt")),
                            "old _internal lost on bad-bundle update")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_rollback_when_bundle_missing_internal(self):
        # A bundle that has the exe but NO _internal must NOT be swapped in: the
        # integrity gate (exe AND _internal) must fire and roll back to the old
        # install. This is the partial/stale-runtime case the gate exists to catch.
        work = tempfile.mkdtemp(prefix="upd_rbi_")
        try:
            install = os.path.join(work, "App")
            os.makedirs(os.path.join(install, "_internal"))
            shutil.copy(_HARMLESS_EXE, os.path.join(install, updater.EXE_NAME))
            with open(os.path.join(install, "_internal", "old.txt"), "w") as f:
                f.write("OLD")
            # bundle WITH the exe but WITHOUT _internal
            bundle_root = os.path.join(work, "bundle")
            inner = os.path.join(bundle_root, updater.BUNDLE_DIR_NAME)
            os.makedirs(inner)
            shutil.copy(_HARMLESS_EXE, os.path.join(inner, updater.EXE_NAME))
            zip_path = os.path.join(work, "PhoenixCheckoutTool_FullInstall.zip")
            with zipfile.ZipFile(zip_path, "w") as z:
                z.write(os.path.join(inner, updater.EXE_NAME),
                        f"{updater.BUNDLE_DIR_NAME}/{updater.EXE_NAME}")
            exe = os.path.join(install, updater.EXE_NAME)
            bat_path = os.path.join(work, "apply.bat")
            with open(bat_path, "w") as f:
                f.write(updater._apply_bat_content(exe, install, zip_path, 999997))
            subprocess.run(["cmd.exe", "/c", bat_path], timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # old install fully restored (exe + the _internal the gate protected)
            self.assertTrue(os.path.exists(os.path.join(install, updater.EXE_NAME)),
                            "exe lost when bundle missing _internal")
            self.assertTrue(os.path.exists(os.path.join(install, "_internal", "old.txt")),
                            "old _internal lost — integrity gate failed to roll back")
            self.assertFalse(os.path.exists(install + ".bak-999997"),
                             "backup left behind after rollback")
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
