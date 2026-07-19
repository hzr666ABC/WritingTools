"""Pure workflow helpers for the quick-action UI."""

from __future__ import annotations


def resolve_remembered_option(config: dict | None, options: dict | None) -> str | None:
    """Return the preset to execute directly, or ``None`` to show the popup."""

    config = config or {}
    options = options or {}
    if not config.get("remember_last_action", False):
        return None
    option = config.get("last_used_option", "Proofread")
    if option == "Custom" or option not in options:
        return None
    return option


def bottom_right_position(screen_geometry, popup_width: int, popup_height: int, margin: int = 20):
    """Calculate a popup origin inside a screen's available work area."""

    x = screen_geometry.right() - popup_width - margin + 1
    y = screen_geometry.bottom() - popup_height - margin + 1
    return x, y


def number_key_to_index(key_number: int, option_count: int) -> int | None:
    """Map a visible 1-based number shortcut to a zero-based preset index."""

    index = key_number - 1
    if 0 <= index < option_count:
        return index
    return None
