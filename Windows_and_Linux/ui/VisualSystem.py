"""Shared visual language and restrained motion for Writing Tools.

This module is intentionally presentation-only.  It does not know about
providers, prompts, shortcuts, or request state beyond the visual state names
passed to ``ActivityIndicator``.
"""

from __future__ import annotations

import os

from PySide6 import QtCore, QtGui, QtWidgets


LIGHT = {
    "canvas": "#F4F6FB",
    "surface": "#FFFFFF",
    "surface_alt": "#F8F9FD",
    "surface_soft": "#F1F3F9",
    "text": "#171A2B",
    "text_soft": "#4F5870",
    "muted": "#667086",
    "border": "#E2E6EF",
    "border_strong": "#D2D8E5",
    "accent": "#695CF6",
    "accent_hover": "#584BE5",
    "accent_pressed": "#493DCB",
    "accent_soft": "#EEEBFF",
    "accent_text": "#4135B8",
    "cyan": "#4AC7D4",
    "success": "#1D9A78",
    "danger": "#C9405B",
    "danger_soft": "#FFF0F3",
}

DARK = {
    "canvas": "#11131A",
    "surface": "#191C26",
    "surface_alt": "#202431",
    "surface_soft": "#272B38",
    "text": "#F5F6FB",
    "text_soft": "#C9CFDE",
    "muted": "#969FB5",
    "border": "#303647",
    "border_strong": "#41495D",
    "accent": "#897DFF",
    "accent_hover": "#9A90FF",
    "accent_pressed": "#7366ED",
    "accent_soft": "#302B55",
    "accent_text": "#D8D4FF",
    "cyan": "#50CAD5",
    "success": "#4BC6A3",
    "danger": "#FF8095",
    "danger_soft": "#482B35",
}


def palette(mode: str):
    return DARK if str(mode).casefold() == "dark" else LIGHT


def animations_enabled() -> bool:
    if os.environ.get("WRITINGTOOLS_DISABLE_ANIMATIONS", "").strip() == "1":
        return False
    app = QtWidgets.QApplication.instance()
    if app is None:
        return False
    return QtGui.QGuiApplication.platformName().casefold() not in {"offscreen", "minimal"}


def global_stylesheet(mode: str) -> str:
    p = palette(mode)
    return f"""
        QWidget {{
            color: {p['text']};
            font-family: "Microsoft YaHei UI", "Segoe UI Variable", "Segoe UI";
            font-size: 13px;
        }}
        QToolTip {{
            color: {p['text']};
            background: {p['surface']};
            border: 1px solid {p['border']};
            border-radius: 7px;
            padding: 6px 8px;
        }}
        QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QComboBox {{
            border: 1px solid {p['border_strong']};
            border-radius: 11px;
            background: {p['surface']};
            color: {p['text']};
            selection-background-color: {p['accent']};
            selection-color: white;
        }}
        QLineEdit, QComboBox {{
            min-height: 36px;
            padding: 2px 11px;
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
        QTextBrowser:focus, QComboBox:focus {{
            border: 1px solid {p['accent']};
        }}
        QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {{
            background: {p['surface_soft']};
            color: {p['muted']};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QComboBox QAbstractItemView {{
            border: 1px solid {p['border']};
            border-radius: 9px;
            background: {p['surface']};
            selection-background-color: {p['accent_soft']};
            selection-color: {p['accent_text']};
            padding: 5px;
            outline: none;
        }}
        QGroupBox {{
            border: 1px solid {p['border']};
            border-radius: 12px;
            margin-top: 10px;
            padding-top: 10px;
            background: {p['surface_alt']};
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 5px;
            color: {p['text_soft']};
        }}
        QTabWidget::pane {{
            border: 1px solid {p['border']};
            border-radius: 12px;
            background: {p['surface']};
            top: -1px;
        }}
        QTabBar::tab {{
            min-height: 34px;
            padding: 2px 14px;
            margin-right: 5px;
            border: none;
            border-radius: 9px;
            background: transparent;
            color: {p['muted']};
        }}
        QTabBar::tab:hover {{ background: {p['surface_soft']}; color: {p['text']}; }}
        QTabBar::tab:selected {{
            background: {p['accent_soft']};
            color: {p['accent_text']};
            font-weight: 650;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 9px;
            margin: 3px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {p['border_strong']};
            min-height: 28px;
            border-radius: 4px;
            margin: 1px 2px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QMenu {{
            background: {p['surface']};
            border: 1px solid {p['border']};
            border-radius: 10px;
            padding: 6px;
        }}
        QMenu::item {{ padding: 7px 18px; border-radius: 7px; }}
        QMenu::item:selected {{ background: {p['accent_soft']}; color: {p['accent_text']}; }}
    """


