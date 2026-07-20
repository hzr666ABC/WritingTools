"""Encrypted local generation history with lightweight version tracking."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone

from secure_storage import protect_secret, unprotect_secret


class HistoryStore:
    FORMAT_VERSION = 1
    MAX_FILE_BYTES = 25_000_000

    def __init__(self, path: str, max_entries: int = 100):
        self.path = path
        self.max_entries = max(10, int(max_entries))
        self._lock = threading.RLock()

    @staticmethod
    def _group_id(option: str, original: str) -> str:
        payload = f"{option}\0{original}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:20]

    def _load_raw(self) -> dict:
        if not os.path.exists(self.path):
            return {"version": self.FORMAT_VERSION, "entries": []}
        try:
            if os.path.getsize(self.path) > self.MAX_FILE_BYTES:
                return {"version": self.FORMAT_VERSION, "entries": []}
        except OSError:
            return {"version": self.FORMAT_VERSION, "entries": []}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {"version": self.FORMAT_VERSION, "entries": []}
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            return {"version": self.FORMAT_VERSION, "entries": []}
        return data

    def _save_raw(self, data: dict):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=directory,
                prefix=".writing-tools-history-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = handle.name
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            if os.name != "nt":
                os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    @staticmethod
    def _decode_entry(raw: dict) -> dict:
        entry = dict(raw)
        for key in ("original", "result"):
            try:
                entry[key] = unprotect_secret(entry.get(key, ""))
            except Exception:
                entry[key] = "<无法解密>"
        return entry

    def add_entry(self, *, option: str, original: str, result: str,
                  provider: str = "", model: str = "", status: str = "preview") -> dict:
        with self._lock:
            data = self._load_raw()
            group_id = self._group_id(option, original)
            version = 1 + sum(1 for item in data["entries"] if item.get("group_id") == group_id)
            raw = {
                "id": uuid.uuid4().hex,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "option": option,
                "provider": provider,
                "model": model,
                "status": status,
                "group_id": group_id,
                "version": version,
                "original": protect_secret(original),
                "result": protect_secret(result),
            }
            data["entries"].insert(0, raw)
            data["entries"] = data["entries"][:self.max_entries]
            self._save_raw(data)
            return self._decode_entry(raw)

    def list_entries(self) -> list[dict]:
        with self._lock:
            return [self._decode_entry(item) for item in self._load_raw()["entries"]]

    def update_status(self, entry_id: str, status: str) -> bool:
        with self._lock:
            data = self._load_raw()
            for item in data["entries"]:
                if item.get("id") == entry_id:
                    item["status"] = status
                    item["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    self._save_raw(data)
                    return True
        return False

    def delete_entry(self, entry_id: str) -> bool:
        with self._lock:
            data = self._load_raw()
            before = len(data["entries"])
            data["entries"] = [item for item in data["entries"] if item.get("id") != entry_id]
            if len(data["entries"]) == before:
                return False
            self._save_raw(data)
            return True

    def clear(self):
        with self._lock:
            self._save_raw({"version": self.FORMAT_VERSION, "entries": []})
