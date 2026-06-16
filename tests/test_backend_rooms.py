"""
Tests for the Job -> Room -> ValveCheckout backend (model + store + migration).

Patches checkout_tool_backend.DATA_FILE to a temp file so CheckoutStore load/save
(and the one-time legacy migration) run against disposable data. stdlib unittest.

    .venv\\Scripts\\python.exe -m unittest tests.test_backend_rooms -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import checkout_tool_backend as be
from checkout_tool_backend import CheckoutStore, Job, Room, ValveCheckout


class _TempDataFile(unittest.TestCase):
    """Base: point DATA_FILE at a fresh temp file for each test."""

    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="be_rooms_")
        self._orig = be.DATA_FILE
        be.DATA_FILE = os.path.join(self._dir, "data.json")

    def tearDown(self):
        be.DATA_FILE = self._orig

    def _write_legacy(self, jobs, records):
        """Write a v1 (no 'rooms') data file."""
        with open(be.DATA_FILE, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "jobs": jobs, "records": records}, fh)

    def _read_disk(self):
        with open(be.DATA_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)


class ModelTests(_TempDataFile):
    def test_new_fields_and_room_dataclass(self):
        self.assertEqual(Job().project_manager, "")
        self.assertEqual(Job().building_address, "")
        self.assertEqual(Job().site_name, "")
        self.assertEqual(Job().floor, "")
        self.assertEqual(ValveCheckout().room_id, "")
        self.assertEqual(Room(job_id="J", name="Lab 1").job_id, "J")

    def test_old_job_without_new_fields_loads(self):
        self._write_legacy(
            [{"id": "J1", "job_number": "100", "job_name": "Acme"}],
            [],
        )
        store = CheckoutStore()
        job = store.get_job("J1")
        self.assertEqual(job.job_number, "100")
        self.assertEqual(job.project_manager, "")   # defaulted
        self.assertEqual(job.building_address, "")


class MigrationTests(_TempDataFile):
    def _legacy_one_job(self):
        self._write_legacy(
            [{"id": "J1", "job_number": "100", "job_name": "Acme"}],
            [
                {"id": "R1", "job_id": "J1", "valve_tag": "V1", "location_room": "Lab 314"},
                {"id": "R2", "job_id": "J1", "valve_tag": "V2", "location_room": "Lab 314"},
                {"id": "R3", "job_id": "J1", "valve_tag": "V3", "location_room": "Mech 2"},
                {"id": "R4", "job_id": "J1", "valve_tag": "V4", "location_room": ""},  # -> Unassigned
            ],
        )

    def test_migration_creates_rooms_and_assigns(self):
        self._legacy_one_job()
        store = CheckoutStore()
        rooms = store.rooms_for_job("J1")
        names = sorted(rm.name for rm in rooms)
        self.assertEqual(names, ["Lab 314", "Mech 2", "Unassigned"])
        # every record got a room_id
        for rid in ("R1", "R2", "R3", "R4"):
            self.assertTrue(store.get(rid).room_id, f"{rid} not assigned a room")
        # V1 and V2 share the same room; V4 is in Unassigned
        self.assertEqual(store.get("R1").room_id, store.get("R2").room_id)
        unassigned = next(rm for rm in rooms if rm.name == "Unassigned")
        self.assertEqual(store.get("R4").room_id, unassigned.id)
        # records_for_room returns the right valves
        lab = next(rm for rm in rooms if rm.name == "Lab 314")
        self.assertEqual([r.valve_tag for r in store.records_for_room(lab.id)], ["V1", "V2"])

    def test_migration_persists_v2_and_backup(self):
        self._legacy_one_job()
        CheckoutStore()
        disk = self._read_disk()
        self.assertEqual(disk["version"], 2)
        self.assertIn("rooms", disk)
        self.assertEqual(len(disk["rooms"]), 3)
        # original file was backed up once
        self.assertTrue(os.path.exists(be.DATA_FILE + ".pre-rooms.bak"))

    def test_migration_idempotent(self):
        self._legacy_one_job()
        CheckoutStore()                      # first load migrates
        store2 = CheckoutStore()             # second load: already migrated
        self.assertEqual(len(store2.rooms_for_job("J1")), 3)  # no extra rooms
        # all records still have a room_id, none re-orphaned
        self.assertTrue(all(r.room_id for r in store2.records_for_job("J1")))

    def test_migration_dedupes_dirty_text(self):
        self._write_legacy(
            [{"id": "J1", "job_number": "100", "job_name": "Acme"}],
            [
                {"id": "R1", "job_id": "J1", "valve_tag": "V1", "location_room": "Lab 314"},
                {"id": "R2", "job_id": "J1", "valve_tag": "V2", "location_room": "lab 314 "},
                {"id": "R3", "job_id": "J1", "valve_tag": "V3", "location_room": "LAB 314"},
            ],
        )
        store = CheckoutStore()
        self.assertEqual(len(store.rooms_for_job("J1")), 1)  # all one room
        self.assertEqual(len({store.get(r).room_id for r in ("R1", "R2", "R3")}), 1)


class RoomCrudTests(_TempDataFile):
    def _store_with_job(self):
        store = CheckoutStore()
        store.add_job(Job(id="J1", job_number="100", job_name="Acme"))
        return store

    def test_add_get_update_room(self):
        store = self._store_with_job()
        store.add_room(Room(id="RM1", job_id="J1", name="Lab 1"))
        self.assertEqual(store.get_room("RM1").name, "Lab 1")
        store.update_room(Room(id="RM1", job_id="J1", name="Lab 1A"))
        self.assertEqual(store.get_room("RM1").name, "Lab 1A")
        # survives reload
        store2 = CheckoutStore()
        self.assertEqual(store2.get_room("RM1").name, "Lab 1A")

    def test_delete_room_cascades_records(self):
        store = self._store_with_job()
        store.add_room(Room(id="RM1", job_id="J1", name="Lab 1"))
        store.add(ValveCheckout(id="V1", job_id="J1", room_id="RM1", valve_tag="V1"))
        store.add(ValveCheckout(id="V2", job_id="J1", room_id="RM1", valve_tag="V2"))
        store.delete_room("RM1")
        self.assertIsNone(store.get_room("RM1"))
        self.assertIsNone(store.get("V1"))   # cascaded
        self.assertIsNone(store.get("V2"))

    def test_delete_job_cascades_rooms_and_records(self):
        store = self._store_with_job()
        store.add_room(Room(id="RM1", job_id="J1", name="Lab 1"))
        store.add(ValveCheckout(id="V1", job_id="J1", room_id="RM1", valve_tag="V1"))
        store.delete_job("J1")
        self.assertIsNone(store.get_job("J1"))
        self.assertEqual(store.rooms_for_job("J1"), [])
        self.assertIsNone(store.get("V1"))

    def test_rooms_for_job_sorted(self):
        store = self._store_with_job()
        store.add_room(Room(job_id="J1", name="Zebra"))
        store.add_room(Room(job_id="J1", name="alpha"))
        self.assertEqual([rm.name for rm in store.rooms_for_job("J1")], ["alpha", "Zebra"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
