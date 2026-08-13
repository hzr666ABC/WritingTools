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


def find_named_hotkey_conflict(
    shortcut: str,
    *,
    main_shortcut: str = "",
    prompt_shortcut: str = "",
    options: dict | None = None,
    ignore: str = "",
) -> str | None:
    """Return the stable owner name for a global hotkey collision."""

    normalized = (shortcut or "").strip().lower()
    ignored = (ignore or "").strip().lower()
    if not normalized:
        return None
    owners = (
        ("main", main_shortcut),
        ("prompt", prompt_shortcut),
    )
    for owner, value in owners:
        if owner == ignored:
            continue
        if (value or "").strip().lower() == normalized:
            return owner
    option = find_hotkey_conflict(options, normalized)
    if option and ignored != f"option:{option}".lower():
        return f"option:{option}"
    return None
