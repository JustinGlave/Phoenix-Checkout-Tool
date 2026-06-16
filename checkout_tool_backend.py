"""
checkout_tool_backend.py — Data and storage logic for Phoenix Valve Checkout Tool
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from phoenix_commons.paths import user_data_dir as _commons_user_data_dir


def _app_data_path(filename: str) -> str:
    """Path to user data in %APPDATA%\\ATS Inc\\Phoenix Valve Checkout Tool\\.

    Phase 3B retrofit: delegates to ``phoenix_commons.paths.user_data_dir``.
    Behavior preserved byte-for-byte — commons creates the directory if
    missing (matches pre-retrofit ``base.mkdir(parents=True, exist_ok=True)``).
    Verified pre-retrofit: ``_app_data_path('data.json')`` produces the same
    string both before and after this change.

    Kept as a local function (not removed) so existing callers
    (``DATA_FILE = _app_data_path("data.json")`` + ``checkout_export.py``)
    continue working unchanged.
    """
    return str(_commons_user_data_dir("Phoenix Valve Checkout Tool", "ATS Inc") / filename)


DATA_FILE = _app_data_path("data.json")


# ── Job container ──────────────────────────────────────────────────────────────

@dataclass
class Job:
    """A job / project container — the sole source of project-level metadata.

    job_number / job_name double as Project Number / Project Name (reused, not
    duplicated). project_manager and building_address were added for the project
    metadata block (Startup Report Cover sheet).
    """
    id:               str  = field(default_factory=lambda: str(uuid.uuid4()))
    job_number:       str  = ""    # Project Number
    job_name:         str  = ""    # Project Name
    project_manager:  str  = ""
    building_address: str  = ""
    site_name:        str  = ""
    floor:            str  = ""
    archived:         bool = False


# ── Room ─────────────────────────────────────────────────────────────────────

@dataclass
class Room:
    """A room within a job; groups the valve checkouts performed in that room."""
    id:     str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""   # parent Job.id
    name:   str = ""


# ── Checkout record ────────────────────────────────────────────────────────────

@dataclass
class ValveCheckout:
    """One complete valve checkout record, mirroring the Phoenix Celeris checkout sheet."""
    id:      str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id:  str = ""   # parent Job.id
    room_id: str = ""   # parent Room.id (3-level model)

    # ── Header fields ──────────────────────────────────────────────────────────
    valve_tag:      str = ""
    project:        str = ""
    ats_job_number: str = ""
    date:           str = ""   # ISO yyyy-MM-dd
    technician:     str = ""
    description:    str = ""
    location_room:  str = ""   # RETIRED: superseded by the valve's Room; kept so legacy
                               # data loads and seeds room names during migration
    model:          str = "CELERIS 2"
    valve_type:     str = "Fume Hood"
    pass_fail:      str = ""   # "Pass" | "Fail" | ""
    emer_min:       str = ""
    valve_min_sp:   str = ""
    valve_max_sp:   str = ""

    # ── Wiring checkboxes ──────────────────────────────────────────────────────
    # Keys: "p_{i}_i" / "p_{i}_w"  → Phoenix wiring row i, Install / Wired
    #       "b_{i}_i" / "b_{i}_w"  → Black Box wiring row i, Install / Wired
    wiring: dict = field(default_factory=dict)

    # ── Sash sensor ────────────────────────────────────────────────────────────
    sash_sensor_mounted: bool = False

    # ── Configuration ──────────────────────────────────────────────────────────
    # Keys: "{row_key}_cfm", "{row_key}_notes"
    config: dict = field(default_factory=dict)

    # ── Verification ───────────────────────────────────────────────────────────
    # Keys: "{row_key}_result", "{row_key}_notes"
    verification: dict = field(default_factory=dict)

    # ── Free-form notes ────────────────────────────────────────────────────────
    notes: str = ""


# ── Store ──────────────────────────────────────────────────────────────────────

class CheckoutStore:
    """Persists Job containers and ValveCheckout records as JSON."""

    def __init__(self) -> None:
        self._jobs:    list[Job]           = []
        self._rooms:   list[Room]          = []
        self._records: list[ValveCheckout] = []
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────────

    _DATA_VERSION = 2   # v2 introduced the Room level (Job -> Room -> ValveCheckout)

    def _load(self) -> None:
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            return

        jobs: list[Job] = []
        for j in raw.get("jobs", []):
            try:
                jobs.append(Job(**{k: v for k, v in j.items() if k in Job.__dataclass_fields__}))
            except Exception:
                pass  # skip individual bad records, preserve the rest

        rooms: list[Room] = []
        for rm in raw.get("rooms", []):
            try:
                rooms.append(Room(**{k: v for k, v in rm.items() if k in Room.__dataclass_fields__}))
            except Exception:
                pass

        records: list[ValveCheckout] = []
        for r in raw.get("records", []):
            try:
                records.append(ValveCheckout(**{k: v for k, v in r.items()
                                                if k in ValveCheckout.__dataclass_fields__}))
            except Exception:
                pass

        self._jobs    = jobs
        self._rooms   = rooms
        self._records = records

        # One-time, idempotent migration to the Room model: assign a Room to any
        # checkout that lacks one (legacy 2-level data). Room names are seeded from
        # the retired location_room field, defaulting to "Unassigned". The original
        # file is backed up once before the migrated structure is written.
        if self._migrate_orphans_to_rooms():
            self._backup_once(DATA_FILE + ".pre-rooms.bak")
            self._save()

    def _save(self) -> None:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "version": self._DATA_VERSION,
                    "jobs":    [asdict(j) for j in self._jobs],
                    "rooms":   [asdict(rm) for rm in self._rooms],
                    "records": [asdict(r) for r in self._records],
                },
                fh,
                indent=2,
            )
        os.replace(tmp, DATA_FILE)  # atomic — avoids corruption on crash

    # ── Migration (legacy 2-level -> 3-level Room model) ─────────────────────────

    @staticmethod
    def _norm(name: str) -> str:
        return (name or "").strip().casefold()

    def _find_or_create_room(self, job_id: str, name: str) -> Room:
        """Return an existing room (matched case-insensitively by name within the
        job) or create one. Avoids duplicate-room fragmentation from dirty text."""
        key = self._norm(name)
        for rm in self._rooms:
            if rm.job_id == job_id and self._norm(rm.name) == key:
                return rm
        room = Room(job_id=job_id, name=(name or "").strip() or "Unassigned")
        self._rooms.append(room)
        return room

    def _migrate_orphans_to_rooms(self) -> bool:
        """Assign a room_id to any checkout that lacks one. Idempotent — records
        that already have a room_id are untouched. Returns True if anything changed."""
        changed = False
        for rec in self._records:
            if rec.room_id:
                continue
            name = (rec.location_room or "").strip() or "Unassigned"
            rec.room_id = self._find_or_create_room(rec.job_id, name).id
            changed = True
        return changed

    @staticmethod
    def _backup_once(path: str) -> None:
        """Copy the current data file to `path` once (never overwrite an existing
        backup), preserving the original pre-migration state."""
        try:
            if os.path.exists(DATA_FILE) and not os.path.exists(path):
                shutil.copy2(DATA_FILE, path)
        except OSError:
            pass

    # ── Job API ────────────────────────────────────────────────────────────────

    def all_jobs(self) -> list[Job]:
        """Active (non-archived) jobs sorted by job_number then job_name."""
        return sorted(
            [j for j in self._jobs if not j.archived],
            key=lambda j: (j.job_number.lower(), j.job_name.lower()),
        )

    def archived_jobs(self) -> list[Job]:
        """Archived jobs sorted by job_number then job_name."""
        return sorted(
            [j for j in self._jobs if j.archived],
            key=lambda j: (j.job_number.lower(), j.job_name.lower()),
        )

    def get_job(self, job_id: str) -> Optional[Job]:
        return next((j for j in self._jobs if j.id == job_id), None)

    def add_job(self, job: Job) -> None:
        self._jobs.append(job)
        self._save()

    def update_job(self, job: Job) -> None:
        for idx, existing in enumerate(self._jobs):
            if existing.id == job.id:
                self._jobs[idx] = job
                self._save()
                return

    def archive_job(self, job_id: str) -> None:
        """Mark a job as archived (hidden from active view)."""
        job = self.get_job(job_id)
        if job:
            job.archived = True
            self._save()

    def restore_job(self, job_id: str) -> None:
        """Restore an archived job back to active."""
        job = self.get_job(job_id)
        if job:
            job.archived = False
            self._save()

    def delete_job(self, job_id: str) -> None:
        """Delete a job and all its rooms and checkout records."""
        self._jobs    = [j  for j  in self._jobs    if j.id      != job_id]
        self._rooms   = [rm for rm in self._rooms   if rm.job_id != job_id]
        self._records = [r  for r  in self._records if r.job_id  != job_id]
        self._save()

    # ── Room API ─────────────────────────────────────────────────────────────────

    def rooms_for_job(self, job_id: str) -> list[Room]:
        """Rooms in a job, sorted by name."""
        return sorted([rm for rm in self._rooms if rm.job_id == job_id],
                      key=lambda rm: rm.name.lower())

    def get_room(self, room_id: str) -> Optional[Room]:
        return next((rm for rm in self._rooms if rm.id == room_id), None)

    def add_room(self, room: Room) -> None:
        self._rooms.append(room)
        self._save()

    def update_room(self, room: Room) -> None:
        for idx, existing in enumerate(self._rooms):
            if existing.id == room.id:
                self._rooms[idx] = room
                self._save()
                return

    def delete_room(self, room_id: str) -> None:
        """Delete a room and all its checkout records (cascade)."""
        self._rooms   = [rm for rm in self._rooms   if rm.id      != room_id]
        self._records = [r  for r  in self._records if r.room_id  != room_id]
        self._save()

    def records_for_room(self, room_id: str) -> list[ValveCheckout]:
        """All checkouts in a room, sorted alphabetically by valve_tag."""
        recs = [r for r in self._records if r.room_id == room_id]
        return sorted(recs, key=lambda r: r.valve_tag.lower())

    # ── Record API ─────────────────────────────────────────────────────────────

    def records_for_job(self, job_id: str) -> list[ValveCheckout]:
        """All checkouts for a job, sorted alphabetically by valve_tag."""
        recs = [r for r in self._records if r.job_id == job_id]
        return sorted(recs, key=lambda r: r.valve_tag.lower())

    def get(self, record_id: str) -> Optional[ValveCheckout]:
        return next((r for r in self._records if r.id == record_id), None)

    def add(self, record: ValveCheckout) -> None:
        self._records.append(record)
        self._save()

    def update(self, record: ValveCheckout) -> None:
        for idx, existing in enumerate(self._records):
            if existing.id == record.id:
                self._records[idx] = record
                self._save()
                return

    def delete(self, record_id: str) -> None:
        self._records = [r for r in self._records if r.id != record_id]
        self._save()
