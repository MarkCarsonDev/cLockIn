import objc
import Quartz
import time
import AppKit
import rumps
from typing import Callable, Dict, Optional

class KeyboardShortcut:
    """Class to manage global keyboard shortcuts"""
    def __init__(self, key: str, modifiers: list, callback: Callable):
        self.key = key
        self.modifiers = modifiers
        self.callback = callback
        self.event_tap = None
        self.run_loop_source = None
        self.running = False
        
    def start(self):
        """Start listening for the keyboard shortcut with improved error handling"""
        try:
            if self.running:
                return
            
            # Ensure permissions are available - add this helper method
            accessibility_enabled = self._check_accessibility_permissions()
            if not accessibility_enabled:
                print("Accessibility permissions not granted.")
                rumps.notification(
                    "Keyboard Shortcut Failed",
                    "Please enable accessibility permissions for this app",
                    "Go to System Preferences > Security & Privacy > Privacy > Accessibility"
                )
                return
            
            # Create a callback function that will call our instance method properly
            def callback_func(proxy, event_type, event, refcon):
                return self._event_callback_impl(proxy, event_type, event, refcon)
            
            # Store the callback to prevent garbage collection
            self._callback_func = callback_func
            
            # IMPORTANT: Create event tap at session level instead of app level
            self.event_tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,  # Tap at session level (higher privilege)
                Quartz.kCGHeadInsertEventTap,  # Insert at beginning of event tap chain
                Quartz.kCGEventTapOptionDefault,
                (1 << Quartz.kCGEventKeyDown),  # Only listen for key down events
                self._callback_func,  # Callback function
                None  # User data (not used here)
            )
            
            if self.event_tap is None:
                print("Failed to create event tap. Make sure your app has accessibility permissions.")
                rumps.notification(
                    "Keyboard Shortcut Failed",
                    "Please enable accessibility permissions for this app",
                    "Go to System Preferences > Security & Privacy > Privacy > Accessibility"
                )
                return
            
            # Create a CFRunLoopSource from the event tap
            self.run_loop_source = Quartz.CFMachPortCreateRunLoopSource(
                None, self.event_tap, 0
            )
            
            # Add the source to the current run loop (Critical!)
            Quartz.CFRunLoopAddSource(
                Quartz.CFRunLoopGetCurrent(), 
                self.run_loop_source, 
                Quartz.kCFRunLoopCommonModes
            )
            
            # Enable the event tap
            Quartz.CGEventTapEnable(self.event_tap, True)
            
            self.running = True
            print(f"Keyboard shortcut {self.key_string()} registered")
        except Exception as e:
            print(f"Error starting keyboard shortcut: {e}")

    def _check_accessibility_permissions(self):
        """Check if the app has accessibility permissions"""
        try:
            # Use AXIsProcessTrustedWithOptions to check if we have accessibility access
            trusted_check = {
                AppKit.NSString.stringWithString_("AXTrustedCheckOptionPrompt"): False
            }
            return AppKit.AXIsProcessTrustedWithOptions(trusted_check)
        except Exception:
            return False

    def _event_callback_impl(self, proxy, event_type, event, refcon):
        """Callback for CGEventTap, handles keyboard events"""
        try:
            if event_type != Quartz.kCGEventKeyDown:
                return event
            
            # Get keycode and modifiers from the event
            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            flags = Quartz.CGEventGetFlags(event)
            
            # Debug output to help diagnose shortcut issues
            print(f"Key event: keycode={keycode}, flags={flags}")
            
            # IMPORTANT: Check if any input field currently has focus
            # Don't intercept keys when a text field is active
            frontmost_app = AppKit.NSApplication.sharedApplication()
            if frontmost_app:
                main_window = frontmost_app.mainWindow()
                if main_window and main_window.firstResponder():
                    first_responder = main_window.firstResponder()
                    # If the first responder is a text field or field editor, don't intercept
                    if isinstance(first_responder, (AppKit.NSTextField, AppKit.NSTextView)):
                        print("Text field has focus, not intercepting key")
                        return event
            
            # Check if this matches our shortcut
            if self._is_shortcut_match(keycode, flags):
                print(f"Shortcut {self.key_string()} triggered!")
                
                # Try to safely call the callback
                try:
                    self.callback()
                except Exception as cb_error:
                    print(f"Error in shortcut callback: {cb_error}")
                
                # Return None to consume the event
                return None
            
            # Return the event unchanged to pass it through
            return event
        except Exception as e:
            print(f"Error in _event_callback_impl: {e}")
            # Return the original event to avoid breaking keyboard input
            return event

    def stop(self):
        """Stop listening for the keyboard shortcut"""
        try:
            if not self.running:
                return
            
            if self.event_tap:
                # Disable the event tap
                Quartz.CGEventTapEnable(self.event_tap, False)
                
                # Remove from run loop if we have a source
                if hasattr(self, 'run_loop_source') and self.run_loop_source:
                    Quartz.CFRunLoopRemoveSource(
                        Quartz.CFRunLoopGetCurrent(),
                        self.run_loop_source,
                        Quartz.kCFRunLoopCommonModes
                    )
                    # Release the run loop source
                    del self.run_loop_source
                    self.run_loop_source = None
                
                # Release the event tap
                del self.event_tap
                self.event_tap = None
            
            self.running = False
            print(f"Keyboard shortcut {self.key_string()} unregistered")
        except Exception as e:
            print(f"Error stopping keyboard shortcut: {e}")
    
    def _is_shortcut_match(self, keycode, event_flags):
        """Check if the event matches our shortcut with improved matching logic"""
        try:
            # Convert key string to keycode for comparison
            shortcut_keycode = self._key_to_keycode(self.key)
            if keycode != shortcut_keycode:
                return False
            
            # Get required flags for our modifier combination
            required_flags = self._modifiers_to_flags(self.modifiers)
            
            # Mask out irrelevant flags - focus only on modifiers we care about
            relevant_flags = (
                Quartz.kCGEventFlagMaskCommand | 
                Quartz.kCGEventFlagMaskShift | 
                Quartz.kCGEventFlagMaskAlternate | 
                Quartz.kCGEventFlagMaskControl
            )
            
            # Get only the modifier flags we care about
            masked_event_flags = event_flags & relevant_flags
            
            # Check if all required modifiers are present
            return masked_event_flags == required_flags
        except Exception as e:
            print(f"Error in _is_shortcut_match: {e}")
            return False
    
    def _key_to_keycode(self, key):
        """Convert a key string to a keycode"""
        # Handle single character keys
        if len(key) == 1:
            char = key.upper()
            if 'A' <= char <= 'Z':
                return ord(char) - ord('A') + 0x00  # A-Z: 0x00-0x19
            elif '0' <= char <= '9':
                return ord(char) - ord('0') + 0x1D  # 0-9: 0x1D-0x26
        
        # Special keys mapping
        special_keys = {
            'SPACE': 0x31,
            'RETURN': 0x24,
            'ENTER': 0x4C,
            'TAB': 0x30,
            'ESC': 0x35,
            'ESCAPE': 0x35,
            'DELETE': 0x33,
            'FORWARDDELETE': 0x75,
            'HOME': 0x73,
            'END': 0x77,
            'PAGEUP': 0x74,
            'PAGEDOWN': 0x79,
            'LEFT': 0x7B,
            'RIGHT': 0x7C,
            'UP': 0x7E,
            'DOWN': 0x7D,
            'F1': 0x7A,
            'F2': 0x78,
            'F3': 0x63,
            'F4': 0x76,
            'F5': 0x60,
            'F6': 0x61,
            'F7': 0x62,
            'F8': 0x64,
            'F9': 0x65,
            'F10': 0x6D,
            'F11': 0x67,
            'F12': 0x6F,
            'F13': 0x69,
            'F14': 0x6B,
            'F15': 0x71,
            'F16': 0x6A,
            'F17': 0x40,
            'F18': 0x4F,
            'F19': 0x50,
            'F20': 0x5A
        }
        
        return special_keys.get(key.upper(), 0)
    
    def _modifiers_to_flags(self, modifiers):
        """Convert modifier list to CGEventFlags"""
        flags = 0
        for mod in modifiers:
            if mod.upper() in ('CMD', 'COMMAND'):
                flags |= Quartz.kCGEventFlagMaskCommand
            elif mod.upper() == 'SHIFT':
                flags |= Quartz.kCGEventFlagMaskShift
            elif mod.upper() in ('ALT', 'OPTION'):
                flags |= Quartz.kCGEventFlagMaskAlternate
            elif mod.upper() in ('CTRL', 'CONTROL'):
                flags |= Quartz.kCGEventFlagMaskControl
        
        return flags
    
    def key_string(self):
        """Return a string representation of the shortcut"""
        mod_strings = []
        for mod in self.modifiers:
            if mod.upper() in ('CMD', 'COMMAND'):
                mod_strings.append('⌘')
            elif mod.upper() == 'SHIFT':
                mod_strings.append('⇧')
            elif mod.upper() in ('ALT', 'OPTION'):
                mod_strings.append('⌥')
            elif mod.upper() in ('CTRL', 'CONTROL'):
                mod_strings.append('⌃')
        
        return f"{' + '.join(mod_strings)} + {self.key.upper()}"


