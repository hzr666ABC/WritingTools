"""Encrypted final-Prompt favorites with lightweight version history."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone

from secure_storage import protect_secret, unprotect_secret


class PromptLibraryStore:
    FORMAT_VERSION = 1
    MAX_FILE_BYTES = 5_000_000
    MAX_ENTRIES = 300
    MAX_VERSIONS = 20

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _clean_entry(item):
        if not isinstance(item, dict):
            return None
        entry_id = str(item.get("id") or "").strip()[:80]
        title = str(item.get("title") or "").strip()[:160]
        versions = []
        for version in item.get("versions") or []:
            if not isinstance(version, dict):
                continue
            prompt = str(version.get("prompt") or "").strip()[:200_000]
            if prompt:
                versions.append({"prompt": prompt, "saved_at": str(version.get("saved_at") or "")[:40]})
        if not entry_id or not title or not versions:
            return None
        return {
            "id": entry_id,
            "title": title,
            "tags": [str(tag).strip()[:50] for tag in (item.get("tags") or []) if str(tag).strip()][:20],
            "preset_id": str(item.get("preset_id") or "")[:80],
            "created_at": str(item.get("created_at") or "")[:40],
            "updated_at": str(item.get("updated_at") or "")[:40],
            "versions": versions[-PromptLibraryStore.MAX_VERSIONS :],
        }

    def _read(self):
        if not os.path.isfile(self.path):
            return []
        try:
            if os.path.getsize(self.path) > self.MAX_FILE_BYTES:
                return []
            with open(self.path, "r", encoding="utf-8") as handle:
                envelope = json.load(handle)
            payload = json.loads(unprotect_secret(envelope.get("payload", "")))
        except (OSError, UnicodeError, ValueError, TypeError):
            return []
        if not isinstance(payload, dict) or payload.get("schema_version") != self.FORMAT_VERSION:
            return []
        result = []
        for item in payload.get("entries") or []:
            clean = self._clean_entry(item)
            if clean:
                result.append(clean)
        return result[-self.MAX_ENTRIES :]

    def list(self, query: str = ""):
        with self._lock:
            items = self._read()
        query = str(query or "").strip().casefold()
        if query:
            items = [item for item in items if query in (item["title"] + " " + " ".join(item["tags"]) + " " + item["versions"][-1]["prompt"]).casefold()]
        return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)

    def save(self, *, title: str, prompt: str, tags=None, preset_id: str = "", entry_id: str = ""):
        title = str(title or "").strip()[:160]
        prompt = str(prompt or "").strip()[:200_000]
        if not title or not prompt:
            raise ValueError("收藏标题和 Prompt 不能为空")
        now = self._now()
        with self._lock:
            items = self._read()
            existing = next((item for item in items if item["id"] == entry_id), None) if entry_id else None
            if existing:
                existing["title"] = title
                existing["tags"] = [str(tag).strip()[:50] for tag in (tags or []) if str(tag).strip()][:20]
                existing["preset_id"] = str(preset_id or "")[:80]
                if existing["versions"][-1]["prompt"] != prompt:
                    existing["versions"].append({"prompt": prompt, "saved_at": now})
                existing["versions"] = existing["versions"][-self.MAX_VERSIONS :]
                existing["updated_at"] = now
                result = existing
            else:
                result = {
                    "id": "prompt-" + uuid.uuid4().hex,
                    "title": title,
                    "tags": [str(tag).strip()[:50] for tag in (tags or []) if str(tag).strip()][:20],
                    "preset_id": str(preset_id or "")[:80],
                    "created_at": now,
                    "updated_at": now,
                    "versions": [{"prompt": prompt, "saved_at": now}],
                }
                items.append(result)
            self._write(items[-self.MAX_ENTRIES :])
            return dict(result)

    def delete(self, entry_id: str) -> bool:
        with self._lock:
            items = self._read()
            kept = [item for item in items if item["id"] != entry_id]
            if len(kept) == len(items):
                return False
            self._write(kept)
            return True

    def _write(self, items):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        raw = json.dumps({"schema_version": self.FORMAT_VERSION, "entries": items}, ensure_ascii=False, separators=(",", ":"))
        envelope = {"version": self.FORMAT_VERSION, "payload": protect_secret(raw)}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=directory, prefix=".prompt-library-", suffix=".tmp", delete=False) as handle:
                temporary = handle.name
                json.dump(envelope, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass


__all__ = ["PromptLibraryStore"]