def button_style(mode: str, *, primary=False, danger=False, compact=False) -> str:
    p = palette(mode)
    if primary:
        background = (
            f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {p['accent']},stop:1 #7B70FA)"
        )
        hover = p["accent_hover"]
        pressed = p["accent_pressed"]
        foreground = "#FFFFFF"
        border = "transparent"
    elif danger:
        background = p["danger_soft"]
        hover = "#FFE3E9" if mode != "dark" else "#59323E"
        pressed = "#FFD6DE" if mode != "dark" else "#643744"
        foreground = p["danger"]
        border = p["danger_soft"]
    else:
        background = p["surface_alt"]
        hover = p["accent_soft"]
        pressed = p["surface_soft"]
        foreground = p["text_soft"]
        border = p["border"]
    min_height = 32 if compact else 38
    horizontal = 11 if compact else 15
    return f"""
        QPushButton {{
            min-height: {min_height}px;
            padding: 2px {horizontal}px;
            border: 1px solid {border};
            border-radius: {9 if compact else 11}px;
            background: {background};
            color: {foreground};
            font-size: {12 if compact else 13}px;
            font-weight: 620;
        }}
        QPushButton:hover {{ background: {hover}; border-color: {p['accent'] if not primary else hover}; }}
        QPushButton:pressed {{ background: {pressed}; }}
        QPushButton:focus {{
            border: 2px solid {p['accent']};
            padding-left: {max(1, horizontal - 1)}px;
            padding-right: {max(1, horizontal - 1)}px;
        }}
        QPushButton:disabled {{
            background: {p['surface_soft']};
            border-color: {p['border']};
            color: {p['muted']};
        }}
    """


def editor_style(mode: str, *, prominent=False) -> str:
    p = palette(mode)
    radius = 16 if prominent else 13
    padding = 17 if prominent else 13
    return f"""
        QPlainTextEdit, QTextEdit, QTextBrowser {{
            border: 1px solid {p['border_strong']};
            border-radius: {radius}px;
            padding: {padding}px;
            background: {p['surface']};
            color: {p['text']};
            selection-background-color: {p['accent']};
            font-family: "Microsoft YaHei UI", "Segoe UI Variable", "Segoe UI";
            font-size: {14 if prominent else 13}px;
            line-height: 1.5;
        }}
        QPlainTextEdit:focus, QTextEdit:focus, QTextBrowser:focus {{
            border: 1px solid {p['accent']};
            background: {p['surface']};
        }}
    """


def card_style(mode: str, object_name: str = "premiumCard") -> str:
    p = palette(mode)
    return f"""
        QWidget#{object_name} {{
            background: {p['surface']};
            border: 1px solid {p['border']};
            border-radius: 15px;
        }}
    """


