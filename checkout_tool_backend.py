"""
checkout_tool_backend.py — Data and storage logic for Phoenix Valve Checkout Tool
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


def _app_data_path(filename: str) -> str:
    """Path to user data in %APPDATA%\\ATS Inc\\Phoenix Valve Checkout Tool\\."""
    base = Path(os.environ.get("APPDATA", Path.home())) / "ATS Inc" / "Phoenix Valve Checkout Tool"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / filename)


DATA_FILE = _app_data_path("data.json")


# ── Job container ──────────────────────────────────────────────────────────────

@dataclass
class Job:
    """A job / project container that holds one or more valve checkout records."""
    id:         str  = field(default_factory=lambda: str(uuid.uuid4()))
    job_number: str  = ""
    job_name:   str  = ""
    archived:   bool = False


# ── Checkout record ────────────────────────────────────────────────────────────

@dataclass
class ValveCheckout:
    """One complete valve checkout record, mirroring the Phoenix Celeris checkout sheet."""
    id:     str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""   # parent Job.id

    # ── Header fields ──────────────────────────────────────────────────────────
    valve_tag:      str = ""
    project:        str = ""
    ats_job_number: str = ""
    date:           str = ""   # ISO yyyy-MM-dd
    technician:     str = ""
    description:    str = ""
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
        self._records: list[ValveCheckout] = []
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self._jobs    = [Job(**j)            for j in raw.get("jobs",    [])]
            self._records = [ValveCheckout(**r)  for r in raw.get("records", [])]
        except (OSError, ValueError, KeyError, TypeError):
            self._jobs    = []
            self._records = []

    def _save(self) -> None:
        with open(DATA_FILE, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "jobs":    [asdict(j) for j in self._jobs],
                    "records": [asdict(r) for r in self._records],
                },
                fh,
                indent=2,
            )

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
        """Delete a job and all its checkout records."""
        self._jobs    = [j for j in self._jobs    if j.id     != job_id]
        self._records = [r for r in self._records if r.job_id != job_id]
        self._save()

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
