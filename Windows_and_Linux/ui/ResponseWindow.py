import logging
import os
import sys

import markdown2
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QScrollArea

from ui.UIUtils import UIUtils, colorMode
from ui.VisualSystem import (
    ActivityIndicator,
    button_style,
    card_style,
    editor_style,
    install_button_motion,
    install_focus_glow,
    palette,
)

_ = lambda x: x

class MarkdownTextBrowser(QtWidgets.QTextBrowser):
    """Enhanced text browser for displaying Markdown content with improved sizing"""
    
    def __init__(self, parent=None, is_user_message=False):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.zoom_factor = 1.2
        self.base_font_size = 14
        self.is_user_message = is_user_message
        
        # Critical: Remove scrollbars to prevent extra space
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Set size policies to prevent unwanted expansion
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum
        )
        
        self._apply_zoom()
        
    def _apply_zoom(self):
        new_size = int(self.base_font_size * self.zoom_factor)
        p = palette(colorMode)
        self.document().setDefaultStyleSheet(f"""
            body {{ color: {p['text']}; font-family: 'Microsoft YaHei UI', 'Segoe UI';
                font-size: {new_size}px; line-height: 1.5; }}
            h1, h2, h3, h4 {{ color: {p['text']}; margin-top: 14px; margin-bottom: 8px; }}
            p {{ margin-top: 4px; margin-bottom: 9px; }}
            ul, ol {{ margin-top: 5px; margin-bottom: 9px; }}
            blockquote {{ color: {p['text_soft']}; border-left: 3px solid {p['accent']};
                margin-left: 4px; padding-left: 12px; }}
            code {{ color: {p['accent_text']}; background-color: {p['accent_soft']};
                padding: 2px 4px; }}
            pre {{ color: {p['text']}; background-color: {p['surface_soft']};
                border: 1px solid {p['border']}; padding: 10px; }}
            table {{ border-collapse: collapse; margin-top: 10px; margin-bottom: 10px; }}
            th {{ color: {p['text']}; background-color: {p['surface_soft']};
                border: 1px solid {p['border_strong']}; padding: 7px 10px; }}
            td {{ color: {p['text_soft']}; border: 1px solid {p['border_strong']};
                padding: 7px 10px; }}
            a {{ color: {p['accent_text']}; text-decoration: none; }}
        """)
        
        # Updated stylesheet with table styling
        self.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {(p['accent_soft'] if self.is_user_message else p['surface'])};
                color: {(p['accent_text'] if self.is_user_message else p['text'])};
                border: 1px solid {(p['accent'] if self.is_user_message else p['border'])};
                border-radius: 14px;
                padding: 13px 15px;
                margin: 0px;
                font-size: {new_size}px;
                line-height: 1.45;
                width: 100%;
            }}

            /* Table styles */
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 10px 0;
            }}
            
            th, td {{
                border: 1px solid {p['border_strong']};
                padding: 8px;
                text-align: left;
            }}
            
            th {{
                background-color: {p['surface_soft']};
                font-weight: bold;
            }}
            
            tr:nth-child(even) {{
                background-color: {p['surface_alt']};
            }}
            
            tr:hover {{
                background-color: {p['accent_soft']};
            }}
        """)

    def set_markdown_text(self, text):
        self.setHtml(markdown2.markdown(str(text or ""), extras=['tables', 'strike']))
        self._update_size()
        
    def _update_size(self):
        # Calculate correct document width
        available_width = self.viewport().width() - 16  # Account for padding
        self.document().setTextWidth(available_width)
        
        # Get precise content height
        doc_size = self.document().size()
        content_height = doc_size.height()
        
        # Add minimal padding for content
        new_height = int(content_height + 16)  # Reduced total padding
        
        if self.minimumHeight() != new_height:
            self.setMinimumHeight(new_height)
            self.setMaximumHeight(new_height)  # Force fixed height
            
            # Update scroll area if needed
            scroll_area = self.get_scroll_area()
            if scroll_area:
                scroll_area.update_content_height()
                
    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            # Get the main response window
            parent = self.parent()
            while parent and not isinstance(parent, ResponseWindow):
                parent = parent.parent()
                
            if parent:
                if delta > 0:
                    parent.zoom_all_messages('in')
                else:
                    parent.zoom_all_messages('out')
                event.accept()
        else:
            # Pass wheel events to parent for scrolling
            if self.parent():
                self.parent().wheelEvent(event)
            
    def zoom_in(self):
        old_factor = self.zoom_factor
        self.zoom_factor = min(3.0, self.zoom_factor * 1.1)
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()
        
    def zoom_out(self):
        old_factor = self.zoom_factor
        self.zoom_factor = max(0.5, self.zoom_factor / 1.1)
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()
        
    def reset_zoom(self):
        old_factor = self.zoom_factor
        self.zoom_factor = 1.2  # Reset to default zoom
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()
    
    def get_scroll_area(self):
        """Find the parent ChatContentScrollArea"""
        parent = self.parent()
        while parent:
            if isinstance(parent, ChatContentScrollArea):
                return parent
            parent = parent.parent()
        return None
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_size()


class ChatContentScrollArea(QScrollArea):
    """Improved scrollable container for chat messages with dynamic sizing and proper spacing"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.content_widget = None
        self.layout = None
        self.setup_ui()
        
    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Main container widget with explicit size policy
        self.content_widget = QtWidgets.QWidget()
        self.content_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding
        )
        self.setWidget(self.content_widget)
        
        # Main layout with improved spacing
        self.layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.layout.setSpacing(12)
        self.layout.setContentsMargins(4, 10, 4, 10)
        self.layout.addStretch()
        
        p = palette(colorMode)
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {p['border_strong']};
                min-height: 20px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

    def add_message(self, text, is_user=False):
        # Remove bottom stretch
        self.layout.takeAt(self.layout.count() - 1)
        
        # Create message container with improved width
        msg_container = QtWidgets.QWidget()
        msg_container.setObjectName("messageContainer")
        msg_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum
        )
        
        # Message layout with minimal margins
        msg_layout = QtWidgets.QVBoxLayout(msg_container)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.setSpacing(0)
        
        # Create text display with updated width
        text_display = MarkdownTextBrowser(is_user_message=is_user)
        
        # Enable tables extension in markdown2
        text_display.set_markdown_text(text)
        
        # Calculate proper text display size using full width
        text_display.document().setTextWidth(self.width() - 20)
        doc_size = text_display.document().size()
        text_display.setMinimumHeight(int(doc_size.height() + 16))
        
        msg_layout.addWidget(text_display)
        
        self.layout.addWidget(msg_container)
        self.layout.addStretch()

        owner = self.parent()
        while owner and not isinstance(owner, ResponseWindow):
            owner = owner.parent()
        if owner is not None:
            owner.motion.reveal_widget(msg_container, duration=170)
        
        QtCore.QTimer.singleShot(50, self.post_message_updates)
        
        return text_display

    def post_message_updates(self):
        """Handle updates after adding a message with proper timing"""
        self.scroll_to_bottom()
        if isinstance(self.parent(), ResponseWindow):
            self.parent()._adjust_window_height()

    def update_content_height(self):
        """Recalculate total content height with improved spacing calculation"""
        total_height = 0
        
        # Calculate height of all messages
        for i in range(self.layout.count() - 1):  # Skip stretch item
            item = self.layout.itemAt(i)
            if item and item.widget():
                widget_height = item.widget().sizeHint().height()
                total_height += widget_height
        
        # Add spacing between messages and margins
        total_height += (self.layout.spacing() * (self.layout.count() - 2))  # Message spacing
        total_height += self.layout.contentsMargins().top() + self.layout.contentsMargins().bottom()
        
        # Set minimum height with some padding
        self.content_widget.setMinimumHeight(total_height + 10)
        
        # Update window height if needed
        if isinstance(self.parent(), ResponseWindow):
            self.parent()._adjust_window_height()

    def scroll_to_bottom(self):
        """Smooth scroll to bottom of content"""
        vsb = self.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def resizeEvent(self, event):
        """Handle resize events with improved width calculations"""
        super().resizeEvent(event)
        
        # Update width for all message displays
        available_width = self.width() - 40  # Account for margins
        for i in range(self.layout.count() - 1):  # Skip stretch item
            item = self.layout.itemAt(i)
            if item and item.widget():
                container = item.widget()
                text_display = container.layout().itemAt(0).widget()
                if isinstance(text_display, MarkdownTextBrowser):
                    # Recalculate text width and height
                    text_display.document().setTextWidth(available_width)
                    doc_size = text_display.document().size()
                    text_display.setMinimumHeight(int(doc_size.height() + 20))  # Reduced padding