class ShortcutManager:
    """Manager class for handling multiple keyboard shortcuts"""
    def __init__(self):
        self.shortcuts = {}
    
    def register_shortcut(self, key, modifiers, callback):
        """Register a new keyboard shortcut"""
        try:
            shortcut_id = f"{'-'.join(modifiers)}-{key}"
            if shortcut_id in self.shortcuts:
                print(f"Shortcut {shortcut_id} already registered, updating...")
                self.shortcuts[shortcut_id].stop()
            
            print(f"Registering shortcut: {key} with modifiers {modifiers}")
            shortcut = KeyboardShortcut(key, modifiers, callback)
            self.shortcuts[shortcut_id] = shortcut
            shortcut.start()
            return shortcut_id
        except Exception as e:
            print(f"Error registering shortcut: {e}")
    
    def unregister_shortcut(self, shortcut_id):
        """Unregister an existing keyboard shortcut"""
        try:
            if shortcut_id in self.shortcuts:
                self.shortcuts[shortcut_id].stop()
                del self.shortcuts[shortcut_id]
                return True
            return False
        except Exception as e:
            print(f"Error unregistering shortcut: {e}")
            return False
    
    def unregister_all(self):
        """Unregister all shortcuts"""
        try:
            for shortcut in list(self.shortcuts.values()):
                shortcut.stop()
            self.shortcuts.clear()
        except Exception as e:
            print(f"Error unregistering all shortcuts: {e}")
        
    def cleanup(self):
        """Clean up all shortcuts when app quits"""
        self.unregister_all()