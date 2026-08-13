"""Opt-in encrypted preferences for the Prompt Workbench.

Only a small allow-list of structured fields is accepted. Raw inputs, full
prompts, and conversation messages have no representation in this format.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone

from secure_storage import protect_secret, unprotect_secret
from sharpinput_workflow import PREFERENCE_KEYS


class PromptPreferenceStore:
    FORMAT_VERSION = 1
    MAX_FILE_BYTES = 512_000
    MAX_EVENTS = 10

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()

    @staticmethod
    def _normalize(preferences: dict | None) -> dict[str, str]:
        normalized = {}
        for key, value in (preferences or {}).items():
            if key not in PREFERENCE_KEYS:
                continue
            text = str(value or "").strip()[:2_000]
            if text:
                normalized[key] = text
        return normalized

    def _read_data(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            if os.path.getsize(self.path) > self.MAX_FILE_BYTES:
                return {}
            with open(self.path, "r", encoding="utf-8") as handle:
                envelope = json.load(handle)
            if not isinstance(envelope, dict):
                return {}
            payload = unprotect_secret(envelope.get("payload", ""))
            data = json.loads(payload)
        except (OSError, UnicodeError, ValueError, TypeError):
            return {}
        if not isinstance(data, dict) or data.get("schema_version") != self.FORMAT_VERSION:
            return {}
        consent = data.get("consent")
        if not isinstance(consent, dict) or consent.get("enabled") is not True:
            return {}
        return data

    def load(self, *, enabled: bool) -> dict[str, str]:
        """Return preferences only after the caller confirms opt-in."""

        if not enabled:
            return {}
        with self._lock:
            return self._normalize(self._read_data().get("preferences"))

    def save(self, preferences: dict | None, *, enabled: bool) -> bool:
        """Persist an encrypted allow-listed snapshot when consent is enabled."""

        if not enabled:
            return False
        normalized = self._normalize(preferences)
        with self._lock:
            previous = self._read_data()
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            previous_preferences = self._normalize(previous.get("preferences"))
            changed_keys = sorted(
                key
                for key in PREFERENCE_KEYS
                if previous_preferences.get(key) != normalized.get(key)
            )
            events = previous.get("events") if isinstance(previous.get("events"), list) else []
            if changed_keys:
                events.append({"timestamp": now, "changed_keys": changed_keys})
            data = {
                "schema_version": self.FORMAT_VERSION,
                "consent": {
                    "enabled": True,
                    "granted_at": (
                        previous.get("consent", {}).get("granted_at")
                        if isinstance(previous.get("consent"), dict)
                        else None
                    )
                    or now,
                },
                "preferences": normalized,
                "events": events[-self.MAX_EVENTS :],
                "updated_at": now,
            }
            self._save_encrypted(data)
        return True

    def _save_encrypted(self, data: dict):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        envelope = {
            "version": self.FORMAT_VERSION,
            "payload": protect_secret(payload),
        }
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=directory,
                prefix=".prompt-preferences-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = handle.name
                json.dump(envelope, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
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

    def clear(self) -> bool:
        with self._lock:
            try:
                os.remove(self.path)
                return True
            except FileNotFoundError:
                return False

    def has_data(self) -> bool:
        return os.path.isfile(self.path)


__all__ = ["PromptPreferenceStore"]
