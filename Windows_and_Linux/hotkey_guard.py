"""Helpers that keep stateful global hotkeys from firing on stale modifiers."""

from __future__ import annotations

import ctypes
import os


_MODIFIER_ALIASES = {
    "control": "ctrl",
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "meta": "win",
    "windows": "win",
    "win": "win",
}

_MODIFIER_VIRTUAL_KEYS = {
    "ctrl": (0x11,),  # VK_CONTROL
    "alt": (0x12,),  # VK_MENU
    "shift": (0x10,),  # VK_SHIFT
    "win": (0x5B, 0x5C),  # VK_LWIN, VK_RWIN
}


def _hotkey_tokens(hotkey: str) -> tuple[str, ...]:
    return tuple(
        token.strip().casefold().strip("<>")
        for token in str(hotkey or "").split("+")
        if token.strip()
    )


def _windows_key_state(virtual_key: int) -> int | None:
    """Return GetAsyncKeyState or ``None`` when the API is unavailable."""

    try:
        function = ctypes.windll.user32.GetAsyncKeyState
        function.argtypes = [ctypes.c_int]
        function.restype = ctypes.c_short
        return int(function(int(virtual_key)))
    except (AttributeError, OSError):
        return None


def modifier_is_physically_down(
    modifier: str,
    *,
    platform_name: str | None = None,
    state_reader=None,
) -> bool:
    """Check a Windows modifier without relying on pynput's cached state."""

    platform_name = os.name if platform_name is None else platform_name
    normalized = _MODIFIER_ALIASES.get(str(modifier).casefold(), "")
    virtual_keys = _MODIFIER_VIRTUAL_KEYS.get(normalized, ())
    if platform_name != "nt" or not virtual_keys:
        return False

    reader = state_reader or _windows_key_state
    for virtual_key in virtual_keys:
        try:
            state = reader(virtual_key)
        except (AttributeError, OSError):
            state = None
        if state is not None and int(state) & 0x8000:
            return True
    return False


def hotkey_modifiers_are_physically_active(
    hotkey: str,
    *,
    platform_name: str | None = None,
    state_reader=None,
) -> bool:
    """Reject a Windows activation when a required modifier is not held.

    ``pynput.GlobalHotKeys`` keeps an internal pressed-key set. Windows can
    occasionally omit a release event during focus or IME transitions, which
    leaves a modifier in that set and makes a later plain key look like a
    shortcut. GetAsyncKeyState is consulted at activation time to distinguish
    a real chord from that stale state. If the Windows API cannot be queried,
    validation fails open so a platform quirk cannot disable all shortcuts.
    """

    platform_name = os.name if platform_name is None else platform_name
    if platform_name != "nt":
        return True

    required = []
    for token in _hotkey_tokens(hotkey):
        normalized = _MODIFIER_ALIASES.get(token)
        if normalized and normalized not in required:
            required.append(normalized)
    if not required:
        return True

    reader = state_reader or _windows_key_state
    for modifier in required:
        states = []
        for virtual_key in _MODIFIER_VIRTUAL_KEYS[modifier]:
            try:
                states.append(reader(virtual_key))
            except (AttributeError, OSError):
                states.append(None)
        known_states = [state for state in states if state is not None]
        if not known_states:
            continue
        if not any(int(state) & 0x8000 for state in known_states):
            return False
    return True


def send_modified_key(controller, modifier_key, key, *, modifier_already_down=False):
    """Press and release a key chord without releasing a user's modifier.

    The modifier and primary key are released from nested ``finally`` blocks,
    so an exception cannot strand an injected Ctrl key in the pressed state.
    """

    modifier_injected = False
    key_pressed = False
    try:
        if not modifier_already_down:
            controller.press(modifier_key)
            modifier_injected = True
        controller.press(key)
        key_pressed = True
    finally:
        if key_pressed:
            try:
                controller.release(key)
            finally:
                if modifier_injected:
                    controller.release(modifier_key)
        elif modifier_injected:
            controller.release(modifier_key)