class MotionController(QtCore.QObject):
    """Keeps presentation animations alive and cleans them up safely."""

    def __init__(self, owner: QtWidgets.QWidget):
        super().__init__(owner)
        self.owner = owner
        self._animations: list[QtCore.QAbstractAnimation] = []
        self._window_revealed = False
        owner.installEventFilter(self)

    def eventFilter(self, watched, event):
        owner = getattr(self, "owner", None)
        if owner is not None and watched is owner and event.type() == QtCore.QEvent.Type.Show:
            if not getattr(self, "_window_revealed", False):
                self._window_revealed = True
                if animations_enabled() and not (
                    owner.isMaximized() or owner.isFullScreen()
                ):
                    owner.setWindowOpacity(0.0)
                QtCore.QTimer.singleShot(0, self.reveal_window)
        return super().eventFilter(watched, event)

    def _track(self, animation: QtCore.QAbstractAnimation):
        self._animations.append(animation)

        def cleanup():
            if animation in self._animations:
                self._animations.remove(animation)

        animation.finished.connect(cleanup)
        animation.start()
        return animation

    def reveal_window(self, *, distance=12, duration=220):
        if (
            not animations_enabled()
            or not self.owner.isVisible()
            or self.owner.isMaximized()
            or self.owner.isFullScreen()
        ):
            self.owner.setWindowOpacity(1.0)
            return
        end_position = self.owner.pos()
        start_position = end_position + QtCore.QPoint(0, max(0, int(distance)))
        self.owner.setWindowOpacity(0.0)
        self.owner.move(start_position)
        group = QtCore.QParallelAnimationGroup(self)
        opacity = QtCore.QPropertyAnimation(self.owner, b"windowOpacity", group)
        opacity.setStartValue(0.0)
        opacity.setEndValue(1.0)
        position = QtCore.QPropertyAnimation(self.owner, b"pos", group)
        position.setStartValue(start_position)
        position.setEndValue(end_position)
        for animation in (opacity, position):
            animation.setDuration(int(duration))
            animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        group.finished.connect(lambda: self.owner.move(end_position))
        self._track(group)

    def reveal_widget(self, widget: QtWidgets.QWidget, *, duration=180, delay=0):
        if widget is None or not animations_enabled():
            return

        def start():
            if widget is None or not widget.isVisible():
                return
            effect = QtWidgets.QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)
            animation = QtCore.QPropertyAnimation(effect, b"opacity", self)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setDuration(int(duration))
            animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

            def finish():
                if widget is not None and widget.graphicsEffect() is effect:
                    widget.setGraphicsEffect(None)

            animation.finished.connect(finish)
            self._track(animation)

        QtCore.QTimer.singleShot(max(0, int(delay)), start)

    def stagger(self, widgets, *, interval=24, duration=150):
        for index, widget in enumerate(tuple(widgets or ())):
            self.reveal_widget(widget, duration=duration, delay=index * interval)

    def transition(self, stack: QtWidgets.QStackedWidget, index: int):
        if stack.currentIndex() == index:
            return
        stack.setCurrentIndex(index)
        self.reveal_widget(stack.currentWidget(), duration=190)


class _HoverShadowFilter(QtCore.QObject):
    def __init__(self, widget, mode: str, strong=False):
        super().__init__(widget)
        self.widget = widget
        p = palette(mode)
        self.effect = QtWidgets.QGraphicsDropShadowEffect(widget)
        shadow = QtGui.QColor(p["accent"])
        shadow.setAlpha(88 if strong else 53)
        self.effect.setColor(shadow)
        self.effect.setBlurRadius(8 if strong else 4)
        self.effect.setOffset(0, 1)
        widget.setGraphicsEffect(self.effect)
        widget.installEventFilter(self)
        self._group = None

    def _animate(self, blur, y_offset, duration=150):
        if not animations_enabled():
            self.effect.setBlurRadius(blur)
            self.effect.setOffset(0, y_offset)
            return
        if self._group is not None:
            self._group.stop()
        self._group = QtCore.QParallelAnimationGroup(self)
        blur_animation = QtCore.QPropertyAnimation(
            self.effect, b"blurRadius", self._group
        )
        blur_animation.setStartValue(self.effect.blurRadius())
        blur_animation.setEndValue(float(blur))
        offset_animation = QtCore.QPropertyAnimation(
            self.effect, b"offset", self._group
        )
        offset_animation.setStartValue(self.effect.offset())
        offset_animation.setEndValue(QtCore.QPointF(0, y_offset))
        for animation in (blur_animation, offset_animation):
            animation.setDuration(duration)
            animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._group.start()

    def eventFilter(self, watched, event):
        event_type = event.type()
        if event_type == QtCore.QEvent.Type.Enter:
            self._animate(18, 4)
        elif event_type == QtCore.QEvent.Type.Leave:
            self._animate(7, 1)
        elif event_type == QtCore.QEvent.Type.MouseButtonPress:
            self._animate(4, 0, 90)
        elif event_type == QtCore.QEvent.Type.MouseButtonRelease:
            self._animate(16, 3, 120)
        return super().eventFilter(watched, event)


