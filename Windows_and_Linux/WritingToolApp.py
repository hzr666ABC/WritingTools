import gettext
import json
import logging
import os
import signal
import sys
import tempfile
import threading
import time

import darkdetect
import pyperclip
import ui.AboutWindow
import ui.CustomPopupWindow
import ui.DiagnosticsWindow
import ui.HistoryWindow
import ui.OnboardingWindow
import ui.ResponseWindow
import ui.SafeApplyWindow
import ui.SettingsWindow
from aiprovider import GeminiProvider, OllamaProvider, OpenAICompatibleProvider
from history_store import HistoryStore
from pynput import keyboard as pykeyboard

from hotkey_guard import (
    hotkey_modifiers_are_physically_active,
    modifier_is_physically_down,
    send_modified_key,
)
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QLocale, Signal, Slot
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox
from prompting import compose_system_instruction, normalize_options, option_display_name
from quick_action_workflow import (
    bottom_right_position,
    record_trigger,
    resolve_remembered_option,
)
from request_guard import RequestGenerationGuard
from secure_storage import protect_secret, redact_text, unprotect_secret
from text_application import activate_window, capture_foreground_window
from ui.i18n import translate
from update_checker import UpdateChecker

_ = gettext.gettext


class _SelectedTextHolder:
    """
    Carries the result of an async clipboard capture from `_show_popup` to
    `process_option_thread`. The capture thread sets `text` and signals
    `ready` once done.
    """
    __slots__ = ("text", "ready", "request_id", "source_window_handle")

    def __init__(self):
        self.text = ""
        self.ready = threading.Event()
        self.request_id = 0
        self.source_window_handle = None


