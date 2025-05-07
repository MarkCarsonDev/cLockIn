import AppKit
import objc
from typing import Callable, Optional
import Cocoa
from Quartz import CGShieldingWindowLevel

from autocomplete import AutocompleteTextInput

class TextInputWindow(AppKit.NSObject):
    """A Spotlight-style text input window for task entry"""
    
    # Declare ObjC properties and methods
    callback = objc.ivar('callback')
    storage = objc.ivar('storage')
    window = objc.ivar('window')
    text_input = objc.ivar('text_input')
    
    @objc.python_method
    def init(self):
        """Initialize with default values"""
        self = objc.super(TextInputWindow, self).init()
        if self is None:
            return None
            
        # Set default instance variables
        self.callback = None
        self.storage = None
        self.window = None
        self.text_input = None
        return self
    
    @objc.python_method
    def initWithCallback_storage_(self, callback, storage):
        """Initialize with a callback and storage"""
        # Initialize properly using super's designated initializer
        self = self.init()
        if self is None:
            return None
            
        # Set instance variables
        self.callback = callback
        self.storage = storage
        return self
    
    # This method implements the window delegate protocol
    def windowDidResignKey_(self, notification):
        """Close the window when it loses focus"""
        print("Window lost focus")
        if self.window:
            if self.callback:
                self.callback(None)
            self.close_window()
    
    def windowWillClose_(self, notification):
        """Handle window closing"""
        print("Window will close")
        if self.callback:
            self.callback(None)
    
    # Handle key events at the window level too
    def keyDown_(self, event):
        """Handle key events at window level"""
        key_code = event.keyCode()
        chars = event.characters()
        print(f"Window keyDown: {chars} (code: {key_code})")
        
        # Handle Escape key
        if key_code == 53:  # Escape key
            print("Escape key pressed in window")
            if self.callback:
                self.callback(None)
            self.close_window()
            return True
        
        return False
    
    @objc.python_method
    def createWindow(self):
        """Create the input window with a modern Spotlight-style appearance"""
        try:
            print("Creating enhanced text input window...")
            
            # Create a standard window with a title bar for better keyboard focus handling
            window_frame = Cocoa.NSRect((0, 0), (500, 60))
            style_mask = (
                Cocoa.NSWindowStyleMaskTitled |  # Title bar helps with keyboard focus
                Cocoa.NSWindowStyleMaskClosable  # Closable window
            )
            
            self.window = Cocoa.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                window_frame,
                style_mask,
                Cocoa.NSBackingStoreBuffered,
                False
            )
            
            # Set window properties
            self.window.setTitle_("New Task")  # Add a title for better visibility
            self.window.setLevel_(Cocoa.NSFloatingWindowLevel)  # Float above other windows
            self.window.setCollectionBehavior_(Cocoa.NSWindowCollectionBehaviorMoveToActiveSpace)
            
            # Center window on screen
            self.window.center()
            
            # Create the text input field (simplified version without autocomplete for now)
            input_frame = Cocoa.NSMakeRect(20, 15, 460, 30)
            self.text_input = AutocompleteTextInput.alloc().initWithFrame_callback_storage_(
                input_frame,
                self.callback,
                self.storage
            )
            
            # Add to window
            self.window.contentView().addSubview_(self.text_input)
            
            # Register for window events
            self.window.setDelegate_(self)
            
            # Show window BEFORE setting focus
            self.window.makeKeyAndOrderFront_(None)
            
            # Ensure app is active before focusing
            Cocoa.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            
            # Now set focus to text field
            self.window.makeFirstResponder_(self.text_input)
            
            # Create a timer to ensure focus after a slight delay
            Cocoa.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.1, self, "ensureFocus:", None, False
            )
            
            print("Enhanced text input window created.")
            return True
        except Exception as e:
            print(f"Error creating window: {e}")
            return False
    
    def ensureFocus_(self, timer):
        """Ensure text field has focus after a delay"""
        try:
            if not self.window or not self.text_input:
                return
                
            print("Ensuring text field focus...")
            
            # Force app to front again
            Cocoa.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            
            # Re-order window to front
            self.window.orderFront_(None)
            self.window.makeKeyWindow()
            
            # Force focus on text field
            self.window.makeFirstResponder_(self.text_input)
            
            # Force field editor creation
            field_editor = self.window.fieldEditor_forObject_(True, self.text_input)
            if field_editor:
                print("Field editor ensured")
                field_editor.setSelectedRange_(Cocoa.NSMakeRange(0, 0))
        except Exception as e:
            print(f"Error ensuring focus: {e}")
    
    @objc.python_method
    def close_window(self):
        """Close the window immediately"""
        try:
            if not self.window:
                return
                
            print("Closing text input window...")
            
            # Save reference before clearing
            window = self.window
            
            # Clear references
            self.window = None
            self.text_input = None
            
            # Close window
            window.close()
            
            print("Text input window closed.")
        except Exception as e:
            print(f"Error closing window: {e}")