def install_button_motion(button: QtWidgets.QAbstractButton, mode: str, *, strong=False):
    if button is None or getattr(button, "_premium_hover_filter", None) is not None:
        return
    button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    button._premium_hover_filter = _HoverShadowFilter(button, mode, strong=strong)


class _FocusGlowFilter(QtCore.QObject):
    def __init__(self, widget, mode: str):
        super().__init__(widget)
        self.widget = widget
        self.effect = QtWidgets.QGraphicsDropShadowEffect(widget)
        glow = QtGui.QColor(palette(mode)["accent"])
        glow.setAlpha(85)
        self.effect.setColor(glow)
        self.effect.setBlurRadius(0)
        self.effect.setOffset(0, 0)
        widget.setGraphicsEffect(self.effect)
        widget.installEventFilter(self)
        self.animation = QtCore.QPropertyAnimation(self.effect, b"blurRadius", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

    def eventFilter(self, watched, event):
        if event.type() in {QtCore.QEvent.Type.FocusIn, QtCore.QEvent.Type.FocusOut}:
            self.animation.stop()
            self.animation.setStartValue(self.effect.blurRadius())
            self.animation.setEndValue(
                18.0 if event.type() == QtCore.QEvent.Type.FocusIn else 0.0
            )
            if animations_enabled():
                self.animation.start()
            else:
                self.effect.setBlurRadius(float(self.animation.endValue()))
        return super().eventFilter(watched, event)


def install_focus_glow(widget: QtWidgets.QWidget, mode: str):
    if widget is None or getattr(widget, "_premium_focus_filter", None) is not None:
        return
    widget._premium_focus_filter = _FocusGlowFilter(widget, mode)


class ActivityIndicator(QtWidgets.QWidget):
    """Small, low-noise state indicator used by generation surfaces."""

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.state = "idle"
        self.phase = 0
        self.setFixedSize(22, 22)
        self.setAccessibleName("状态指示器")
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(32)
        self.timer.timeout.connect(self._advance)

    def set_state(self, state: str):
        state = state if state in {"idle", "busy", "success", "error"} else "idle"
        self.state = state
        if state == "busy" and animations_enabled():
            self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def _advance(self):
        self.phase = (self.phase + 9) % 360
        self.update()

    def paintEvent(self, event):
        del event
        p = palette(self.mode)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = QtCore.QRectF(3.5, 3.5, 15, 15)
        if self.state == "busy":
            painter.setPen(QtGui.QPen(QtGui.QColor(p["border_strong"]), 2.1))
            painter.drawArc(rect, 0, 360 * 16)
            painter.setPen(
                QtGui.QPen(
                    QtGui.QColor(p["accent"]),
                    2.3,
                    QtCore.Qt.PenStyle.SolidLine,
                    QtCore.Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawArc(rect, int((90 - self.phase) * 16), -105 * 16)
        elif self.state == "success":
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(p["success"]))
            painter.drawEllipse(rect)
            painter.setPen(
                QtGui.QPen(
                    QtGui.QColor("#FFFFFF"),
                    1.8,
                    QtCore.Qt.PenStyle.SolidLine,
                    QtCore.Qt.PenCapStyle.RoundCap,
                    QtCore.Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.drawPolyline(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(7, 11),
                        QtCore.QPointF(10, 14),
                        QtCore.QPointF(16, 8),
                    ]
                )
            )
        elif self.state == "error":
            painter.setPen(QtGui.QPen(QtGui.QColor(p["danger"]), 2.0))
            painter.drawEllipse(rect)
            painter.drawLine(QtCore.QPointF(8, 8), QtCore.QPointF(14, 14))
            painter.drawLine(QtCore.QPointF(14, 8), QtCore.QPointF(8, 14))
        else:
            painter.setPen(QtGui.QPen(QtGui.QColor(p["border_strong"]), 2.0))
            painter.drawEllipse(rect)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(p["accent"]))
            painter.drawEllipse(QtCore.QPointF(11, 11), 2.1, 2.1)


__all__ = [
    "ActivityIndicator",
    "MotionController",
    "animations_enabled",
    "button_style",
    "card_style",
    "editor_style",
    "global_stylesheet",
    "install_button_motion",
    "install_focus_glow",
    "palette",
]
