"""Private device identity, sessions and durable request receipts in SQLite."""
import hashlib
from contextlib import contextmanager
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path

from .errors import GadgetError


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        self.path = self.directory / "state.sqlite3"
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, token_hash TEXT UNIQUE,
                personas TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sessions(device TEXT, persona TEXT, backend TEXT, session TEXT,
                PRIMARY KEY(device,persona,backend));
            CREATE TABLE IF NOT EXISTS receipts(device TEXT, operation TEXT, hash TEXT, status TEXT,
                result TEXT, PRIMARY KEY(device,operation));
            CREATE TABLE IF NOT EXISTS reviews(device TEXT, operation TEXT, revision TEXT, status TEXT,
                PRIMARY KEY(device,operation));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at REAL, device TEXT,
                operation TEXT, event TEXT);
            """)
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def cached(self, device, operation, digest):
        with self.connect() as db:
            row = db.execute("SELECT * FROM receipts WHERE device=? AND operation=?", (device, operation)).fetchone()
        if row:
            if row["hash"] != digest:
                raise GadgetError("operation_conflict", "Operation ID was used with a different request.", 409)
            if row["status"] != "done":
                raise GadgetError("operation_uncertain", "Turn is running or uncertain; review its outcome before a new operation.", 409)
            return json.loads(row["result"])
        return None

    def enroll(self, device, personas):
        token = "gdev_" + secrets.token_urlsafe(32)
        with self.connect() as db:
            try:
                db.execute("INSERT INTO devices(id,token_hash,personas) VALUES(?,?,?)",
                           (device, hashlib.sha256(token.encode()).hexdigest(), json.dumps(personas)))
            except sqlite3.IntegrityError as exc:
                raise GadgetError("device_exists", "Device already exists; rotate or revoke it explicitly.", 409) from exc
        return token

    def rotate(self, device):
        token = "gdev_" + secrets.token_urlsafe(32)
        with self.connect() as db:
            result = db.execute("UPDATE devices SET token_hash=?,revoked=0 WHERE id=?",
                                (hashlib.sha256(token.encode()).hexdigest(), device))
            if result.rowcount != 1:
                raise GadgetError("unknown_device", "Device not found.", 404)
        return token

    def revoke(self, device):
        with self.connect() as db:
            db.execute("UPDATE devices SET revoked=1 WHERE id=?", (device,))

    def authenticate(self, token):
        if not isinstance(token, str) or not token.startswith("gdev_"):
            raise GadgetError("device_unauthorized", "A device credential is required.", 401)
        with self.connect() as db:
            row = db.execute("SELECT id,personas FROM devices WHERE token_hash=? AND revoked=0",
                             (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row:
            raise GadgetError("device_unauthorized", "Device credential is invalid or revoked.", 401)
        return {"id": row["id"], "personas": json.loads(row["personas"])}

    def reserve(self, device, operation, digest):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM receipts WHERE device=? AND operation=?", (device, operation)).fetchone()
            if row:
                if row["hash"] != digest:
                    raise GadgetError("operation_conflict", "Operation ID was used with a different request.", 409)
                if row["status"] != "done":
                    raise GadgetError("operation_uncertain", "Turn is running or uncertain; review its outcome before a new operation.", 409)
                return json.loads(row["result"])
            db.execute("INSERT INTO receipts VALUES(?,?,?,'running',NULL)", (device, operation, digest))
        return None

    def finish(self, device, operation, result):
        with self.connect() as db:
            db.execute("UPDATE receipts SET status='done',result=? WHERE device=? AND operation=?",
                       (json.dumps(result, allow_nan=False), device, operation))
            db.execute("INSERT INTO audit(at,device,operation,event) VALUES(?,?,?,'turn_completed')",
                       (time.time(), device, operation))

    def fail(self, device, operation):
        with self.connect() as db:
            db.execute("UPDATE receipts SET status='uncertain' WHERE device=? AND operation=?", (device, operation))
            db.execute("INSERT INTO audit(at,device,operation,event) VALUES(?,?,?,'turn_uncertain')",
                       (time.time(), device, operation))

    def session(self, device, persona, backend):
        with self.connect() as db:
            row = db.execute("SELECT session FROM sessions WHERE device=? AND persona=? AND backend=?",
                             (device, persona, backend)).fetchone()
        return row["session"] if row else None

    def receipt(self, device, operation):
        with self.connect() as db:
            row = db.execute("SELECT status,result FROM receipts WHERE device=? AND operation=?", (device, operation)).fetchone()
        if not row:
            raise GadgetError("unknown_operation", "Operation has not reached this bridge.", 404)
        return {"operationId": operation, "status": row["status"],
                **({"result": json.loads(row["result"])} if row["result"] else {})}

    def save_session(self, device, persona, backend, session):
        if session:
            with self.connect() as db:
                db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?)", (device, persona, backend, session))

    def review_fixture(self, device, operation, revision, decision):
        if decision not in ("approve", "decline"):
            raise GadgetError("invalid_review", "Choose approve or decline.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT result FROM receipts WHERE device=? AND operation=? AND status='done'",
                             (device, operation)).fetchone()
            if not row:
                raise GadgetError("unknown_operation", "Completed turn not found.", 404)
            result = json.loads(row["result"])
            if result.get("mode") != "fixture":
                raise GadgetError("live_review_required", "Protected live actions require the authenticated Persona app.", 403)
            if result.get("revision") != revision:
                raise GadgetError("review_revision_changed", "Review the current complete proposal before approving.", 409)
            old = db.execute("SELECT revision,status FROM reviews WHERE device=? AND operation=?", (device, operation)).fetchone()
            if old and (old["revision"] != revision or old["status"] != decision):
                raise GadgetError("review_conflict", "This proposal already has a different decision.", 409)
            db.execute("INSERT OR IGNORE INTO reviews VALUES(?,?,?,?)", (device, operation, revision, decision))
        # An approval in the SDK demo never files, buys, dispatches, publishes or transfers money.
        return {"status": "simulated_approval" if decision == "approve" else "declined",
                "mode": "fixture", "revision": revision, "externalEffects": [],
                "note": "Review recorded for synthetic demonstration only; no live effect executed."}
