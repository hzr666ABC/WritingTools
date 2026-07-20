"""Pure helpers for settings selection and validation."""

from __future__ import annotations


def provider_index_by_name(provider_names, selected_name: str | None) -> int:
    """Resolve a saved provider name to a stable list index."""

    try:
        return list(provider_names).index(selected_name)
    except ValueError:
        return 0


def find_hotkey_conflict(options: dict | None, shortcut: str) -> str | None:
    """Return the option key that already owns ``shortcut``, if any."""

    normalized = (shortcut or "").strip().lower()
    if not normalized:
        return None
    for option_key, option in (options or {}).items():
        if not isinstance(option, dict):
            continue
        if (option.get("hotkey") or "").strip().lower() == normalized:
            return option_key
    return None
