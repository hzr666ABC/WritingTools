import os
import sys

from PySide6 import QtGui, QtCore, QtWidgets
from PySide6.QtGui import QImage, QPixmap

import darkdetect
from ui.VisualSystem import MotionController, global_stylesheet, palette
colorMode = 'dark' if darkdetect.isDark() else 'light'

class UIUtils:
    @classmethod
    def clear_layout(cls, layout):
        """
        Clear the layout of all widgets.
        """
        while ((child := layout.takeAt(0)) != None):
            child_layout = child.layout()
            child_widget = child.widget()
            if child_layout:
                cls.clear_layout(child_layout)
                child_layout.deleteLater()
            elif child_widget:
                child_widget.hide()
                child_widget.setParent(None)
                child_widget.deleteLater()

    @classmethod
    def resize_and_round_image(cls, image, image_size = 100, rounding_amount = 50):
        image = image.scaledToWidth(image_size)
        clipPath = QtGui.QPainterPath()
        clipPath.addRoundedRect(0, 0, image_size, image_size, rounding_amount, rounding_amount)
        target = QImage(image_size, image_size, QImage.Format_ARGB32)
        target.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(target)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setClipPath(clipPath)
        painter.drawImage(0, 0, image)
        painter.end()
        targetPixmap = QPixmap.fromImage(target)
        return targetPixmap

    @classmethod
    def setup_window_and_layout(cls, base: QtWidgets.QWidget):
        # Set the window icon
        icon_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
        if os.path.exists(icon_path): base.setWindowIcon(QtGui.QIcon(icon_path))
        base.setStyleSheet(global_stylesheet(colorMode))
        base.motion = MotionController(base)
        main_layout = QtWidgets.QVBoxLayout(base)
        main_layout.setContentsMargins(0, 0, 0, 0)
        app = getattr(base, 'app', None)
        config = getattr(app, 'config', {}) or {}
        base.background = ThemeBackground(
            base,
            config.get('theme', 'plain'),
            custom_background_path=config.get('custom_background_path', ''),
        )
        main_layout.addWidget(base.background)


class ThemeBackground(QtWidgets.QWidget):
    """
    A custom widget that creates a background for the application based on the selected theme.
    """
    def __init__(self, parent=None, theme='gradient', is_popup=False,
                 border_radius=0, custom_background_path=''):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.theme = theme
        self.is_popup = is_popup
        self.border_radius = border_radius
        self.custom_background_path = custom_background_path

    def paintEvent(self, event):
        """
        Override the paint event to draw the background based on the selected theme.
        """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.border_radius, self.border_radius)
        painter.setClipPath(path)

        if self.theme == 'custom' and os.path.isfile(self.custom_background_path):
            background_image = QtGui.QPixmap(self.custom_background_path)
            if not background_image.isNull():
                scaled = background_image.scaled(
                    self.size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                offset_x = max(0, (scaled.width() - self.width()) // 2)
                offset_y = max(0, (scaled.height() - self.height()) // 2)
                source = QtCore.QRect(offset_x, offset_y, self.width(), self.height())
                painter.drawPixmap(self.rect(), scaled, source)
                overlay = QtGui.QColor(24, 27, 36, 188) if colorMode == 'dark' else QtGui.QColor(248, 249, 255, 210)
                painter.fillRect(self.rect(), overlay)
            else:
                self._paint_plain_background(painter)
        elif self.theme == 'gradient':
            if self.is_popup:
                background_image = QtGui.QPixmap(os.path.join(os.path.dirname(sys.argv[0]), 'background_popup_dark.png' if colorMode == 'dark' else 'background_popup.png'))
            else:
                background_image = QtGui.QPixmap(os.path.join(os.path.dirname(sys.argv[0]), 'background_dark.png' if colorMode == 'dark' else 'background.png'))
            painter.drawPixmap(self.rect(), background_image)
        else:
            self._paint_plain_background(painter)

        # A hairline border keeps translucent windows crisp on bright and dark
        # desktop backgrounds without turning the surface into a heavy card.
        border = QtGui.QColor("#FFFFFF")
        border.setAlpha(40 if colorMode == "dark" else 216)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(border, 1))
        inset = QtCore.QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.drawRoundedRect(inset, self.border_radius, self.border_radius)

    def _paint_plain_background(self, painter):
        p = palette(colorMode)
        rect = QtCore.QRectF(0, 0, self.width(), self.height())
        base = QtGui.QLinearGradient(0, 0, self.width(), self.height())
        if colorMode == "dark":
            base.setColorAt(0, QtGui.QColor("#1A1D28"))
            base.setColorAt(0.55, QtGui.QColor(p["canvas"]))
            base.setColorAt(1, QtGui.QColor("#141720"))
        else:
            base.setColorAt(0, QtGui.QColor("#FCFDFF"))
            base.setColorAt(0.62, QtGui.QColor(p["canvas"]))
            base.setColorAt(1, QtGui.QColor("#F1F4FA"))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(base)
        painter.drawRoundedRect(rect, self.border_radius, self.border_radius)

        accent_glow = QtGui.QRadialGradient(
            QtCore.QPointF(self.width() * 0.86, self.height() * 0.02),
            max(self.width() * 0.72, 180),
        )
        accent = QtGui.QColor(p["accent"])
        accent.setAlpha(30 if colorMode == "dark" else 22)
        accent_glow.setColorAt(0, accent)
        accent_glow.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
        painter.setBrush(accent_glow)
        painter.drawRect(rect)

        cyan_glow = QtGui.QRadialGradient(
            QtCore.QPointF(self.width() * 0.04, self.height() * 0.96),
            max(self.width() * 0.58, 160),
        )
        cyan = QtGui.QColor(p["cyan"])
        cyan.setAlpha(14 if colorMode == "dark" else 11)
        cyan_glow.setColorAt(0, cyan)
        cyan_glow.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
        painter.setBrush(cyan_glow)
        painter.drawRect(rect)