class ResponseWindow(QtWidgets.QWidget):
    """Enhanced response window with improved sizing and zoom handling"""
    
    def __init__(self, app, title=_("Response"), parent=None):
        super().__init__(parent)
        self.app = app
        self.original_title = title
        self.setWindowTitle(title)
        self.option = title.replace(" Result", "")
        self.selected_text = None
        self.input_field = None
        self.loading_label = None
        self.loading_container = None
        self.loading_indicator = None
        self.chat_area = None
        self.chat_history = []
        self._closed = False
        self._stream_target = ""
        self._stream_rendered = ""
        self._stream_scroll_counter = 0
        self._stream_preview_display = None
        self._stream_timer = QtCore.QTimer(self)
        self._stream_timer.setInterval(18)
        self._stream_timer.timeout.connect(self._type_stream_character)

        # Setup thinking animation with full range of dots
        self.thinking_timer = QtCore.QTimer(self)
        self.thinking_timer.timeout.connect(self.update_thinking_dots)
        self.thinking_dots_state = 0
        self.thinking_dots = ["", ".", "..", "..."]  # Now properly includes all states
        self.thinking_timer.setInterval(300)

        self.init_ui()
        logging.debug('Connecting response signals')
        self.app.followup_response_signal.connect(self.handle_followup_response)
        logging.debug('Response signals connected')

        # Set initial size for "Thinking..." state
        initial_width = 500
        initial_height = 250
        self.resize(initial_width, initial_height)
                
    def init_ui(self):
        # Window setup with enhanced flags
        self.setWindowFlags(QtCore.Qt.WindowType.Window | 
                          QtCore.Qt.WindowType.WindowCloseButtonHint | 
                          QtCore.Qt.WindowType.WindowMinimizeButtonHint |
                          QtCore.Qt.WindowType.WindowMaximizeButtonHint)
        self.setMinimumSize(600, 400)
        
        # Main layout setup
        UIUtils.setup_window_and_layout(self)
        content_layout = QtWidgets.QVBoxLayout(self.background)
        content_layout.setContentsMargins(28, 24, 28, 22)
        content_layout.setSpacing(13)

        # Top bar with zoom controls
        top_bar = QtWidgets.QHBoxLayout()
        
        title_copy = QtWidgets.QVBoxLayout()
        title_copy.setSpacing(0)
        eyebrow = QtWidgets.QLabel("WRITING  RESULT")
        eyebrow.setStyleSheet(
            f"color:{palette(colorMode)['accent']};font-size:9px;font-weight:700;letter-spacing:1.4px;"
        )
        title_label = QtWidgets.QLabel(self.option)
        title_label.setStyleSheet(
            f"font-size:21px;font-weight:700;color:{palette(colorMode)['text']};"
        )
        title_copy.addWidget(eyebrow)
        title_copy.addWidget(title_label)
        top_bar.addLayout(title_copy)
        
        top_bar.addStretch()

        # Zoom label with matched size
        zoom_label = QtWidgets.QLabel("阅读缩放")
        zoom_label.setStyleSheet(f"""
            color: {palette(colorMode)['muted']};
            font-size: 11px;
            margin-right: 5px;
        """)
        top_bar.addWidget(zoom_label)
        
        # Enhanced zoom controls with swapped order
        zoom_controls = [
            ('plus', '放大', lambda: self.zoom_all_messages('in')),
            ('minus', '缩小', lambda: self.zoom_all_messages('out')),
            ('reset', '恢复默认缩放', lambda: self.zoom_all_messages('reset'))
        ]
            
        for icon, tooltip, action in zoom_controls:
            btn = QtWidgets.QPushButton()
            btn.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.argv[0]), 'icons', icon + ('_dark' if colorMode == 'dark' else '_light') + '.png')))
            btn.setStyleSheet(self.get_button_style())
            btn.setToolTip(tooltip)
            btn.clicked.connect(action)
            btn.setFixedSize(30, 30)
            top_bar.addWidget(btn)
            
        content_layout.addLayout(top_bar)

        divider = QtWidgets.QFrame()
        divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        divider.setStyleSheet(
            f"color:{palette(colorMode)['border']};background:{palette(colorMode)['border']};max-height:1px;"
        )
        content_layout.addWidget(divider)

        copy_bar = QtWidgets.QHBoxLayout()
        copy_hint = QtWidgets.QLabel("结果支持 Markdown · 选中文字可保留格式复制")
        copy_hint.setStyleSheet(
            f"color:{palette(colorMode)['muted']};font-size:11px;"
        )
        copy_bar.addWidget(copy_hint)
        copy_bar.addStretch()
        
        copy_md_btn = QtWidgets.QPushButton("复制 Markdown")
        copy_md_btn.setStyleSheet(self.get_button_style())
        copy_md_btn.clicked.connect(self.copy_first_response)  # Updated to only copy first response
        copy_bar.addWidget(copy_md_btn)
        content_layout.addLayout(copy_bar)

        # Loading indicator
        loading_container = QtWidgets.QWidget()
        loading_layout = QtWidgets.QHBoxLayout(loading_container)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        
        self.loading_label = QtWidgets.QLabel(_("Thinking"))
        self.loading_label.setStyleSheet(f"""
            QLabel {{
                color: {palette(colorMode)['text_soft']};
                font-size: 13px;
                padding: 4px;
            }}
        """)
        self.loading_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        
        loading_inner_container = QtWidgets.QWidget()
        loading_inner_container.setObjectName("loadingSurface")
        loading_inner_container.setStyleSheet(card_style(colorMode, "loadingSurface"))
        loading_inner_container.setFixedWidth(210)
        loading_inner_layout = QtWidgets.QHBoxLayout(loading_inner_container)
        loading_inner_layout.setContentsMargins(0, 0, 0, 0)
        loading_inner_layout.setContentsMargins(14, 10, 14, 10)
        self.loading_indicator = ActivityIndicator(colorMode)
        self.loading_indicator.set_state("busy")
        loading_inner_layout.addWidget(self.loading_indicator)
        loading_inner_layout.addWidget(self.loading_label)
        
        loading_layout.addStretch()
        loading_layout.addWidget(loading_inner_container)
        loading_layout.addStretch()
        
        content_layout.addWidget(loading_container)
        self.loading_container = loading_container
        
        # Start thinking animation
        self.start_thinking_animation(initial=True)
        
        # Enhanced chat area with full width
        self.chat_area = ChatContentScrollArea()
        content_layout.addWidget(self.chat_area)
        
        # Input area with enhanced styling
        bottom_bar = QtWidgets.QHBoxLayout()
        
        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText("继续追问…")
        self.input_field.setMinimumHeight(44)
        install_focus_glow(self.input_field, colorMode)
        self.input_field.returnPressed.connect(self.send_message)
        bottom_bar.addWidget(self.input_field)
        
        send_button = QtWidgets.QPushButton()
        send_button.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'send' + ('_dark' if colorMode == 'dark' else '_light') + '.png')))
        send_button.setStyleSheet(button_style(colorMode, primary=True))
        send_button.setFixedSize(44, 44)
        install_button_motion(send_button, colorMode, strong=True)
        send_button.clicked.connect(self.send_message)
        bottom_bar.addWidget(send_button)
        
        content_layout.addLayout(bottom_bar)

    # Method to get first response text
    def get_first_response_text(self):
        """Get the first model response text from chat history"""
        try:
            # Check chat history exists
            if not self.chat_history:
                return None
                
            # Find first assistant message
            for msg in self.chat_history:
                if msg["role"] == "assistant":
                    return msg["content"]
                    
            return None
        except Exception as e:
            logging.error(f"Error getting first response: {e}")
            return None

    def copy_first_response(self):
        """Copy only the first model response as Markdown"""
        response_text = self.get_first_response_text()
        if response_text:
            QtWidgets.QApplication.clipboard().setText(response_text)
            self.loading_label.setText("已复制 Markdown")
            self.loading_label.show()
            if self.loading_indicator is not None:
                self.loading_indicator.set_state("success")
                self.loading_indicator.show()
            self.loading_container.show()
            QtCore.QTimer.singleShot(1100, self.loading_container.hide)

    def get_button_style(self):
        return button_style(colorMode, compact=True)

    def update_thinking_dots(self):
        """Update the thinking animation dots with proper cycling"""
        self.thinking_dots_state = (self.thinking_dots_state + 1) % len(self.thinking_dots)
        dots = self.thinking_dots[self.thinking_dots_state]
        
        if self.loading_label.isVisible():
            self.loading_label.setText(_("Thinking")+f"{dots}")
        else:
            self.input_field.setPlaceholderText(_("Thinking")+f"{dots}")
    
    def start_thinking_animation(self, initial=False):
        """Start the thinking animation for either initial load or follow-up questions"""
        self.thinking_dots_state = 0
        
        if initial:
            self.loading_label.setText(_("Thinking"))
            self.loading_label.setVisible(True)
            self.loading_container.setVisible(True)
        else:
            self.input_field.setPlaceholderText("正在生成…")
            self.loading_container.setVisible(False)
            
        self.thinking_timer.start()
        if self.loading_indicator is not None:
            self.loading_indicator.set_state("busy")

    def stop_thinking_animation(self):
        """Stop the thinking animation"""
        self.thinking_timer.stop()
        self.loading_container.hide()
        self.loading_label.hide()
        self.input_field.setPlaceholderText("继续追问…")
        self.input_field.setEnabled(True)
        if self.loading_indicator is not None:
            self.loading_indicator.set_state("success")
        
        # Force layout update
        if self.layout():
            self.layout().invalidate()
            self.layout().activate()

    def zoom_all_messages(self, action='in'):
        """Apply zoom action to all messages in the chat"""
        for i in range(self.chat_area.layout.count() - 1):  # Skip stretch item
            item = self.chat_area.layout.itemAt(i)
            if item and item.widget():
                text_display = item.widget().layout().itemAt(0).widget()
                if isinstance(text_display, MarkdownTextBrowser):
                    if action == 'in':
                        text_display.zoom_in()
                    elif action == 'out':
                        text_display.zoom_out()
                    else:  # reset
                        text_display.reset_zoom()
        
        # Update layout after zooming
        self.chat_area.update_content_height()
        
    def _adjust_window_height(self):
        """Calculate and set the ideal window height"""
        # Skip adjustment if window already has a size
        if hasattr(self, '_size_initialized'):
            return
                
        try:
            # Get content widget height
            content_height = self.chat_area.content_widget.sizeHint().height()
                
            # Calculate other UI elements height
            ui_elements_height = (
                self.layout().contentsMargins().top() +
                self.layout().contentsMargins().bottom() +
                self.input_field.height() +
                self.layout().spacing() * 5 +
                200  # Increased from 185 for taller default height
            )
                
            # Get screen constraints
            screen = QtWidgets.QApplication.screenAt(self.pos())
            if not screen:
                screen = QtWidgets.QApplication.primaryScreen()
                
            # Calculate maximum available height (85% of screen)
            max_height = int(screen.geometry().height() * 0.85)
                
            # Calculate desired height to show more content initially
            desired_content_height = int(content_height * 0.85)  # Show 85% of content
            desired_total_height = min(
                desired_content_height + ui_elements_height,
                max_height
            )
                
            # Set reasonable minimum height - increased by 10%
            final_height = max(600, desired_total_height)  # Increased from 540
                
            # Set width to 600px
            final_width = 600
                
            # Update both width and height
            self.resize(final_width, final_height)
                
            # Center on screen
            frame_geometry = self.frameGeometry()
            screen_center = screen.geometry().center()
            frame_geometry.moveCenter(screen_center)
            self.move(frame_geometry.topLeft())
                
            # Mark size as initialized
            self._size_initialized = True
                
        except Exception as e:
            logging.error(f"Error adjusting window height: {e}")
            self.resize(600, 600)  # Updated fallback size
            self._size_initialized = True

    @Slot(str)
    def set_text(self, text):
        """Set initial response text with enhanced handling"""
        if not text.strip():
            return
                
        # Always ensure chat history is initialized properly
        self.chat_history = [
            {"role": "user", "content": f"{self.option}: {self.selected_text}"},
            {"role": "assistant", "content": text}  # Add initial response immediately
        ]
        
        self.stop_thinking_animation()
        text_display = getattr(self, '_stream_preview_display', None)
        if text_display is not None:
            self._stream_timer.stop()
            self._stream_target = str(text)
            self._stream_rendered = str(text)
            text_display.set_markdown_text(text)
            self._stream_preview_display = None
        else:
            text_display = self.chat_area.add_message(text)
        
        # Update zoom state
        if isinstance(self.app.config, dict) and 'response_window_zoom' in self.app.config:
            text_display.zoom_factor = self.app.config['response_window_zoom']
            text_display._apply_zoom()
        self.current_text_display = text_display
        
        QtCore.QTimer.singleShot(100, self._adjust_window_height)

    @Slot(str)
    def set_stream_preview(self, text):
        """Queue a partial response and reveal it one character at a time."""
        if self._closed or not str(text or "").strip():
            return
        self.stop_thinking_animation()
        self.input_field.setEnabled(False)
        target = str(text)
        if not target.startswith(self._stream_rendered):
            self._stream_rendered = ""
            if self._stream_preview_display is not None:
                self._stream_preview_display.clear()
        self._stream_target = target
        if self._stream_preview_display is None:
            self._stream_preview_display = self.chat_area.add_message("")
        if not self._stream_rendered:
            self._type_stream_character()
        if not self._stream_timer.isActive():
            self._stream_timer.start()

    def _type_stream_character(self):
        if self._closed or len(self._stream_rendered) >= len(self._stream_target):
            self._stream_timer.stop()
            return
        character = self._stream_target[len(self._stream_rendered)]
        self._stream_rendered += character
        self._stream_preview_display.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        self._stream_preview_display.insertPlainText(character)
        self._stream_scroll_counter += 1
        if self._stream_scroll_counter % 3 == 0 or character == "\n":
            QtCore.QTimer.singleShot(0, self.chat_area.post_message_updates)
        
    @Slot(object)
    def handle_followup_response(self, context):
        """Handle the follow-up response from the AI with improved layout handling"""
        if self._closed or context.get("window") is not self:
            return
        response_text = context.get("response", "")
        if response_text:
            self.loading_label.setVisible(False)
            text_display = self.chat_area.add_message(response_text)
            
            # Maintain consistent zoom level
            if hasattr(self, 'current_text_display'):
                text_display.zoom_factor = self.current_text_display.zoom_factor
                text_display._apply_zoom()
            self.current_text_display = text_display
            
            if len(self.chat_history) > 0 and self.chat_history[-1]["role"] != "assistant":
                self.chat_history.append({
                    "role": "assistant",
                    "content": response_text
                })
        
        self.stop_thinking_animation()
        self.input_field.setEnabled(True)
        
        # Update window height
        QtCore.QTimer.singleShot(100, self._adjust_window_height)
        
    def send_message(self):
        """Send a new message/question"""
        message = self.input_field.text().strip()
        if not message:
            return
            
        self.input_field.setEnabled(False)
        self.input_field.clear()
        
        # Add user message and maintain zoom level
        text_display = self.chat_area.add_message(message, is_user=True)
        if hasattr(self, 'current_text_display'):
            text_display.zoom_factor = self.current_text_display.zoom_factor
            text_display._apply_zoom()
        self.current_text_display = text_display
        
        self.chat_history.append({"role": "user", "content": message})
        self.start_thinking_animation()
        self.app.process_followup_question(self, message)
        
    def copy_as_markdown(self):
        """Copy conversation as Markdown"""
        markdown = ""
        for msg in self.chat_history:
            if msg["role"] == "user":
                markdown += f"**用户**：{msg['content']}\n\n"
            else:
                markdown += f"**AI**：{msg['content']}\n\n"
                
        QtWidgets.QApplication.clipboard().setText(markdown)
        
    def closeEvent(self, event):
        """Handle window close event"""
        self._closed = True
        self._stream_timer.stop()
        self.thinking_timer.stop()
        # Save zoom factor to main config
        if hasattr(self, 'current_text_display'):
            self.app.config['response_window_zoom'] = self.current_text_display.zoom_factor
            self.app.save_config(self.app.config)

        self.chat_history = []
        
        if getattr(self.app, 'current_response_window', None) is self:
            self.app.current_response_window = None
        

        super().closeEvent(event)