class WritingToolApp(QtWidgets.QApplication):
    """
    The main application class for Writing Tools.
    """
    generation_result_signal = Signal(object)
    show_message_signal = Signal(str, str)  # a signal for showing message boxes
    hotkey_triggered_signal = Signal()
    followup_response_signal = Signal(object)


    def __init__(self, argv):
        super().__init__(argv)
        self.current_response_window = None
        logging.debug('Initializing WritingToolApp')
        self.generation_result_signal.connect(self._handle_generation_result)
        self.show_message_signal.connect(self.show_message_box)
        self.hotkey_triggered_signal.connect(self.on_hotkey_pressed)
        self.config = None
        self.config_path = None
        self.load_config()

        # Run any pending config migrations in a single pass (single restart).
        self._migrate_config()
        self._ensure_custom_defaults()

        self.options = None
        self.options_path = None
        self.load_options()
        self.history_store = HistoryStore(
            os.path.join(os.path.dirname(sys.argv[0]), 'history.json'),
            max_entries=self.config.get('history_max_entries', 100) if self.config else 100,
        )
        self.onboarding_window = None
        self.popup_window = None
        self.tray_icon = None
        self.tray_menu = None
        self.settings_window = None
        self.about_window = None
        self.safe_apply_window = None
        self.history_window = None
        self.diagnostics_window = None
        self.source_window_handle = None
        self.pending_option = ""
        self.pending_original = ""
        self.registered_hotkey = None
        self.output_queue = ""
        self.last_replace = 0
        self.hotkey_listener = None
        self.paused = False
        self.toggle_action = None

        # Holder for the user's selected text. Populated asynchronously by a
        # background thread so the popup can show instantly — see `_show_popup`
        # and `_fire_ctrl_c_and_capture_async`. The lock serializes Ctrl+C
        # captures across rapid hotkey presses so two captures don't fight
        # over the clipboard at once.
        self.current_text_holder = None
        self._capture_lock = threading.Lock()
        self._request_guard = RequestGenerationGuard()
        self._trigger_lock = threading.Lock()
        self.recent_triggers = []
        self.TRIGGER_WINDOW = 1.5
        self.MAX_TRIGGERS = 3

        self._ = gettext.gettext
        self.setup_translations('zh_CN')

        # Initialize the ctrl+c hotkey listener
        self.ctrl_c_timer = None
        self.setup_ctrl_c_listener()

        # Setup available AI providers
        self.providers = [GeminiProvider(self), OpenAICompatibleProvider(self), OllamaProvider(self)]

        if not self.config:
            logging.debug('No config found, showing onboarding')
            self.show_onboarding()
        else:
            logging.debug('Config found, setting up hotkey and tray icon')

            # Initialize the current provider, defaulting to Gemini
            provider_name = self.config.get('provider', 'Gemini')

            self.current_provider = next((provider for provider in self.providers if provider.provider_name == provider_name), None)
            if not self.current_provider:
                logging.warning(f'Provider {provider_name} not found. Using default provider.')
                self.current_provider = self.providers[0]

            self.current_provider.load_config(self.config.get("providers", {}).get(provider_name, {}))

            self.create_tray_icon()
            self.register_hotkey()

            try:
                lang = self.config['locale']
            except KeyError:
                lang = None
            self.change_language(lang)

            # Initialize update checker
            self.update_checker = UpdateChecker(self)
            self.update_checker.check_updates_async()

    def setup_translations(self, lang=None):
        if not lang:
            lang = QLocale.system().name().split('_')[0]

        if str(lang).lower().startswith('zh'):
            translation_function = translate
        else:
            try:
                translation = gettext.translation(
                    'messages',
                    localedir=os.path.join(os.path.dirname(__file__), 'locales'),
                    languages=[lang]
                )
            except FileNotFoundError:
                translation = gettext.NullTranslations()
            translation.install()
            translation_function = translation.gettext

        # Update the translation function for all UI components.
        self._ = translation_function
        ui.AboutWindow._ = self._
        ui.SettingsWindow._ = self._
        ui.ResponseWindow._ = self._
        ui.OnboardingWindow._ = self._
        ui.CustomPopupWindow._ = self._

    def retranslate_ui(self):
        self.update_tray_menu()

    def change_language(self, lang):
        self.setup_translations(lang)
        self.retranslate_ui()

        # Update all other windows
        for widget in QApplication.topLevelWidgets():
            if widget != self and hasattr(widget, 'retranslate_ui'):
                widget.retranslate_ui()

    def check_trigger_spam(self):
        """
        Check if the hotkey is being triggered too frequently.

        Rapid keyboard repeat is ignored; it must never terminate the app.
        """
        with self._trigger_lock:
            self.recent_triggers, throttled = record_trigger(
                self.recent_triggers,
                time.monotonic(),
                window_seconds=self.TRIGGER_WINDOW,
                maximum_triggers=self.MAX_TRIGGERS,
            )
            return throttled

    def load_config(self):
        """
        Load the configuration file.
        """
        self.config_path = os.path.join(os.path.dirname(sys.argv[0]), 'config.json')
        logging.debug(f'Loading config from {self.config_path}')
        if os.path.exists(self.config_path):
            try:
                if os.path.getsize(self.config_path) > 2_000_000:
                    raise ValueError('config.json exceeds the 2 MB safety limit')
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                if not isinstance(loaded, dict):
                    raise ValueError('config.json must contain a JSON object')
                self.config = loaded
                logging.debug('Config loaded successfully')
            except (OSError, UnicodeError, ValueError) as error:
                logging.error(f'Unable to load config.json safely: {error}')
                self.config = None
        else:
            logging.debug('Config file not found')
            self.config = None

    def _ensure_custom_defaults(self):
        """Add custom-build defaults without discarding existing user data."""
        if self.config is None:
            return

        defaults = {
            'locale': 'zh_CN',
            'remember_last_action': False,
            'last_used_option': 'Proofread',
            'popup_position': 'bottom_right',
            'custom_background_path': '',
            'safe_apply_enabled': True,
            'history_enabled': True,
            'history_max_entries': 100,
        }
        changed = False
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value
                changed = True

        # This fork is intentionally Chinese-first, including upgrades from
        # the portable English release.
        if self.config.get('locale') != 'zh_CN':
            self.config['locale'] = 'zh_CN'
            changed = True

        if changed:
            self.save_config(self.config)

    def _migrate_config(self):
        """
        One-shot config migration. Catches any user up to the current schema
        (v10) regardless of where they started — v7, v8, or already current —
        in a single pass without forcing a restart.

        Each version is gated on its own `is_config_file_updated_for_v{N}`
        flag, so re-running this is a no-op once everything's caught up.
        Bump CURRENT_CONFIG_VERSION and add a `# v{N}` block when adding a
        new migration step.

        v8 (introduced 2025):
          • Google removed Gemini 2.0 from the free API → bump model.
          • Obfuscate plaintext Gemini API keys (defeats Ctrl+F scanning).
          The custom-model input field didn't exist pre-v8, so any pre-v8
          model value is safe to overwrite — there's nothing custom to
          preserve.

        v9 (introduced 2026):
          • Google deprecated the Gemma 3 family. Migrate every v8 user on a
            now-deprecated preset to the new default (`gemini-flash-latest`)
            so they immediately land on the fast experience. They can opt
            into the unlimited-but-slow Gemma 4 options from the dropdown
            if they hit the 20/day Flash quota.
            Preserve custom model values (which DID exist by then) so a user
            who picked, say, `gemini-3.1-pro-preview` doesn't get reset.
          • SDK migration to `google-genai` is code-side only; nothing to
            do in config.

        v10 (custom build):
          • Migrate every provider API key to Windows DPAPI.
          • Enable safe apply and encrypted history defaults.
        """
        CURRENT_CONFIG_VERSION = 10
        # Default for new installs and migrating users.
        NEW_DEFAULT_MODEL = 'gemini-flash-latest'
        # v8 -> v9 model mapping. Every retired preset is bumped to the new
        # default so users get the fast Flash-tier experience by default.
        V8_TO_V9_MAP = {
            'gemma-3-27b-it':           NEW_DEFAULT_MODEL,
            'gemma-3-4b-it':            NEW_DEFAULT_MODEL,
            'gemini-flash-lite-latest': NEW_DEFAULT_MODEL,
            # 'gemini-flash-latest' itself is already current — no entry needed.
        }

        # New user (no config yet) — onboarding will create a fresh, current
        # config; nothing to migrate.
        if not self.config:
            logging.debug('No config to migrate (new user)')
            return

        needs_v8 = not self.config.get('is_config_file_updated_for_v8', False)
        needs_v9 = not self.config.get('is_config_file_updated_for_v9', False)
        needs_v10 = not self.config.get('is_config_file_updated_for_v10', False)

        if not needs_v8 and not needs_v9 and not needs_v10:
            logging.debug('Config already up-to-date, no migration needed')
            return

        logging.info(
            f'Running config migration (needs_v8={needs_v8}, needs_v9={needs_v9}, '
            f'needs_v10={needs_v10})...'
        )

        config_changed = False
        gemini_config = (
            self.config.get('providers', {}).get('Gemini (Recommended)')
        )

        if gemini_config is not None:
            old_model = gemini_config.get('model_name', '')

            # v8: pre-v8 users didn't have a custom-model field, so we can
            # bump unconditionally. We skip the historical "v8 default of
            # gemma-3-27b-it" intermediate stop and jump straight to the
            # current default.
            if needs_v8:
                if old_model != NEW_DEFAULT_MODEL:
                    gemini_config['model_name'] = NEW_DEFAULT_MODEL
                    logging.info(f'[v8] Bumped Gemini model "{old_model}" -> "{NEW_DEFAULT_MODEL}"')
                    config_changed = True

                # Obfuscate the API key. The helper is idempotent — already-
                # obfuscated keys (with the `enc:` prefix) pass through
                # unchanged.
                api_key = gemini_config.get('api_key', '')
                if api_key:
                    new_key = protect_secret(api_key)
                    if new_key != api_key:
                        gemini_config['api_key'] = new_key
                        logging.info('[v8] Obfuscated plaintext Gemini API key')
                        config_changed = True

            # v9: only runs for users coming from v8. Preserve tier choice via
            # the V8_TO_V9_MAP so an unlimited-tier user doesn't get silently
            # downgraded to a daily-quota model. Custom values (anything not
            # in the map) are left alone.
            elif needs_v9:
                new_model = V8_TO_V9_MAP.get(old_model)
                if new_model is not None and new_model != old_model:
                    gemini_config['model_name'] = new_model
                    logging.info(f'[v9] Bumped Gemini model "{old_model}" -> "{new_model}"')
                    config_changed = True

        if needs_v10:
            for provider_config in self.config.get('providers', {}).values():
                if not isinstance(provider_config, dict):
                    continue
                api_key = provider_config.get('api_key', '')
                if not api_key:
                    continue
                try:
                    protected_key = protect_secret(unprotect_secret(api_key))
                except Exception as error:
                    logging.error(f'Unable to migrate an API key to DPAPI: {error}')
                    continue
                if protected_key != api_key:
                    provider_config['api_key'] = protected_key
                    config_changed = True
            self.config.setdefault('safe_apply_enabled', True)
            self.config.setdefault('history_enabled', True)
            self.config.setdefault('history_max_entries', 100)

        # Stamp every version flag up to current so we never re-run on
        # subsequent startups, even if no fields actually needed changing
        # (e.g., a v8 user who'd already picked a custom non-deprecated model).
        for n in range(8, CURRENT_CONFIG_VERSION + 1):
            self.config[f'is_config_file_updated_for_v{n}'] = True

        self.save_config(self.config)
        logging.info('Config migration complete')

        if config_changed:
            logging.info('Configuration data was upgraded without requiring a restart')

    def load_options(self):
        """
        Load the options file.
        """
        self.options_path = os.path.join(os.path.dirname(sys.argv[0]), 'options.json')
        logging.debug(f'Loading options from {self.options_path}')
        if os.path.exists(self.options_path):
            try:
                if os.path.getsize(self.options_path) > 2_000_000:
                    raise ValueError('options.json exceeds the 2 MB safety limit')
                with open(self.options_path, 'r', encoding='utf-8') as f:
                    self.options = normalize_options(json.load(f))
                logging.debug('Options loaded successfully')
            except (OSError, UnicodeError, ValueError) as error:
                logging.error(f'Unable to load options.json safely: {error}')
                self.options = {}
                self.show_message_signal.emit(
                    '预设文件错误',
                    'options.json 无法读取或格式无效。程序将继续运行，请在预设管理中恢复或导入预设。',
                )
        else:
            logging.debug('Options file not found')
            self.options = {}

    def save_config(self, config):
        """
        Save the configuration file.
        """
        directory = os.path.dirname(self.config_path) or "."
        os.makedirs(directory, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=directory,
                prefix=".writing-tools-config-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = handle.name
                json.dump(config, handle, indent=4, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            if os.name != "nt":
                os.chmod(temporary, 0o600)
            os.replace(temporary, self.config_path)
            logging.debug('Config saved successfully')
        finally:
            if temporary and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
        self.config = config

    def _safe_error_text(self, error):
        provider = getattr(self, "current_provider", None)
        secret = getattr(provider, "api_key", "") if provider else ""
        return redact_text(str(error), [secret])

    def show_onboarding(self):
        """
        Show the onboarding window for first-time users.
        """
        logging.debug('Showing onboarding window')
        self.onboarding_window = ui.OnboardingWindow.OnboardingWindow(self)
        self.onboarding_window.close_signal.connect(self.exit_app)
        self.onboarding_window.show()

    @staticmethod
    def _to_pynput_hotkey(hotkey_str):
        """
        Convert a user-facing hotkey string ('ctrl+j', 'ctrl+alt+space') to
        pynput's `<ctrl>+j` / `<ctrl>+<alt>+<space>` format. Single-char keys
        stay as-is; multi-char keys (modifiers, named keys) get wrapped in <>.
        """
        return '+'.join(
            f'{t}' if len(t) <= 1 else f'<{t}>'
            for t in hotkey_str.split('+')
        )

    def start_hotkey_listener(self):
        """
        Build a single `GlobalHotKeys` listener that handles both the main
        Writing Tools shortcut AND any per-button direct hotkeys defined in
        options.json. Per-button hotkeys fire the corresponding option
        immediately, skipping the popup.

        On conflict between a button hotkey and the global shortcut (or
        between two button hotkeys), the first registration wins and the
        later one is logged and skipped — the listener can't dispatch to
        two callbacks for the same combination anyway.
        """
        try:
            if self.hotkey_listener is not None:
                self.hotkey_listener.stop()
                self.hotkey_listener = None

            hotkey_map = {}

            # --- Global Writing Tools hotkey ----------------------------------
            orig_shortcut = self.config.get('shortcut', 'ctrl+space')
            self.registered_hotkey = orig_shortcut
            try:
                global_parsed = self._to_pynput_hotkey(orig_shortcut)
                # Validate by parsing — raises if malformed.
                pykeyboard.HotKey.parse(global_parsed)

                def on_global_activate():
                    if self.paused:
                        return
                    if not hotkey_modifiers_are_physically_active(orig_shortcut):
                        logging.warning(
                            'Ignored a global hotkey activation with stale modifier state'
                        )
                        return
                    logging.debug('triggered global hotkey')
                    self.hotkey_triggered_signal.emit()

                hotkey_map[global_parsed] = on_global_activate
                logging.debug(f'Registered global hotkey: {global_parsed}')
            except Exception as e:
                logging.error(f'Failed to parse global hotkey "{orig_shortcut}": {e}')

            # --- Per-button direct hotkeys ------------------------------------
            # Custom is excluded — it needs a typed instruction from the user,
            # so a "fire directly" hotkey doesn't make sense for it.
            if self.options:
                for button_name, button_cfg in self.options.items():
                    if button_name == 'Custom':
                        continue
                    raw = (button_cfg.get('hotkey') or '').strip()
                    if not raw:
                        continue
                    try:
                        parsed = self._to_pynput_hotkey(raw)
                        # Same validation path as the global shortcut.
                        pykeyboard.HotKey.parse(parsed)
                    except Exception as e:
                        logging.error(
                            f'Invalid hotkey "{raw}" for button "{button_name}": {e}'
                        )
                        continue
                    if parsed in hotkey_map:
                        logging.warning(
                            f'Hotkey "{raw}" for button "{button_name}" '
                            f'conflicts with an already-registered binding; skipping'
                        )
                        continue
                    hotkey_map[parsed] = self._make_button_hotkey_callback(
                        button_name, raw
                    )
                    logging.debug(f'Registered button hotkey: {parsed} -> {button_name}')

            if not hotkey_map:
                logging.warning('No hotkeys to register')
                return

            self.hotkey_listener = pykeyboard.GlobalHotKeys(hotkey_map)
            self.hotkey_listener.start()
        except Exception as e:
            logging.error(f'Failed to register hotkey listener: {e}')

    def _make_button_hotkey_callback(self, button_name, hotkey=""):
        """
        Build a callback that fires `button_name` directly, bypassing the
        popup. Closes over `button_name` so we can register many distinct
        callbacks in a single GlobalHotKeys map.

        The actual fire is bounced through the Qt event loop because pynput
        invokes callbacks on its listener thread; popup/clipboard work needs
        to happen on the main thread.
        """
        def callback():
            if self.paused:
                return
            if not hotkey_modifiers_are_physically_active(hotkey):
                logging.warning(
                    'Ignored a preset hotkey activation with stale modifier state'
                )
                return
            if self.check_trigger_spam():
                logging.warning('Ignored rapid repeated preset hotkey activation')
                return
            logging.debug(f'Direct hotkey fired for button "{button_name}"')
            # Match the global hotkey's behaviour: cancel any in-flight
            # request so a new fire doesn't pile up on top of a previous one.
            if self.current_provider:
                self.current_provider.cancel()
                self.output_queue = ""
            # noinspection PyTypeChecker
            QtCore.QMetaObject.invokeMethod(
                self,
                "_fire_button_directly",
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(str, button_name)
            )
        return callback

    @Slot(str)
    def _fire_button_directly(self, button_name):
        """
        Run a button's option without showing the popup — invoked by a
        per-button direct hotkey. Mirrors the relevant parts of
        `_show_popup`: set up the async clipboard capture, then hand off
        to the worker thread (`process_option`) which waits on the holder
        and dispatches the AI call.
        """
        logging.debug(f'Firing button "{button_name}" directly')

        # If the popup is currently visible (e.g., user opened it then
        # pressed a button hotkey), close it so it doesn't compete.
        if self.popup_window is not None and self.popup_window.isVisible():
            self.popup_window.close()

        # Sanity check: button must still exist in options. Could be stale
        # if options.json was edited externally between registration and
        # fire — skip gracefully rather than crash.
        if not self.options or button_name not in self.options:
            logging.warning(f'Button "{button_name}" no longer exists; ignoring hotkey')
            return

        holder = self._begin_selection_capture()
        if holder is None:
            return

        # Same worker path as a popup-button click. process_option_thread
        # waits on the holder, surfaces "Please select text…" if empty,
        # and routes window-mode options through the response window.
        self.process_option(button_name)

    def register_hotkey(self):
        """
        Register the global hotkey for activating Writing Tools.
        """
        logging.debug('Registering hotkey')
        self.start_hotkey_listener()
        logging.debug('Hotkey registered')

    def on_hotkey_pressed(self):
        """
        Handle the hotkey press event.
        """
        logging.debug('Hotkey pressed')
        
        # Check for spam triggers
        if self.check_trigger_spam():
            logging.warning('Ignored rapid repeated hotkey activation')
            return
            
        # Original hotkey handling continues...
        if self.current_provider:
            logging.debug("Cancelling current provider's request")
            self.current_provider.cancel()
            self.output_queue = ""

        option = resolve_remembered_option(self.config, self.options)
        if option:
            self._fire_button_directly(option)
            return

        # noinspection PyTypeChecker
        QtCore.QMetaObject.invokeMethod(self, "_show_popup", QtCore.Qt.ConnectionType.QueuedConnection)

    @Slot()
    def _show_popup(self):
        """
        Show the popup window the moment the hotkey fires, and capture the
        user's selected text in parallel — popup display no longer waits on
        the clipboard. The old behaviour gated popup show on a 0.2-0.5s
        clipboard read, which on slower systems would time out and
        incorrectly fall back to the chat-only "Ask your AI" UI even when
        text *was* selected. We now assume text is always selected;
        `process_option_thread` waits on the holder before kicking off the
        AI request.
        """
        logging.debug('Showing popup window')

        # Fresh holder per popup. Fire Ctrl+C *before* we create the popup
        # so the keystroke is queued while focus is still on the user's
        # source app — the actual clipboard read happens in the background.
        holder = self._begin_selection_capture()
        if holder is None:
            return

        try:
            if self.popup_window is not None:
                logging.debug('Existing popup window found')
                if self.popup_window.isVisible():
                    logging.debug('Closing existing visible popup window')
                    self.popup_window.close()
                self.popup_window = None
            logging.debug('Creating new popup window')
            self.popup_window = ui.CustomPopupWindow.CustomPopupWindow(self)

            # Set the window icon
            icon_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
            if os.path.exists(icon_path): self.setWindowIcon(QtGui.QIcon(icon_path))
            # Get the screen containing the cursor
            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos)
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            screen_geometry = screen.availableGeometry()
            logging.debug(f'Cursor is on screen: {screen.name()}')
            logging.debug(f'Screen geometry: {screen_geometry}')
            # Show the popup to get its size
            self.popup_window.show()
            self.popup_window.adjustSize()
            # Ensure the popup it's focused, even on lower-end machines
            self.popup_window.activateWindow()
            # Keep focus on the popup so 1–9 and arrow keys work immediately.
            # The free-form input receives focus only after the user clicks it.
            QtCore.QTimer.singleShot(100, self.popup_window.setFocus)

            popup_width = self.popup_window.width()
            popup_height = self.popup_window.height()
            # Default to the bottom-right work area so the popup is predictable
            # and does not cover the user's current selection.
            x, y = bottom_right_position(screen_geometry, popup_width, popup_height)
            self.popup_window.move(x, y)
            logging.debug(f'Popup window moved to position: ({x}, {y})')
        except Exception as e:
            logging.error(f'Error showing popup window: {e}', exc_info=True)

    def _begin_selection_capture(self):
        """Start one isolated text capture and make it the active request."""

        source_window_handle = capture_foreground_window()
        holder = _SelectedTextHolder()
        if not self._fire_ctrl_c_and_capture_async(holder):
            return None

        holder.request_id = self._request_guard.begin()
        holder.source_window_handle = source_window_handle
        self.source_window_handle = source_window_handle
        self.current_text_holder = holder
        return holder

    def _fire_ctrl_c_and_capture_async(self, holder):
        """
        Inject Ctrl+C now (must happen while focus is still on the user's
        source app, before the popup is shown), then poll the clipboard
        for the result in a background thread. Returns immediately so the
        popup can display with no perceptible delay.

        Slow systems' clipboard subsystems can take a while to populate
        after Ctrl+C — that's the whole reason this is async. The polling
        timeout is generous; an empty result after timeout means the user
        pressed the hotkey without actually selecting anything, which
        `process_option_thread` reports as a normal error.
        """
        if not self._capture_lock.acquire(blocking=False):
            logging.warning('Ignored text capture while another clipboard capture is active')
            return False

        clipboard_backup = ''
        try:
            try:
                clipboard_backup = pyperclip.paste()
            except Exception:
                clipboard_backup = ''

            if not self.clear_clipboard():
                raise RuntimeError('Unable to clear clipboard before text capture')

            kbrd = pykeyboard.Controller()
            copy_key = pykeyboard.KeyCode.from_vk(0x43) if os.name == 'nt' else 'c'
            send_modified_key(
                kbrd,
                pykeyboard.Key.ctrl.value,
                copy_key,
                modifier_already_down=modifier_is_physically_down('ctrl'),
            )
        except Exception as e:
            logging.error(f'Error simulating Ctrl+C: {e}')
            try:
                pyperclip.copy(clipboard_backup)
            except Exception as restore_error:
                logging.error(f'Error restoring clipboard after capture failure: {restore_error}')
            holder.ready.set()
            self._capture_lock.release()
            return False

        def _poll_clipboard():
            text = ''
            try:
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    try:
                        text = pyperclip.paste() or ''
                    except Exception as e:
                        logging.error(f'Error reading clipboard during poll: {e}')
                        text = ''
                    if text:
                        break
                    time.sleep(0.05)
                holder.text = text
                logging.debug(f'Captured selected text (len={len(text)})')
            finally:
                try:
                    pyperclip.copy(clipboard_backup)
                except Exception as e:
                    logging.error(f'Error restoring clipboard: {e}')
                holder.ready.set()
                self._capture_lock.release()

        try:
            threading.Thread(target=_poll_clipboard, daemon=True).start()
            return True
        except Exception as error:
            logging.error(f'Unable to start clipboard capture worker: {error}')
            try:
                pyperclip.copy(clipboard_backup)
            except Exception as restore_error:
                logging.error(f'Error restoring clipboard after worker failure: {restore_error}')
            holder.ready.set()
            self._capture_lock.release()
            return False

    @staticmethod
    def clear_clipboard():
        """
        Clear the system clipboard.
        """
        try:
            pyperclip.copy('')
            return True
        except Exception as e:
            logging.error(f'Error clearing clipboard: {e}')
            return False

    def process_option(self, option, custom_change=None):
        """
        Spawn a worker thread that waits for the asynchronous clipboard
        capture and then runs the chosen option. Kept as a thin wrapper so
        the popup's click handler returns immediately and the GUI thread
        is never blocked on the clipboard read.
        """
        logging.debug(f'Processing option: {option}')

        holder = self.current_text_holder
        if holder is None or not holder.request_id:
            logging.warning('No active text capture is available for this option')
            self.show_message_signal.emit('错误', '当前选区已经失效，请重新选择文字后再试。')
            return

        if option != 'Custom' and option in self.options:
            self.set_last_used_option(option)

        # Drop any stale ref so a previous run's late-arriving response can't
        # land in a now-irrelevant window. The new window (if any) is created
        # by the worker via `_setup_response_window` once the text is in.
        self.current_response_window = None

        threading.Thread(
            target=self.process_option_thread,
            args=(option, custom_change, holder),
            daemon=True
        ).start()

    def set_last_used_option(self, option):
        """Persist the last successful preset choice for direct-run mode."""
        if not self.config or option not in self.options or option == 'Custom':
            return
        if self.config.get('last_used_option') == option:
            return
        self.config['last_used_option'] = option
        self.save_config(self.config)

    def set_remember_last_action(self, enabled):
        """Enable or disable direct execution from the main shortcut."""
        if self.config is None:
            return
        self.config['remember_last_action'] = bool(enabled)
        self.save_config(self.config)

    @Slot(str, str, int)
    def _setup_response_window(self, option, selected_text, request_id):
        """
        Open the response window and seed its chat history. Called from
        `process_option_thread` via `BlockingQueuedConnection` so the
        worker can rely on the window existing before it dispatches the
        AI request.
        """
        if not self._request_guard.is_current(request_id):
            return
        self.current_response_window = self.show_response_window(option, selected_text)
        self.current_response_window.request_id = request_id
        self.current_response_window.chat_history = [
            {
                "role": "user",
                "content": f"Original text to {option.lower()}:\n\n{selected_text}"
            }
        ]

    def process_option_thread(self, option, custom_change=None, holder=None):
        """
        Worker: wait for the background clipboard capture to land, then
        either open a response window (for window-mode options) or set up
        for inline replacement, and finally run the AI request.
        """
        logging.debug(f'Starting processing thread for option: {option}')

        # Typically near-instant since the user took time to read the popup
        # and click. The 3s ceiling is a safety net for genuinely sluggish
        # systems; if the 2s polling deadline in the capture thread tripped
        # first, the event is already set and this returns immediately.
        if holder is None or not holder.ready.wait(timeout=3.0):
            logging.warning('Timed out waiting for selected text capture')
        selected_text = (holder.text if holder else '') or ''

        request_id = holder.request_id if holder else 0
        if not self._request_guard.is_current(request_id):
            logging.info(f'Discarded stale request before dispatch: {request_id}')
            return

        if not selected_text.strip():
            # The chat-mode fallback that used to fire here was removed when
            # popup show became instant — we no longer have a way to detect
            # "user wants to chat" vs "capture failed", so we pick the safer
            # interpretation and surface the error.
            self.show_message_signal.emit('错误', '请先选择要处理的文字。')
            return

        selected_prompt = self.options.get(option)
        if not isinstance(selected_prompt, dict):
            self.show_message_signal.emit('错误', '所选预设已不存在，请重新打开操作面板。')
            return

        open_in_window = bool(selected_prompt.get('open_in_window', False))

        if open_in_window:
            QtCore.QMetaObject.invokeMethod(
                self,
                '_setup_response_window',
                QtCore.Qt.ConnectionType.BlockingQueuedConnection,
                QtCore.Q_ARG(str, option),
                QtCore.Q_ARG(str, selected_text),
                QtCore.Q_ARG(int, request_id),
            )
            if not self._request_guard.is_current(request_id):
                return

        try:
            prompt_prefix = selected_prompt.get('prefix', '')
            system_instruction = compose_system_instruction(selected_prompt)
            if option == 'Custom':
                prompt = f"{prompt_prefix}用户要求：{custom_change}\n\n待修改内容：\n{selected_text}"
            else:
                prompt = f"{prompt_prefix}{selected_text}"

            self.output_queue = ""

            logging.debug(f'Getting response from provider for option: {option}')
            provider = self.current_provider
            if provider is None:
                raise RuntimeError('No AI provider is active')

            if open_in_window:
                logging.debug('Getting response for window display')
            else:
                logging.debug('Getting response for direct replacement')
            response = provider.get_response(
                system_instruction,
                prompt,
                return_response=True,
            )
            logging.debug(f'Got response of length: {len(response) if response else 0}')
            if response:
                self.generation_result_signal.emit(
                    {
                        'request_id': request_id,
                        'option': option,
                        'original': selected_text,
                        'result': response,
                        'source_window_handle': holder.source_window_handle,
                        'open_in_window': open_in_window,
                        'provider': provider.provider_name,
                        'model': str(
                            getattr(provider, 'model_name', '')
                            or getattr(provider, 'api_model', '')
                            or ''
                        ).strip(),
                    }
                )

        except Exception as e:
            safe_error = self._safe_error_text(e)
            logging.error(f'An error occurred: {safe_error}')

            if not self._request_guard.is_current(request_id):
                logging.info(f'Discarded error from stale request: {request_id}')
                return
            if "Resource has been exhausted" in str(e):
                self.show_message_signal.emit('请求频率受限', 'Gemini API 已达到每分钟请求上限，请稍后再试。若经常发生，请在设置中切换到配额更高的模型。')
            elif "exceeded" in str(e).lower() or "rate limit" in str(e).lower():
                self.show_message_signal.emit('请求频率受限', 'API 已达到频率或用量限制，请稍后再试或调整设置。')
            else:
                self.show_message_signal.emit('错误', f'处理时发生错误：{safe_error}')

    @Slot(object)
    def _handle_generation_result(self, context):
        """Apply only the newest request result to its original selection."""

        request_id = int(context.get('request_id', 0))
        if not self._request_guard.is_current(request_id):
            logging.info(f'Discarded stale AI response: {request_id}')
            return

        result = context.get('result', '')
        if not isinstance(result, str) or not result:
            return

        if context.get('open_in_window'):
            window = self.current_response_window
            if window is None or getattr(window, 'request_id', 0) != request_id:
                logging.info(f'Discarded response for a closed result window: {request_id}')
                return
            if self.config.get('history_enabled', True):
                try:
                    self.history_store.add_entry(
                        option=context.get('option', '写作'),
                        original=context.get('original', ''),
                        result=result,
                        provider=context.get('provider', ''),
                        model=context.get('model', ''),
                        status='viewed',
                    )
                except Exception as error:
                    logging.error(f'Unable to save viewed result to history: {error}')
            window.set_text(result)
            return

        self.source_window_handle = context.get('source_window_handle')
        self.pending_option = context.get('option', '')
        self.pending_original = context.get('original', '')
        self.replace_text(result)

    @Slot(str, str)
    def show_message_box(self, title, message):
        """
        Show a message box with the given title and message.
        """
        QMessageBox.warning(None, title, message)

    def show_response_window(self, option, text):
        """
        Show the response in a new window instead of pasting it.
        """
        display_name = option_display_name(option, self.options.get(option, {}))
        response_window = ui.ResponseWindow.ResponseWindow(self, f"{display_name}结果")
        response_window.option = display_name
        response_window.selected_text = text  # Store the text for regeneration
        response_window.show()
        return response_window

    def replace_text(self, new_text):
        """Route generated text through safe preview or direct application."""
        error_message = 'ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST'
        if not new_text or not isinstance(new_text, str):
            logging.debug('No new text to process')
            return
        cleaned_text = new_text.rstrip('\n')
        if cleaned_text.strip() == error_message:
            self.show_message_signal.emit('错误', '所选文字不适用于当前预设。')
            return

        original = self.pending_original or (
            self.current_text_holder.text if self.current_text_holder else ''
        )
        entry = {
            'id': '',
            'option': self.pending_option or '写作',
            'original': original,
            'result': cleaned_text,
            'version': 1,
        }
        if self.config.get('history_enabled', True):
            try:
                entry = self.history_store.add_entry(
                    option=self.pending_option or '写作',
                    original=original,
                    result=cleaned_text,
                    provider=self.current_provider.provider_name,
                    model=self._current_model_name(),
                    status='preview' if self.config.get('safe_apply_enabled', True) else 'applied',
                )
            except Exception as error:
                logging.error(f'Unable to save generated result to history: {error}')

        if self.config.get('safe_apply_enabled', True):
            if self.safe_apply_window is not None:
                self.safe_apply_window.close()
            self.safe_apply_window = ui.SafeApplyWindow.SafeApplyWindow(self, entry)
            self.safe_apply_window.show()
            self.safe_apply_window.raise_()
            self.safe_apply_window.activateWindow()
        else:
            self.apply_text_to_source(cleaned_text)
        self.output_queue = ""

    def _current_model_name(self):
        provider = getattr(self, 'current_provider', None)
        if provider is None:
            return ''
        return str(
            getattr(provider, 'model_name', '')
            or getattr(provider, 'api_model', '')
            or ''
        ).strip()

    def apply_text_to_source(self, text):
        """Activate the captured source window and paste one complete version."""
        if not isinstance(text, str) or not text:
            return False
        try:
            clipboard_backup = pyperclip.paste()
        except Exception:
            clipboard_backup = ''
        try:
            pyperclip.copy(text)
        except Exception as error:
            logging.error(f'Unable to place generated text on the clipboard: {error}')
            return False
        if not self.source_window_handle:
            logging.warning('No source window handle is available; left result on clipboard')
            return False

        try:
            activated = activate_window(self.source_window_handle)
        except Exception as error:
            logging.error(f'Unable to reactivate the source window: {error}')
            activated = False
        if not activated:
            logging.warning('Unable to reactivate the source window; left result on clipboard')
            return False
        try:
            kbrd = pykeyboard.Controller()
            paste_key = pykeyboard.KeyCode.from_vk(0x56) if os.name == 'nt' else 'v'
            send_modified_key(
                kbrd,
                pykeyboard.Key.ctrl.value,
                paste_key,
                modifier_already_down=modifier_is_physically_down('ctrl'),
            )
            time.sleep(0.12)
        except Exception as error:
            logging.error(f'Unable to apply text to source window: {error}')
            try:
                pyperclip.copy(text)
            except Exception as clipboard_error:
                logging.error(f'Unable to retain generated text on clipboard: {clipboard_error}')
            return False
        try:
            pyperclip.copy(clipboard_backup)
        except Exception as error:
            # The paste already succeeded. Keep the generated text available
            # when clipboard restoration fails, but do not report the apply as
            # failed or offer a misleading retry that would paste twice.
            logging.error(f'Unable to restore clipboard after successful paste: {error}')
            try:
                pyperclip.copy(text)
            except Exception as clipboard_error:
                logging.error(f'Unable to retain generated text on clipboard: {clipboard_error}')
        return True

    @Slot()
    def show_history(self):
        if self.history_window is not None:
            self.history_window.close()
        self.history_window = ui.HistoryWindow.HistoryWindow(self)
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    @Slot()
    def show_diagnostics(self):
        if self.diagnostics_window is not None:
            self.diagnostics_window.close()
        self.diagnostics_window = ui.DiagnosticsWindow.DiagnosticsWindow(self)
        self.diagnostics_window.show()
        self.diagnostics_window.raise_()
        self.diagnostics_window.activateWindow()

    def create_tray_icon(self):
        """
        Create the system tray icon for the application.
        """
        if self.tray_icon:
            logging.debug('Tray icon already exists')
            return

        logging.debug('Creating system tray icon')
        icon_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
        if not os.path.exists(icon_path):
            logging.warning(f'Tray icon not found at {icon_path}')
            # Use a default icon if not found
            self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        else:
            self.tray_icon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(icon_path), self)
        # Set the tooltip (hover name) for the tray icon
        self.tray_icon.setToolTip("写作工具")
        self.tray_menu = QtWidgets.QMenu()
        self.tray_icon.setContextMenu(self.tray_menu)

        self.update_tray_menu()
        self.tray_icon.show()
        logging.debug('Tray icon displayed')

    def update_tray_menu(self):
        """
        Update the tray menu with all menu items, including pause functionality
        and proper translations.
        """
        self.tray_menu.clear()

        # Apply dark mode styles using darkdetect
        self.apply_dark_mode_styles(self.tray_menu)

        # Settings menu item
        settings_action = self.tray_menu.addAction(self._('Settings'))
        settings_action.triggered.connect(self.show_settings)

        history_action = self.tray_menu.addAction('历史与版本')
        history_action.triggered.connect(self.show_history)

        diagnostics_action = self.tray_menu.addAction('兼容性诊断')
        diagnostics_action.triggered.connect(self.show_diagnostics)

        # Pause/Resume toggle action 
        self.toggle_action = self.tray_menu.addAction(self._('Resume') if self.paused else self._('Pause'))
        self.toggle_action.triggered.connect(self.toggle_paused)

        # About menu item
        about_action = self.tray_menu.addAction(self._('About'))
        about_action.triggered.connect(self.show_about)

        # Exit menu item
        exit_action = self.tray_menu.addAction(self._('Exit'))
        exit_action.triggered.connect(self.exit_app)
        
    def toggle_paused(self):
        """Toggle the paused state of the application."""
        logging.debug('Toggle paused state')
        self.paused = not self.paused
        self.toggle_action.setText(self._('Resume') if self.paused else self._('Pause'))
        logging.debug('App is paused' if self.paused else 'App is resumed')

    @staticmethod
    def apply_dark_mode_styles(menu):
        """
        Apply styles to the tray menu based on system theme using darkdetect.
        """
        is_dark_mode = darkdetect.isDark()
        palette = menu.palette()

        if is_dark_mode:
            logging.debug('Tray icon dark')
            # Dark mode colors
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#2d2d2d"))  # Dark background
            palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#ffffff"))  # White text
        else:
            logging.debug('Tray icon light')
            # Light mode colors
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#ffffff"))  # Light background
            palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#000000"))  # Black text

        menu.setPalette(palette)


    """
    The function below (process_followup_question) processes follow-up questions in the chat interface for Summary, Key Points, and Table operations.

    This method handles the complex interaction between the UI, chat history, and AI providers:

    1. Chat History Management:
    - Maintains a list of all messages (original text, summary, follow-ups)
    - Properly formats roles (user/assistant) for each message
    - Preserves conversation context across multiple questions (until the Window is closed)

    2. Provider-Specific Handling:
    a) Gemini:
        - Converts internal roles to Gemini's user/model format
        - Uses chat sessions with proper history formatting
        - Maintains context through chat.send_message()
    
    b) OpenAI-compatible:
        - Uses standard OpenAI message array format
        - Includes system instruction and full conversation history
        - Properly maps internal roles to OpenAI roles

    3. Flow:
    a) User asks follow-up question
    b) Question is added to chat history
    c) Full history is formatted for the current provider
    d) Response is generated while maintaining context
    e) Response is displayed in chat UI
    f) New response is added to history for future context

    4. Threading:
    - Runs in a separate thread to prevent UI freezing
    - Uses signals to safely update UI from background thread
    - Handles errors too

    Args:
        response_window: The ResponseWindow instance managing the chat UI
        question: The follow-up question from the user

    This implementation is a bit convoluted, but it allows us to manage chat history & model roles across both providers! :3
    """

    def process_followup_question(self, response_window, question):
        """
        Process a follow-up question in the chat window.
        """
        logging.debug(f'Processing follow-up question: {question}')

        if not response_window.chat_history:
            logging.error("No chat history found")
            self.show_message_signal.emit('错误', '未找到对话记录。')
            self.followup_response_signal.emit(
                {'window': response_window, 'response': ''}
            )
            return

        # ResponseWindow already appended the current question. Snapshot the
        # history once on the GUI thread so the worker neither duplicates the
        # question nor reads a mutable QWidget-owned list in the background.
        history = [dict(message) for message in response_window.chat_history]
        provider = self.current_provider

        def process_thread():
            logging.debug('Starting follow-up processing thread')
            try:
                # System instruction based on original option
                system_instruction = "你是一名清晰、直接的 AI 助手。延续此前回答的语言、格式和风格；必要时使用简洁的 Markdown。"

                logging.debug('Sending request to AI provider')

                if provider is None:
                    raise RuntimeError('No AI provider is active')

                # Format conversation differently based on provider
                if isinstance(provider, GeminiProvider):
                    # Gemini takes the system instruction via its config object,
                    # not as an in-history message. We pass the raw chat history
                    # (user/assistant turns); GeminiProvider handles role mapping
                    # and drops any "system" entries internally.
                    response_text = provider.get_response(
                        system_instruction,
                        history,
                        return_response=True
                    )

                elif isinstance(provider, OllamaProvider):  #
                    # For Ollama, prepare messages with system instruction and history
                    messages = [{"role": "system", "content": system_instruction}]

                    for msg in history:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })

                    # Get response from Ollama
                    response_text = provider.get_response(
                        system_instruction,
                        messages,
                        return_response=True
                    )

                else:
                    # For OpenAI/compatible providers, prepare messages array, add system message
                    messages = [{"role": "system", "content": system_instruction}]

                    # Add history messages (including latest question)
                    for msg in history:
                        # Convert 'assistant' role to 'assistant' for OpenAI
                        role = "assistant" if msg["role"] == "assistant" else "user"
                        messages.append({"role": role, "content": msg["content"]})
                    
                    # Get response by passing the full messages array
                    response_text = provider.get_response(
                        system_instruction,
                        messages,  # Pass messages array directly
                        return_response=True
                    )

                logging.debug(f'Got response of length: {len(response_text or "")}')
                self.followup_response_signal.emit(
                    {'window': response_window, 'response': response_text or ''}
                )

            except Exception as e:
                safe_error = self._safe_error_text(e)
                logging.error(f'Error processing follow-up question: {safe_error}')

                if not getattr(response_window, '_closed', False):
                    if "Resource has been exhausted" in str(e):
                        self.show_message_signal.emit('请求频率受限', 'Gemini API 已达到每分钟请求上限，请稍后再试。')
                    elif "exceeded" in str(e).lower() or "rate limit" in str(e).lower():
                        self.show_message_signal.emit('请求频率受限', 'API 已达到频率或用量限制，请稍后再试或调整设置。')
                    else:
                        self.show_message_signal.emit('错误', f'处理时发生错误：{safe_error}')
                self.followup_response_signal.emit(
                    {'window': response_window, 'response': '抱歉，处理追问时发生错误。'}
                )

        # Start the thread
        threading.Thread(target=process_thread, daemon=True).start()

    def show_settings(self, providers_only=False):

        """
        Show the settings window.
        """
        logging.debug('Showing settings window')
        if (
            self.settings_window is None
            or self.settings_window.providers_only != providers_only
        ):
            self.settings_window = ui.SettingsWindow.SettingsWindow(
                self, providers_only=providers_only
            )
            self.settings_window.close_signal.connect(self.exit_app)
            self.settings_window.retranslate_ui()
        self.settings_window.show()
        self.settings_window.showNormal()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def activate_from_second_instance(self):
        """Bring the existing app forward when its shortcut is launched again."""

        if self.onboarding_window and self.onboarding_window.isVisible():
            window = self.onboarding_window
        elif self.popup_window and self.popup_window.isVisible():
            window = self.popup_window
        else:
            self.show_settings()
            window = self.settings_window

        window.showNormal()
        window.raise_()
        window.activateWindow()


    def show_about(self):
        """
        Show the about window.
        """
        logging.debug('Showing about window')
        if not self.about_window:
            self.about_window = ui.AboutWindow.AboutWindow()
        self.about_window.show()

    def setup_ctrl_c_listener(self):
        """
        Listener for Ctrl+C to exit the app.
        """
        signal.signal(signal.SIGINT, lambda signum, frame: self.handle_sigint(signum, frame))
        # This empty timer is needed to make sure that the sigint handler gets checked inside the main loop:
        # without it, the sigint handle would trigger only when an event is triggered, either by a hotkey combination
        # or by another GUI event like spawning a new window. With this we trigger it every 100ms with an empy lambda
        # so that the signal handler gets checked regularly.
        self.ctrl_c_timer = QtCore.QTimer()
        self.ctrl_c_timer.start(100)
        self.ctrl_c_timer.timeout.connect(lambda: None)
    def handle_sigint(self, signum, frame):
        """
        Handle the SIGINT signal (Ctrl+C) to exit the app gracefully.
        """
        logging.info("Received SIGINT. Exiting...")
        self.exit_app()

    def exit_app(self):
        """
        Exit the application.
        """
        logging.debug('Stopping the listener')
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
        logging.debug('Exiting application')
        self.quit()
