"""Mode/config-pinned, fsynced completed-call journal for development pilots."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode("utf-8")).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_text(path, text):
    """Replace only a derived artifact, never the append-only journal."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".pilot-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


class PilotCheckpoint:
    """Reject legacy/mixed runs and corruption instead of silently regenerating."""

    ARTIFACTS = ("dataset.json", "settings.json", "calls.jsonl", "records.json", "records.jsonl",
                 "summary.json", "eval_rows.json", "report.md")

    def __init__(self, directory, identity, dataset, settings):
        self.directory = Path(directory)
        self.identity = identity
        self.cache = {}
        self.head = "0" * 64
        self.count = 0
        self.lock = None
        self.was_complete = False
        exists = self.directory.exists()
        if exists and not (self.directory / "manifest.json").is_file():
            raise ValueError("Existing output lacks a pinned manifest; preserve it and use a new directory")
        if not exists:
            self.directory.mkdir(parents=True, exist_ok=False)
        try:
            self.lock = (self.directory / ".writer.lock").open("a")
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if exists:
                self.manifest = json.loads((self.directory / "manifest.json").read_text())
                if self.manifest.get("identity") != identity:
                    raise ValueError("Resume mode, settings, dataset, runtime or source mismatch")
                if (self.manifest.get("schema_version") != 1
                        or self.manifest.get("mode") != "order_certificate_development_pilot"
                        or self.manifest.get("evidence") != identity["evidence"]
                        or self.manifest.get("model_calls") is not (not identity["mock"])
                        or self.manifest.get("confirmatory") is not False
                        or self.manifest.get("status") not in ("running", "interrupted", "complete")):
                    raise ValueError("Invalid pilot manifest state or evidence")
                for name, value in (("dataset.json", dataset), ("settings.json", settings)):
                    if json.loads((self.directory / name).read_text()) != value:
                        raise ValueError(f"Pinned {name} changed")
                self._read()
                if self.manifest.get("status") == "complete":
                    hashes = self.manifest.get("artifact_sha256")
                    if not isinstance(hashes, dict) or set(hashes) != set(self.ARTIFACTS):
                        raise ValueError("Missing completed artifact hashes")
                    if self.manifest.get("journal_head") != self.head or self.manifest.get("journal_entries") != self.count:
                        raise ValueError("Completed manifest differs from journal")
                    for name, expected in hashes.items():
                        if file_digest(self.directory / name) != expected:
                            raise ValueError(f"Completed artifact changed: {name}")
                    self.was_complete = True
            else:
                self.manifest = {
                    "schema_version": 1, "mode": "order_certificate_development_pilot",
                    "identity": identity, "evidence": identity["evidence"],
                    "model_calls": not identity["mock"], "status": "running",
                    "publication_review_required": True, "confirmatory": False,
                    "model_revision_verified": False, "journal_head": self.head,
                }
                atomic_json(self.directory / "dataset.json", dataset)
                atomic_json(self.directory / "settings.json", settings)
                (self.directory / "calls.jsonl").touch(exist_ok=False)
            if not self.was_complete:
                self.status("running")
        except BaseException:
            self.close()
            raise

    def _read(self):
        path = self.directory / "calls.jsonl"
        if not path.is_file():
            raise ValueError("Missing completed-call journal")
        anchors = {self.head}
        for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
            if not line.endswith("\n"):
                raise ValueError("Torn journal tail; preserve it for manual review")
            entry = json.loads(line)
            body = {key: value for key, value in entry.items() if key != "sha256"}
            if entry.get("sha256") != digest(body) or body.get("previous") != self.head or body.get("sequence") != self.count:
                raise ValueError("Journal checksum, order or chain mismatch")
            if body.get("evidence") != self.identity["evidence"] or body.get("kind") not in ("generation", "execution", "record"):
                raise ValueError("Journal evidence or kind mismatch")
            key = (body["kind"], *body["key"])
            if key in self.cache:
                raise ValueError("Duplicate journal key")
            self.cache[key] = body["value"]
            self.head = entry["sha256"]
            self.count += 1
            anchors.add(self.head)
        # An interruption after fsync but before the manifest update may leave
        # a valid tail. Its entire chain is checked; no malformed line is dropped.
        if self.manifest.get("journal_head") not in anchors:
            raise ValueError("Manifest head is absent from the journal chain")

    def get(self, kind, key):
        return self.cache.get((kind, *key))

    def save(self, kind, key, value):
        cached = self.get(kind, key)
        if cached is not None:
            if cached != value:
                raise ValueError("Existing journal entry differs from reconstructed output")
            return
        body = {"sequence": self.count, "previous": self.head, "kind": kind,
                "key": list(key), "evidence": self.identity["evidence"], "value": value}
        entry = {**body, "sha256": digest(body)}
        with (self.directory / "calls.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(encoded(entry) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.cache[(kind, *key)] = value
        self.head = entry["sha256"]
        self.count += 1
        self.status("running")
        if kind == "record":
            self.snapshot()

    def snapshot(self):
        rows = [value for key, value in sorted(self.cache.items()) if key[0] == "record"]
        atomic_json(self.directory / "records.json", rows)
        atomic_text(self.directory / "records.jsonl", "".join(encoded(row) + "\n" for row in rows))

    def status(self, status, **fields):
        self.manifest.update(status=status, journal_head=self.head, journal_entries=self.count, **fields)
        atomic_json(self.directory / "manifest.json", self.manifest)

    def complete(self):
        self.status("complete", artifact_sha256={name: file_digest(self.directory / name) for name in self.ARTIFACTS})

    def close(self):
        if self.lock is not None:
            self.lock.close()
            self.lock = None
