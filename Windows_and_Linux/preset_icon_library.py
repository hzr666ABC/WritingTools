"""Curated, real project icons exposed by the preset editor."""

from __future__ import annotations


PRESET_ICON_CHOICES = (
    ("icons/custom", "灵感"),
    ("icons/magnifying-glass", "校对"),
    ("icons/rewrite", "改写"),
    ("icons/smiley-face", "友好"),
    ("icons/briefcase", "专业"),
    ("icons/concise", "简洁"),
    ("icons/summary", "总结"),
    ("icons/keypoints", "要点"),
    ("icons/table", "表格"),
    ("icons/list", "列表"),
    ("icons/copy", "复制"),
    ("icons/regenerate", "润色"),
)

DEFAULT_PRESET_ICON = "icons/custom"


def normalize_preset_icon(icon_name):
    """Return a selectable icon id, falling back for legacy/invalid values."""

    available = {icon_id for icon_id, _label in PRESET_ICON_CHOICES}
    return icon_name if icon_name in available else DEFAULT_PRESET_ICON
