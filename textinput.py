import AppKit
import objc
import Quartz
from typing import Callable, Optional, Dict, List
import Cocoa
import time
import sys

# Enable verbose debug logging
DEBUG = True

def debug_log(message):
    """Print debug message with timestamp"""
    if DEBUG:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[DEBUG {timestamp}] {message}")

class EventMonitor:
    """Global event monitor to capture key events regardless of focus"""
    
    def __init__(self, target):
        self.target = target
        self.event_tap = None
        self.run_loop_source = None
        self.running = False
        
    def start(self):
        """Start monitoring key events"""
        if self.running:
            return
        
        try:
            debug_log("EventMonitor: starting")
            # Create callback function for the event tap
            def callback_func(proxy, event_type, event, refcon):
                return self._event_callback(proxy, event_type, event, refcon)
            
            # Store callback to prevent garbage collection
            self._callback_func = callback_func
            
            # Create event tap for key down events
            self.event_tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,  # Tap at session level
                Quartz.kCGHeadInsertEventTap,  # Insert at beginning of event tap chain
                Quartz.kCGEventTapOptionDefault,
                (1 << Quartz.kCGEventKeyDown),  # Listen for key down events
                self._callback_func,
                None
            )
            
            if self.event_tap is None:
                debug_log("Failed to create event tap. Check accessibility permissions.")
                return False
            
            # Create run loop source from event tap
            self.run_loop_source = Quartz.CFMachPortCreateRunLoopSource(
                None, self.event_tap, 0
            )
            
            # Add source to current run loop
            Quartz.CFRunLoopAddSource(
                Quartz.CFRunLoopGetCurrent(),
                self.run_loop_source,
                Quartz.kCFRunLoopCommonModes
            )
            
            # Enable the event tap
            Quartz.CGEventTapEnable(self.event_tap, True)
            
            self.running = True
            debug_log("Event monitor started")
            return True
        
        except Exception as e:
            debug_log(f"Error starting event monitor: {e}")
            return False
    
    def stop(self):
        """Stop monitoring key events with improved cleanup"""
        debug_log("EventMonitor: stop called")
        if not self.running:
            return
        
        self.running = False  # Set this FIRST to prevent any new callbacks
        
        try:
            if self.event_tap:
                # Disable the event tap
                debug_log("Disabling event tap")
                Quartz.CGEventTapEnable(self.event_tap, False)
                
                # Remove source from run loop and release it
                if self.run_loop_source:
                    debug_log("Removing run loop source")
                    Quartz.CFRunLoopRemoveSource(
                        Quartz.CFRunLoopGetCurrent(),
                        self.run_loop_source,
                        Quartz.kCFRunLoopCommonModes
                    )
                    
                    # Set to None to release reference
                    self.run_loop_source = None
                
                # Set to None to release reference
                self.event_tap = None
            
            # Clear reference to target
            self.target = None
            
            debug_log("EventMonitor: stop completed")
        except Exception as e:
            debug_log(f"Error stopping event monitor: {e}")
    
    def _event_callback(self, proxy, event_type, event, refcon):
        """Callback for CGEventTap to handle key events with enhanced safety checks"""
        # Early exit checks for several conditions
        if not self.running:
            debug_log("EventMonitor not running, passing event through")
            return event
            
        if not self.target:
            debug_log("EventMonitor has no target, passing event through")
            return event
            
        if not hasattr(self.target, 'active'):
            debug_log("Target doesn't have 'active' attribute, passing event through")
            return event
            
        if not self.target.active:
            debug_log("Target is not active, passing event through")
            return event
            
        if event_type != Quartz.kCGEventKeyDown:
            return event
        
        try:
            # Get keycode and modifiers from the event
            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            chars = ""
            try:
                chars = Cocoa.NSEvent.eventWithCGEvent_(event).characters()
            except:
                pass
            
            debug_log(f"Key event: keycode={keycode}, chars='{chars}'")
            
            # Specifically check for ESC key (keycode 53)
            if keycode == 53:  # ESC key
                debug_log("ESC key detected")
                
                # First try to close via window_controller
                if hasattr(self.target, 'window_controller'):
                    debug_log("Target has window_controller, calling close_window")
                    if self.target.window_controller and hasattr(self.target.window_controller, 'close_window'):
                        self.target.window_controller.close_window()
                        return None  # Consume the event
                
                # Try window() method if available
                if hasattr(self.target, 'window') and callable(getattr(self.target, 'window')):
                    window = self.target.window()
                    if window:
                        debug_log("Closing window via target's window() method")
                        if hasattr(window, 'close_window'):
                            window.close_window()
                        else:
                            window.close()
                        return None  # Consume the event
                
                # Try callback as last resort
                if hasattr(self.target, 'callback') and self.target.callback:
                    debug_log("Calling target's callback with None")
                    self.target.callback(None)
                    return None  # Consume the event
            
            # One more safety check before forwarding
            if not hasattr(self.target, 'process_key_event'):
                debug_log("Target doesn't have process_key_event method, passing event through")
                return event
                
            # Forward to target
            consumed = self.target.process_key_event(keycode, chars, event)
            if consumed:
                debug_log(f"Key event consumed: {keycode}")
                return None  # Consume the event
            
            return event  # Pass through the event
        except Exception as e:
            debug_log(f"Error in event callback: {e}")
            # Return the original event to avoid breaking input
            return event
        

class CategoryTaskView(AppKit.NSTextView):
    """A custom text view that handles category and task input with visual styling"""
    
    callback = objc.ivar('callback')
    storage = objc.ivar('storage')
    category_mode = objc.ivar('category_mode')
    selected_category = objc.ivar('selected_category')
    autocomplete_options = objc.ivar('autocomplete_options')
    current_autocomplete_index = objc.ivar('current_autocomplete_index') 
    is_first_character = objc.ivar('is_first_character')
    placeholderAttrString = objc.ivar('placeholderAttrString')
    event_monitor = objc.ivar('event_monitor')
    
    def initWithFrame_callback_storage_(self, frame, callback, storage):
        """Initialize with frame, callback, and data storage"""
        debug_log("CategoryTaskView: initWithFrame_callback_storage_ called")
        self = objc.super(CategoryTaskView, self).initWithFrame_(frame)
        if self is None:
            debug_log("CategoryTaskView: initialization failed - super returned None")
            return None
        
        # Set instance variables
        self.callback = callback
        self.storage = storage
        self.category_mode = False
        self.selected_category = None
        self.autocomplete_options = []
        self.current_autocomplete_index = -1
        self.is_first_character = True
        self.event_monitor = None
        self.active = True
        
        # Configure the text view appearance
        self.setEditable_(True)
        self.setSelectable_(True)
        self.setRichText_(True)
        self.setAllowsUndo_(True)
        
        # Use semi-transparent text
        self.setFont_(AppKit.NSFont.systemFontOfSize_(16.0))
        self.setTextColor_(AppKit.NSColor.textColor())
        
        # Set background to transparent
        self.setDrawsBackground_(True)
        self.setBackgroundColor_(AppKit.NSColor.clearColor())
        
        # CRITICAL CURSOR SETTINGS
        self.setInsertionPointColor_(AppKit.NSColor.whiteColor())  # Make cursor white for visibility
        
        # Disable spell checking which can interfere with cursor
        if hasattr(self, 'setContinuousSpellCheckingEnabled_'):
            self.setContinuousSpellCheckingEnabled_(False)
        
        # REMOVED: setAllowsKeyEquivalents_ as it doesn't exist in your implementation
        
        # Ensure proper drawing behavior
        self.setNeedsDisplayInRect_(self.bounds())
        
        # Set up placeholder
        self.placeholderAttrString = self.createPlaceholderString_("What are you working on?")
        
        # Register for text change notifications
        nc = AppKit.NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(
            self,
            "textDidChange:",
            AppKit.NSTextDidChangeNotification,
            None
        )
        
        # Create event monitor
        self.event_monitor = EventMonitor(self)
        
        debug_log("CategoryTaskView: initialization complete")
        return self

    def drawInsertionPointInRect_color_turnedOn_(self, rect, color, flag):
        """Override to make the cursor more visible"""
        debug_log(f"Drawing insertion point at {rect}")
        # Make cursor wider and use white color
        wider_rect = AppKit.NSMakeRect(
            rect.origin.x, 
            rect.origin.y, 
            3.0,  # Make cursor 3 pixels wide
            rect.size.height
        )
        
        # Always use white color for better visibility
        cursor_color = AppKit.NSColor.whiteColor()
        
        # Call super with our modified parameters
        objc.super(CategoryTaskView, self).drawInsertionPointInRect_color_turnedOn_(
            wider_rect, cursor_color, flag
        )

    def ensureCursorVisible(self):
        """Make sure the cursor is visible and blinking"""
        debug_log("Ensuring cursor is visible")
        
        # Force view to redraw
        self.setNeedsDisplay_(True)
        
        # Get the current selection
        selected_range = self.selectedRange()
        
        # Reset selection to force cursor redraw
        if selected_range.location != AppKit.NSNotFound:
            current_pos = selected_range.location
            # Toggle selection to force cursor redraw
            self.setSelectedRange_(AppKit.NSMakeRange(0, 0))
            self.setSelectedRange_(AppKit.NSMakeRange(current_pos, 0))
            
            # Make sure the cursor position is visible
            self.scrollRangeToVisible_(selected_range)
        else:
            # If no selection, set cursor at end
            text_length = len(self.string())
            self.setSelectedRange_(AppKit.NSMakeRange(text_length, 0))
            
        # Explicitly set focus
        if self.window():
            self.window().makeFirstResponder_(self)
    
    def startEventMonitor(self):
        """Start monitoring keyboard events"""
        if self.event_monitor:
            result = self.event_monitor.start()
            debug_log(f"Event monitor start result: {result}")
            return result
        return False
    
    def stopEventMonitor(self):
        """Stop monitoring keyboard events with improved cleanup"""
        debug_log("CategoryTaskView: stopEventMonitor called")
        
        # Set active to false FIRST to ensure no more events are processed
        self.active = False
        
        if self.event_monitor:
            # Now stop the monitor
            try:
                debug_log("Stopping event monitor from CategoryTaskView")
                self.event_monitor.stop()
                self.event_monitor = None
                debug_log("Event monitor stopped from CategoryTaskView")
            except Exception as e:
                debug_log(f"Error stopping event monitor: {e}")
        
        debug_log("CategoryTaskView: stopEventMonitor completed")
    
    def dealloc(self):
        """Clean up resources"""
        debug_log("CategoryTaskView: dealloc called")
        
        # Stop event monitor if it exists
        self.active = False
        if self.event_monitor:
            try:
                self.event_monitor.stop()
                self.event_monitor = None
            except Exception as e:
                debug_log(f"Error stopping event monitor in dealloc: {e}")
        
        # Remove notification observer
        nc = AppKit.NSNotificationCenter.defaultCenter()
        nc.removeObserver_(self)
        
        debug_log("CategoryTaskView: dealloc completed")
        objc.super(CategoryTaskView, self).dealloc()
    
    def process_key_event(self, keycode, chars, event):
        """Process a key event from the global event monitor"""
        debug_log(f"Process key event: keycode={keycode}, chars='{chars}'")
        
        # Handle arrow keys to navigate the text
        if keycode == 123:  # Left arrow
            self.moveLeft_(None)
            return True
        elif keycode == 124:  # Right arrow
            self.moveRight_(None)
            return True
        elif keycode == 125:  # Down arrow
            self.moveDown_(None)
            return True
        elif keycode == 126:  # Up arrow
            self.moveUp_(None)
            return True
                
        # Handle Escape key to close the window
        if keycode == 53:  # Escape key
            debug_log("Escape key detected - closing window directly")
            window = self.window()
            if window and hasattr(window, 'close_window'):
                # Try to call the close_window method if it exists
                debug_log("Calling window's close_window method")
                window.close_window()
            elif window and hasattr(window, 'close'):
                debug_log("Calling window's close method")
                window.close()
            elif self.callback:
                debug_log("Calling callback with None for window close")
                self.callback(None)
            return True  # Consume the event
        
        # Handle CMD + A to select all text
        if keycode == 0x00:  # 'A' key
            modifiers = AppKit.NSEvent.modifierFlags()
            if modifiers & AppKit.NSCommandKeyMask:
                debug_log("CMD + A detected - selecting all text")
                self.selectAll_(None)
                return True
            
        # Handle Backspace/Delete key with improved behavior
        if keycode == 51:  # Backspace key
            debug_log("Backspace key detected")
            # Handle CMD + Backspace to clear all text
            modifiers = AppKit.NSEvent.modifierFlags()
            if modifiers & AppKit.NSCommandKeyMask:
                debug_log("CMD + Backspace detected - clearing all text")
                self.setString_("")
                self.setSelectedRange_(AppKit.NSMakeRange(0, 0))
                self.category_mode = False
                self.selected_category = None
                self.is_first_character = True
                self.updateTextStyling()
                return True
            
            # Get current text and selection
            text = self.string()
            selected_range = self.selectedRange()
            
            # Case 1: Selection exists - delete it
            if selected_range.length > 0:
                new_text = text[:selected_range.location] + text[selected_range.location + selected_range.length:]
                self.setString_(new_text)
                self.setSelectedRange_(AppKit.NSMakeRange(selected_range.location, 0))
                self.updateTextStyling()
                # If that is all text, reset state
                if len(new_text) == 0:
                    self.category_mode = False
                    self.selected_category = None
                    self.is_first_character = True
                return True
            
            # Case 2: Cursor is right after a category
            if self.selected_category and selected_range.location == len(f"@{self.selected_category.name} "):
                # Clear the category, return to category mode
                self.selected_category = None
                self.category_mode = True
                self.setString_("@" + text[selected_range.location:])
                self.setSelectedRange_(AppKit.NSMakeRange(1, 0))
                self.updateTextStyling()
                return True
            
            # Case 3: In category mode with a complete category name but not yet selected
            if self.category_mode and text.startswith("@") and text[:selected_range.location] in [f"@{c.name}" for c in self.storage.get_categories()]:
                # Remove the @ and clear the text
                self.setString_("@" + text[selected_range.location:].lstrip())
                self.setSelectedRange_(AppKit.NSMakeRange(1, 0))
                self.updateTextStyling()
                return True
            
            # Case 4: At the "@" character in category mode
            if self.category_mode and text.startswith("@") and selected_range.location == 1:
                # Exit category mode
                self.category_mode = False
                self.setString_(text[1:].lstrip())
                self.updateTextStyling()
                return True
            
            # Case 5: Standard backspace - delete previous character
            if selected_range.location > 0:
                new_text = text[:selected_range.location - 1] + text[selected_range.location:]
                self.setString_(new_text)
                self.setSelectedRange_(AppKit.NSMakeRange(selected_range.location - 1, 0))
                self.updateTextStyling()
                return True

            # Case 6: Empty text -- reset state from category mode
            if len(text) == 0:
                self.category_mode = False
                self.selected_category = None
                self.is_first_character = True
                self.setString_("")
                self.updateTextStyling()
                return True
            
            return True  # Always consume backspace
        
        # Handle Return/Enter key to submit input
        if keycode == 36:  # Return key
            debug_log("Return key detected")
            text = self.string()
            debug_log(f"Current text: '{text}'")
            
            if text.startswith("@") and not self.selected_category:
                # We're in category mode but haven't confirmed it yet
                category_name = text[1:].strip()  # Remove the @ prefix
                debug_log(f"Category name from input: '{category_name}'")
                
                if category_name:
                    try:
                        # Create category with full text after @
                        self.selected_category = self.storage.add_category(category_name)
                        self.category_mode = False
                        debug_log(f"Selected category: {self.selected_category.name}")
                        
                        # Update display with selected category (no task portion)
                        self.updateDisplayWithCategory()
                    except Exception as e:
                        debug_log(f"Error selecting category: {e}")
                    
                    return True  # Consume the event
            else:
                # Process full input to create a task
                task_name = text
                
                if self.selected_category:
                    # Extract task part after the category
                    category_display = f"@{self.selected_category.name} "
                    if text.startswith(category_display):
                        task_name = text[len(category_display):].strip()
                
                debug_log(f"Task name from input: '{task_name}'")
                
                if task_name:
                    try:
                        # Create/get the task and start it
                        task = self.storage.get_or_create_task(task_name, self.selected_category)
                        task.start()
                        self.storage.save()
                        debug_log(f"Created and started task: {task.name}")
                        
                        # Call callback with the task
                        if self.callback:
                            debug_log("Calling callback with task")
                            self.callback(task)
                        
                        # Close the window 
                        window = self.window()
                        if window and hasattr(window, 'close'):
                            debug_log("Closing window after task creation")
                            window.close()
                    except Exception as e:
                        debug_log(f"Error creating/starting task: {e}")
                    
                    return True  # Consume the event
        
        # Handle Tab key for autocomplete
        if keycode == 48:  # Tab key
            debug_log("Tab key detected")
            
            # Determine current input context
            if self.string().startswith("@") and not self.selected_category:
                # In category mode - cycle through categories
                debug_log("Handling category tab completion")
                self._cycleCategories()
            elif self.selected_category:
                # With selected category - cycle through its tasks
                debug_log("Handling category tasks tab completion")
                self._cycleCategoryTasks()
            else:
                # No category - cycle through uncategorized tasks
                debug_log("Handling uncategorized tasks tab completion")
                self._cycleUncategorizedTasks()
            return True  # Consume the event
        
        # If this is the first key pressed and it's @, enter category mode
        if len(self.string()) == 0 and chars == "@":
            debug_log("@ symbol detected as first character, entering category mode")
            self.category_mode = True
            self.is_first_character = False
            
            # Insert the @ symbol
            self.insertText_("@")
            
            # Update autocomplete
            self.updateAutocomplete()
            
            return True  # Consume the event
        
        # For all other keys, insert text into the text view
        if chars:
            debug_log(f"Inserting text: '{chars}'")
            self.insertText_(chars)
            return True  # Consume the event
        
        # Otherwise, let the standard event handling take place
        return False

    
    def setPlaceholderText_(self, placeholder_text):
        """Set placeholder text with proper styling"""
        attrs = {
            AppKit.NSFontAttributeName: self.font(),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.whiteColor().colorWithAlphaComponent_(0.5)

        }
        self.placeholderAttrString = AppKit.NSAttributedString.alloc().initWithString_attributes_(
            placeholder_text, attrs
        )
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        """Draw with centered placeholder text if empty"""
        objc.super(CategoryTaskView, self).drawRect_(rect)
        
        # Draw placeholder if the text view is empty
        if len(self.string()) == 0 and hasattr(self, 'placeholderAttrString'):
            bounds = self.bounds()
            text_rect = bounds
            
            # Center placeholder text
            text_size = self.placeholderAttrString.size()
            text_rect.origin.x = 5  # Left padding
            text_rect.origin.y = (bounds.size.height - text_size.height) / 2  # Vertically center
            
            self.placeholderAttrString.drawInRect_(text_rect)
    
    def createPlaceholderString_(self, placeholder_text):
        """Create a styled placeholder string"""
        attrs = {
            AppKit.NSFontAttributeName: self.font(),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.whiteColor().colorWithAlphaComponent_(0.5)
        }
        return AppKit.NSAttributedString.alloc().initWithString_attributes_(
            placeholder_text, attrs
        )

    def _cycleCategories(self):
        """Cycle through available categories"""
        # Get all categories 
        categories = self.storage.get_categories()
        if not categories:
            debug_log("No categories to cycle through")
            return
        
        # Search text is everything after the @ symbol
        search_text = ""
        text = self.string()
        if text.startswith("@") and len(text) > 1:
            search_text = text[1:].lower()
        
        # If the search text entirely matches a category, this must be continuing the cycle. 
        # Therefore we ignore and cycle next
        if search_text and any(c.name.lower() == search_text for c in categories):
            search_text = ""
        
        # Filter categories by search text if present
        print(search_text)
        if search_text:
            filtered_categories = [c for c in categories if search_text in c.name.lower()]
        else:
            filtered_categories = categories
        
        print(filtered_categories)
        if not filtered_categories:
            debug_log("No matching categories found")
            return
        
        # Initialize index if needed
        if not hasattr(self, 'cycle_index') or self.cycle_index < 0:
            self.cycle_index = -1
        
        # Cycle to next category
        self.cycle_index = (self.cycle_index + 1) % len(filtered_categories)
        selected = filtered_categories[self.cycle_index]
        
        # Update the text with selected category
        self.setString_(f"@{selected.name}")
        self.setSelectedRange_(AppKit.NSMakeRange(len(self.string()), 0))
        self.updateTextStyling()
        
        debug_log(f"Cycled to category: {selected.name}")

    def _cycleCategoryTasks(self):
        """Cycle through tasks for the selected category"""
        if not self.selected_category:
            debug_log("No category selected for task cycling")
            return
        
        # Get tasks for this category
        tasks = self.storage.get_tasks(self.selected_category)
        if not tasks:
            debug_log(f"No tasks for category: {self.selected_category.name}")
            return
        
        # Get current task input
        text = self.string()
        prefix = f"@{self.selected_category.name} "
        task_part = ""
        
        if text.startswith(prefix):
            task_part = text[len(prefix):].lower()
        
        # Filter tasks if we have input
        if task_part:
            filtered_tasks = [t for t in tasks if task_part in t.name.lower()]
        else:
            filtered_tasks = tasks
        
        if not filtered_tasks:
            debug_log("No matching tasks found for this category")
            return
        
        # Initialize index if needed
        if not hasattr(self, 'task_cycle_index') or self.task_cycle_index < 0:
            self.task_cycle_index = -1
        
        # Cycle to next task
        self.task_cycle_index = (self.task_cycle_index + 1) % len(filtered_tasks)
        selected = filtered_tasks[self.task_cycle_index]
        
        # Update the text with selected task
        self.setString_(f"{prefix}{selected.name}")
        self.setSelectedRange_(AppKit.NSMakeRange(len(self.string()), 0))
        self.updateTextStyling()
        
        debug_log(f"Cycled to task: {selected.name}")

    def _cycleUncategorizedTasks(self):
        """Cycle through uncategorized tasks"""
        # Get uncategorized tasks
        tasks = self.storage.get_tasks()  # This gets tasks with no category
        if not tasks:
            debug_log("No uncategorized tasks to cycle through")
            return
        
        # Get current input for filtering
        text = self.string().lower()
        
        # Filter tasks if we have input
        if text:
            filtered_tasks = [t for t in tasks if text in t.name.lower()]
        else:
            filtered_tasks = tasks
        
        if not filtered_tasks:
            debug_log("No matching uncategorized tasks found")
            return
        
        # Initialize index if needed
        if not hasattr(self, 'uncategorized_cycle_index') or self.uncategorized_cycle_index < 0:
            self.uncategorized_cycle_index = -1
        
        # Cycle to next task
        self.uncategorized_cycle_index = (self.uncategorized_cycle_index + 1) % len(filtered_tasks)
        selected = filtered_tasks[self.uncategorized_cycle_index]
        
        # Update the text with selected task
        self.setString_(selected.name)
        self.setSelectedRange_(AppKit.NSMakeRange(len(self.string()), 0))
        self.updateTextStyling()
        
        debug_log(f"Cycled to uncategorized task: {selected.name}")
    
    def insertText_(self, text):
        """Override insertText to handle text insertion with special @ handling"""
        debug_log(f"insertText_ called with text: '{text}'")
        
        current_text = self.string()
        selection_range = self.selectedRange()
        
        # Special handling for @ at beginning
        if text == "@" and selection_range.location == 0 and not current_text.startswith("@") and not self.selected_category:
            # Add @ and space at beginning
            if current_text:
                # Add space if there's existing text to separate from task
                new_text = f"@ {current_text}"
            else:
                new_text = "@"
            
            self.category_mode = True
            
            # Set new text and position cursor after @
            self.setString_(new_text)
            self.setSelectedRange_(AppKit.NSMakeRange(1, 0))
            
            # Update autocomplete and styling
            self.updateAutocomplete()
            self.updateTextStyling()
            return
        
        # Standard text insertion
        objc.super(CategoryTaskView, self).insertText_(text)
        
        # Update autocomplete and styling after insertion
        self.updateAutocomplete()
        self.updateTextStyling()
    
    def textDidChange_(self, notification):
        """Handle text changes for updating autocomplete and styling"""
        debug_log("textDidChange_ called")
        
        # Reset first character flag if text is empty
        if len(self.string()) == 0:
            debug_log("Text is empty, resetting state")
            self.is_first_character = True
            self.category_mode = False
            self.selected_category = None
        
        # Update autocomplete and styling
        self.updateAutocomplete()
        self.updateTextStyling()
    
    def updateTextStyling(self):
        """Apply visual styling to the text based on current state"""
        text = self.string()
        if len(text) == 0:
            return
        
        # Create a styled attributed string
        attr_string = AppKit.NSMutableAttributedString.alloc().initWithString_(text)
        
        # Apply base styling
        attr_string.addAttribute_value_range_(
            AppKit.NSFontAttributeName,
            self.font(),
            AppKit.NSMakeRange(0, len(text))
        )
        attr_string.addAttribute_value_range_(
            AppKit.NSForegroundColorAttributeName,
            AppKit.NSColor.textColor(),
            AppKit.NSMakeRange(0, len(text))
        )
        
        # Style category if in category mode or category selected
        if self.category_mode or self.selected_category:
            # Determine the category range
            if self.selected_category:
                category_text = f"@{self.selected_category.name}"
                category_range = AppKit.NSMakeRange(0, len(category_text))
                
                # Get category color
                category_color = self.nscolorFromHex_(self.selected_category.color)
                
                # Create a background style for the category
                attr_string.addAttribute_value_range_(
                    AppKit.NSForegroundColorAttributeName,
                    category_color,
                    category_range
                )
                
                # Add background with rounded corners effect
                attr_string.addAttribute_value_range_(
                    AppKit.NSBackgroundColorAttributeName,
                    category_color.colorWithAlphaComponent_(0.2),
                    category_range
                )
                
                # Bold font for category
                category_font = AppKit.NSFont.boldSystemFontOfSize_(self.font().pointSize())
                attr_string.addAttribute_value_range_(
                    AppKit.NSFontAttributeName,
                    category_font,
                    category_range
                )
            else:
                # We're in category mode but no category selected yet
                category_range = AppKit.NSMakeRange(0, len(text))
                
                # Style with a distinct color
                attr_string.addAttribute_value_range_(
                    AppKit.NSForegroundColorAttributeName,
                    AppKit.NSColor.systemBlueColor(),
                    category_range
                )
                
                # Light background
                attr_string.addAttribute_value_range_(
                    AppKit.NSBackgroundColorAttributeName,
                    AppKit.NSColor.systemBlueColor().colorWithAlphaComponent_(0.1),
                    category_range
                )
        
        # Save selection
        selected_range = self.selectedRange()
        
        # Apply the attributed string to the text view
        self.textStorage().setAttributedString_(attr_string)
        
        # Restore selection if valid
        if selected_range.location != AppKit.NSNotFound:
            self.setSelectedRange_(selected_range)
    
    def updateAutocomplete(self):
        """Update autocomplete suggestions based on current text"""
        text = self.string()
        
        if self.category_mode and not self.selected_category:
            # In category mode, show matching categories
            search_text = text[1:].lower() if len(text) > 1 else ""  # Remove the @ symbol
            categories = self.storage.get_categories()
            
            if search_text:
                self.autocomplete_options = [c for c in categories if search_text in c.name.lower()]
            else:
                self.autocomplete_options = categories
            
            self.current_autocomplete_index = -1
            
            # Inform the window to update autocomplete display
            if self.window() and hasattr(self.window(), "updateAutocompleteResults_"):
                self.window().updateAutocompleteResults_(self.autocomplete_options)
        
        elif self.selected_category:
            # Category is selected, show matching tasks for this category
            category_text = f"@{self.selected_category.name} "
            if text.startswith(category_text):
                search_text = text[len(category_text):].lower()
                
                tasks = self.storage.get_tasks(self.selected_category)
                
                if search_text:
                    self.autocomplete_options = [t for t in tasks if search_text in t.name.lower()]
                else:
                    self.autocomplete_options = tasks
                
                self.current_autocomplete_index = -1
                
                # Inform the window to update autocomplete display
                if self.window() and hasattr(self.window(), "updateAutocompleteResults_"):
                    self.window().updateAutocompleteResults_(self.autocomplete_options)
    
    def handleCategoryTab(self):
        """Handle tab key in category mode to cycle through categories"""
        if not self.autocomplete_options:
            return
        
        # Cycle to the next option
        self.current_autocomplete_index = (self.current_autocomplete_index + 1) % len(self.autocomplete_options)
        selected_category = self.autocomplete_options[self.current_autocomplete_index]
        
        # Update text with the selected category
        self.setString_(f"@{selected_category.name}")
        self.updateTextStyling()
        
        # Update autocomplete display in the window
        if self.window() and hasattr(self.window(), "highlightAutocompleteIndex_"):
            self.window().highlightAutocompleteIndex_(self.current_autocomplete_index)
        
        # Position cursor at the end
        self.setSelectedRange_(AppKit.NSMakeRange(len(self.string()), 0))
    
    def handleTaskTab(self):
        """Handle tab key in task mode to cycle through tasks"""
        if not self.autocomplete_options:
            return
        
        # Cycle to the next option
        self.current_autocomplete_index = (self.current_autocomplete_index + 1) % len(self.autocomplete_options)
        selected_task = self.autocomplete_options[self.current_autocomplete_index]
        
        # Update text with the selected task
        category_text = f"@{self.selected_category.name} "
        self.setString_(f"{category_text}{selected_task.name}")
        self.updateTextStyling()
        
        # Update autocomplete display in the window
        if self.window() and hasattr(self.window(), "highlightAutocompleteIndex_"):
            self.window().highlightAutocompleteIndex_(self.current_autocomplete_index)
        
        # Position cursor at the end
        self.setSelectedRange_(AppKit.NSMakeRange(len(self.string()), 0))

    def handleUncategorizedTaskTab(self):
        """Handle tab key to cycle through uncategorized tasks"""
        # Get uncategorized tasks
        tasks = self.storage.get_tasks()  # Uncategorized tasks
        if not tasks:
            return
        
        # Initialize options if empty
        if not self.autocomplete_options or self.current_autocomplete_index == -1:
            self.autocomplete_options = tasks
            self.current_autocomplete_index = -1
        
        # Cycle to the next option
        self.current_autocomplete_index = (self.current_autocomplete_index + 1) % len(self.autocomplete_options)
        selected_task = self.autocomplete_options[self.current_autocomplete_index]
        
        # Update text with the selected task
        self.setString_(selected_task.name)
        self.updateTextStyling()
        
        # Update autocomplete display in the window
        if self.window() and hasattr(self.window(), "highlightAutocompleteIndex_"):
            self.window().highlightAutocompleteIndex_(self.current_autocomplete_index)
        
        # Position cursor at the end
        self.setSelectedRange_(AppKit.NSMakeRange(len(self.string()), 0))
    
    def updateDisplayWithCategory(self):
        """Update display after selecting a category"""
        if not self.selected_category:
            return
        
        current_text = self.string()
        category_prefix = f"@{self.selected_category.name}"
        
        # Check if we're converting from @ input or adding to existing text
        if current_text.startswith("@"):
            # Extract any text after the category part (if exists)
            self.setString_(f"{category_prefix} {current_text[len(category_prefix):].lstrip()}")
        else:
            # There was no @ - could happen if we're selecting from autocomplete
            self.setString_(f"{category_prefix} ")
        
        self.updateTextStyling()
        
        # Position cursor after the category and space
        self.setSelectedRange_(AppKit.NSMakeRange(len(category_prefix) + 1, 0))
    
    def nscolorFromHex_(self, hex_string):
        """Convert hex color string to NSColor"""
        if not hex_string or not isinstance(hex_string, str) or not hex_string.startswith('#'):
            return AppKit.NSColor.systemBlueColor()
        
        # Remove # prefix
        hex_string = hex_string[1:]
        
        # Parse hex values
        try:
            r_hex = hex_string[0:2]
            g_hex = hex_string[2:4]
            b_hex = hex_string[4:6]
            
            r = int(r_hex, 16) / 255.0
            g = int(g_hex, 16) / 255.0
            b = int(b_hex, 16) / 255.0
            
            return AppKit.NSColor.colorWithRed_green_blue_alpha_(r, g, b, 1.0)
        except Exception:
            return AppKit.NSColor.systemBlueColor()

    def moveLeft_(self, sender):
        """Move cursor left"""
        selection = self.selectedRange()
        if selection.location > 0:
            self.setSelectedRange_(AppKit.NSMakeRange(selection.location - 1, 0))

    def moveRight_(self, sender):
        """Move cursor right"""
        selection = self.selectedRange()
        if selection.location < len(self.string()):
            self.setSelectedRange_(AppKit.NSMakeRange(selection.location + 1, 0))

    def moveUp_(self, sender):
        """Move cursor up - in our case, to beginning of text"""
        self.setSelectedRange_(AppKit.NSMakeRange(0, 0))

    def moveDown_(self, sender):
        """Move cursor down - in our case, to end of text"""
        self.setSelectedRange_(AppKit.NSMakeRange(len(self.string()), 0))

class AutocompleteView(AppKit.NSView):
    """A view to display autocomplete results"""
    
    results = objc.ivar('results')
    highlighted_index = objc.ivar('highlighted_index')
    item_height = objc.ivar('item_height')
    max_visible_items = objc.ivar('max_visible_items')
    callback = objc.ivar('callback')
    
    def initWithFrame_(self, frame):
        """Initialize with frame"""
        self = objc.super(AutocompleteView, self).initWithFrame_(frame)
        if self is None:
            return None
        
        # Set up properties
        self.results = []
        self.highlighted_index = -1
        self.item_height = 36.0
        self.max_visible_items = 5
        self.callback = None
        
        # Set up appearance
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(10.0)
        self.layer().setBorderWidth_(1.0)
        self.layer().setBorderColor_(AppKit.NSColor.separatorColor().CGColor())
        self.layer().setBackgroundColor_(AppKit.NSColor.windowBackgroundColor().colorWithAlphaComponent_(0.2).CGColor())
        
        # Add shadow
        self.layer().setShadowColor_(AppKit.NSColor.blackColor().CGColor())
        self.layer().setShadowOffset_(AppKit.NSMakeSize(0, -2))
        self.layer().setShadowOpacity_(0.2)
        self.layer().setShadowRadius_(10.0)
        
        return self
    
    def setCallback_(self, callback):
        """Set callback to be called when an item is selected"""
        self.callback = callback
    
    def setResults_(self, results):
        """Set the results to display"""
        self.results = results
        self.highlighted_index = -1
        self.setNeedsDisplay_(True)
        
        # Update frame height based on number of results
        if self.results:
            visible_items = min(len(self.results), self.max_visible_items)
            new_height = visible_items * self.item_height
            frame = self.frame()
            frame.size.height = new_height
            self.setFrame_(frame)
        
        self.setHidden_(len(self.results) == 0)
    
    def setHighlightedIndex_(self, index):
        """Set the index of the highlighted result"""
        if 0 <= index < len(self.results):
            self.highlighted_index = index
            self.setNeedsDisplay_(True)
    
    def mouseDown_(self, event):
        """Handle mouse down to select an item"""
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        index = int(point.y / self.item_height)
        
        if 0 <= index < len(self.results):
            self.highlighted_index = index
            self.setNeedsDisplay_(True)
            
            # Call the callback with the selected result
            if self.callback:
                self.callback(self.results[index])
    
    def drawRect_(self, rect):
        """Draw the autocomplete results"""
        objc.super(AutocompleteView, self).drawRect_(rect)
        
        if not self.results:
            return
        
        # Draw each result
        for i, result in enumerate(self.results):
            item_rect = AppKit.NSMakeRect(
                0, i * self.item_height, 
                self.bounds().size.width, self.item_height
            )
            
            # Draw highlight for selected item
            if i == self.highlighted_index:
                AppKit.NSColor.selectedControlColor().setFill()
                path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    AppKit.NSInsetRect(item_rect, 4, 4), 6.0, 6.0
                )
                path.fill()
            
            # Draw separator between items (except for the last one)
            if i < len(self.results) - 1:
                AppKit.NSColor.separatorColor().setStroke()
                sep_y = (i + 1) * self.item_height
                AppKit.NSBezierPath.strokeLineFromPoint_toPoint_(
                    AppKit.NSMakePoint(15, sep_y),
                    AppKit.NSMakePoint(self.bounds().size.width - 15, sep_y)
                )
            
            # Draw text
            text_rect = AppKit.NSInsetRect(item_rect, 15, 0)
            
            # Configure attributes for name
            text_color = (AppKit.NSColor.alternateSelectedControlTextColor() if i == self.highlighted_index 
                         else AppKit.NSColor.textColor())
            
            # Draw name based on what type of result this is
            if hasattr(result, 'name'):
                # For task or category
                name = result.name
                
                # Style differently for categories vs tasks
                if hasattr(result, 'color'):  # It's a category
                    # Create attributed string with color indicator
                    name_string = f"{name}"
                    attrs = {
                        AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(14.0),
                        AppKit.NSForegroundColorAttributeName: text_color
                    }
                    
                    # Draw category indicator
                    indicator_rect = AppKit.NSMakeRect(
                        text_rect.origin.x, 
                        text_rect.origin.y + (text_rect.size.height - 16) / 2,
                        16, 16
                    )
                    category_color = self.nscolorFromHex_(result.color)
                    category_color.setFill()
                    indicator_path = AppKit.NSBezierPath.bezierPathWithOvalInRect_(indicator_rect)
                    indicator_path.fill()
                    
                    # Adjust text rect to account for indicator
                    text_rect.origin.x += 25
                    
                    # Draw name
                    name_string = AppKit.NSAttributedString.alloc().initWithString_attributes_(
                        name_string, attrs
                    )
                    name_string.drawInRect_(AppKit.NSMakeRect(
                        text_rect.origin.x,
                        text_rect.origin.y + (text_rect.size.height - name_string.size().height) / 2,
                        text_rect.size.width,
                        name_string.size().height
                    ))
                else:  # It's a task
                    # Create attributed string for task
                    task_string = AppKit.NSAttributedString.alloc().initWithString_attributes_(
                        name, {
                            AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(14.0),
                            AppKit.NSForegroundColorAttributeName: text_color
                        }
                    )
                    
                    # Calculate duration if it's a task with time entries
                    if hasattr(result, 'time_entries') and result.time_entries:
                        total_seconds = result.total_duration()
                        hours = int(total_seconds // 3600)
                        minutes = int((total_seconds % 3600) // 60)
                        duration_string = AppKit.NSAttributedString.alloc().initWithString_attributes_(
                            f" ({hours}h {minutes}m)", {
                                AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(12.0),
                                AppKit.NSForegroundColorAttributeName: text_color.colorWithAlphaComponent_(0.7)
                            }
                        )
                        
                        # Combine task name and duration
                        combined_string = AppKit.NSMutableAttributedString.alloc().init()
                        combined_string.appendAttributedString_(task_string)
                        combined_string.appendAttributedString_(duration_string)
                        
                        # Draw combined string
                        combined_string.drawInRect_(AppKit.NSMakeRect(
                            text_rect.origin.x,
                            text_rect.origin.y + (text_rect.size.height - combined_string.size().height) / 2,
                            text_rect.size.width,
                            combined_string.size().height
                        ))
                    else:
                        # Just draw task name
                        task_string.drawInRect_(AppKit.NSMakeRect(
                            text_rect.origin.x,
                            text_rect.origin.y + (text_rect.size.height - task_string.size().height) / 2,
                            text_rect.size.width,
                            task_string.size().height
                        ))
    
    def nscolorFromHex_(self, hex_string):
        """Convert hex color string to NSColor"""
        if not hex_string or not isinstance(hex_string, str) or not hex_string.startswith('#'):
            return AppKit.NSColor.systemBlueColor()
        
        # Remove # prefix
        hex_string = hex_string[1:]
        
        # Parse hex values
        try:
            r_hex = hex_string[0:2]
            g_hex = hex_string[2:4]
            b_hex = hex_string[4:6]
            
            r = int(r_hex, 16) / 255.0
            g = int(g_hex, 16) / 255.0
            b = int(b_hex, 16) / 255.0
            
            return AppKit.NSColor.colorWithRed_green_blue_alpha_(r, g, b, 1.0)
        except Exception:
            return AppKit.NSColor.systemBlueColor()

class RainbowBorderView(AppKit.NSView):
    """A view that displays an animated rainbow border"""
    
    def initWithFrame_(self, frame):
        self = objc.super(RainbowBorderView, self).initWithFrame_(frame)
        if self is None:
            return None
        
        # Set up properties
        self.animating = False
        self.hue_offset = 0.0
        self.position_offset = 0.0
        self.animation_timer = None
        self.border_width = 5.0  # Increased from 2.0 to 5.0 for visibility
        self.corner_radius = 16.0
        
        # Make transparent to show content below
        self.setWantsLayer_(True)
        self.layer().setBackgroundColor_(AppKit.NSColor.clearColor().CGColor())
        
        return self
    
    def startAnimation(self):
        """Start the rainbow animation"""
        if self.animating:
            return
            
        self.animating = True
        
        # Create a timer to update the animation
        self.animation_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.03,  # Update every 30ms for smooth animation
            self,
            "updateAnimation:",
            None,
            True
        )
    
    def stopAnimation(self):
        """Stop the rainbow animation"""
        if not self.animating:
            return
            
        self.animating = False
        
        if self.animation_timer:
            self.animation_timer.invalidate()
            self.animation_timer = None
    
    def updateAnimation_(self, timer):
        """Update the animation state"""
        # Increment the hue and position offsets
        self.hue_offset = (self.hue_offset + 0.01) % 1.0
        self.position_offset = (self.position_offset + 0.005) % 1.0
        
        # Redraw
        self.setNeedsDisplay_(True)
    
    def drawRect_(self, rect):
        """Draw the rainbow border"""
        context = AppKit.NSGraphicsContext.currentContext().CGContext()
        
        # Clear the view
        AppKit.NSColor.clearColor().set()
        AppKit.NSRectFill(self.bounds())
        
        # Get inner rect (content area)
        inner_rect = AppKit.NSInsetRect(self.bounds(), self.border_width, self.border_width)
        
        # Create path for border with rounded corners
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), self.corner_radius, self.corner_radius
        )
        
        inner_path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            inner_rect, self.corner_radius - self.border_width, self.corner_radius - self.border_width
        )
        
        # Cut out the inner path to make a border
        path.appendBezierPath_(inner_path)
        path.setWindingRule_(AppKit.NSEvenOddWindingRule)
        
        # Save graphics state
        Quartz.CGContextSaveGState(context)
        
        # Create clip mask
        path.addClip()
        
        # Calculate total path length (approximation)
        perimeter = 2 * (self.bounds().size.width + self.bounds().size.height)
        
        # Draw rainbow gradient along the path
        segments = 100
        for i in range(segments):
            # Calculate position with offset
            pos = (i / float(segments) + self.position_offset) % 1.0
            
            # Calculate hue with offset
            hue = (pos + self.hue_offset) % 1.0
            
            # Create color for this segment - more vibrant colors
            color = AppKit.NSColor.colorWithCalibratedHue_saturation_brightness_alpha_(
                hue, 1.0, 1.0, 1.0  # Full saturation and brightness
            )
            
            # Calculate segment position
            segment_length = perimeter / segments
            segment_position = pos * perimeter
            
            # Determine which side of the rectangle this segment is on
            if segment_position < self.bounds().size.width:
                # Top side
                x1 = segment_position
                y1 = 0
                x2 = x1 + segment_length
                y2 = 0
            elif segment_position < self.bounds().size.width + self.bounds().size.height:
                # Right side
                x1 = self.bounds().size.width
                y1 = segment_position - self.bounds().size.width
                x2 = x1
                y2 = y1 + segment_length
            elif segment_position < 2 * self.bounds().size.width + self.bounds().size.height:
                # Bottom side
                x1 = self.bounds().size.width - (segment_position - self.bounds().size.width - self.bounds().size.height)
                y1 = self.bounds().size.height
                x2 = x1 - segment_length
                y2 = y1
            else:
                # Left side
                x1 = 0
                y1 = self.bounds().size.height - (segment_position - 2 * self.bounds().size.width - self.bounds().size.height)
                x2 = 0
                y2 = y1 - segment_length
            
            # Draw this segment in hue
            color.set()
            
            line_path = AppKit.NSBezierPath.bezierPath()
            line_path.moveToPoint_(AppKit.NSMakePoint(x1, y1))
            line_path.lineToPoint_(AppKit.NSMakePoint(x2, y2))
            line_path.setLineWidth_(self.border_width * 2)  # Make sure the lines overlap
            line_path.stroke()
        
        # Restore graphics state
        Quartz.CGContextRestoreGState(context)

class TextInputWindow(AppKit.NSObject):
    """A modern Spotlight-style text input window with autocomplete"""
    
    # Declare instance variables
    window = objc.ivar('window')
    text_view = objc.ivar('text_view')
    autocomplete_view = objc.ivar('autocomplete_view')
    scroll_view = objc.ivar('scroll_view')
    callback = objc.ivar('callback')
    storage = objc.ivar('storage')
    
    def initWithCallback_storage_(self, callback, storage):
        """Initialize with callback and storage"""
        debug_log("TextInputWindow: initWithCallback_storage_ called")
        self = objc.super(TextInputWindow, self).init()
        if self is None:
            debug_log("TextInputWindow: initialization failed - super returned None")
            return None
        
        # Set instance variables
        self.callback = callback
        self.storage = storage
        self.hue_offset = 0.0
        self.window = None
        self.scroll_view = None
        self.text_view = None
        self.autocomplete_view = None
        self.activation_timer = None  # Add this
        
        # Try to create the window
        success = self.createWindow()
        if not success:
            debug_log("TextInputWindow: createWindow failed")
            return None
        
        # Register for application activation notifications
        nc = AppKit.NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(
            self,
            "applicationActivationChanged:",
            AppKit.NSApplicationDidResignActiveNotification,
            None
        )
        
        # Start a backup timer that checks app activation state
        self.activation_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.2,  # Check every 200ms
            self,
            "checkAppActive:",
            None,
            True
        )
        
        debug_log("TextInputWindow: initialization complete with activation monitoring")
        return self
    
    def applicationActivationChanged_(self, notification):
        """Called when the application activation state changes"""
        debug_log("Application activation changed notification received")
        if notification.name() == AppKit.NSApplicationDidResignActiveNotification:
            debug_log("Application is no longer active - closing input window")
            self.close_window()
    
    def checkAppActive_(self, timer):
        """Backup timer to check if application is active"""
        app = AppKit.NSApplication.sharedApplication()
        #  isActive comes from the AppKit framework, but we should also check if the self.active is false
        if not app.isActive() and self.window and self.window.isVisible():
            debug_log("Timer detected application is not active - closing input window")
            self.close_window()
            # Don't invalidate timer here - it will be cleaned up in close_window
    def createWindow(self):
        """Create the input window with a modern Spotlight-style appearance and rainbow border"""
        try:
            debug_log("TextInputWindow: createWindow called")

            # Get screen dimensions
            screen_rect = AppKit.NSScreen.mainScreen().frame()
            window_width = 600
            window_height = 60

            # Position window near the top of the screen
            window_x = (screen_rect.size.width - window_width) / 2
            window_y = screen_rect.size.height * 0.5  # Position at 80% from bottom
            window_frame = AppKit.NSMakeRect(window_x, window_y, window_width, window_height)

            # First, create a full-screen blur overlay window
            try:
                debug_log("Creating blur overlay window")
                self.blur_window = BlurOverlayWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                    screen_rect,
                    AppKit.NSWindowStyleMaskBorderless,
                    AppKit.NSBackingStoreBuffered,
                    False
                )
                if not self.blur_window:
                    debug_log("Failed to create blur window")
                else:
                    debug_log("Blur window created successfully")
                    self.blur_window.setCollectionBehavior_(
                        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                        AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
                    )
                    # Show the blur window
                    self.blur_window.orderFrontRegardless()
                    debug_log("Blur window ordered front")
            except Exception as e:
                debug_log(f"Error creating blur window: {e}")
                # Continue without blur window
                self.blur_window = None

            # Now create the main panel
            debug_log("Creating main window")
            style_mask = (
                AppKit.NSWindowStyleMaskBorderless |
                AppKit.NSWindowStyleMaskResizable |
                AppKit.NSWindowStyleMaskFullSizeContentView
            )
            self.window = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                window_frame,
                style_mask,
                AppKit.NSBackingStoreBuffered,
                False
            )
            # to allow this NSPanel to become key and main, we need to set the following:
            self.window.setCollectionBehavior_(
                AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
            )
            if not self.window:
                raise RuntimeError("TextInputWindow: Failed to initialize NSPanel")
        
            # after you init the NSPanel
            self.window.setBecomesKeyOnlyIfNeeded_(False)

            # Configure panel appearance
            self.window.setOpaque_(False)
            self.window.setBackgroundColor_(AppKit.NSColor.clearColor())
            self.window.setHasShadow_(True)
            self.window.setLevel_(AppKit.NSStatusWindowLevel)

            self.window.setMovableByWindowBackground_(True)
            self.window.setCollectionBehavior_(
                AppKit.NSWindowCollectionBehaviorMoveToActiveSpace |
                AppKit.NSWindowCollectionBehaviorStationary
            )

            # Delegate must be set to catch focus loss
            self.window.setDelegate_(self)

            # Container and effects
            container = AppKit.NSView.alloc().initWithFrame_(
                AppKit.NSMakeRect(0, 0, window_width, window_height)
            )
            container.setWantsLayer_(True)
            container.layer().setCornerRadius_(20.0)
            container.layer().setMasksToBounds_(False)

            # Rainbow border with increased size
            try:
                debug_log("Creating rainbow border")
                self.rainbow_border = RainbowBorderView.alloc().initWithFrame_(
                    AppKit.NSMakeRect(-5, -5, window_width + 10, window_height + 10)  # Larger to be more visible
                )
                container.addSubview_(self.rainbow_border)
                debug_log("Rainbow border created")
            except Exception as e:
                debug_log(f"Error creating rainbow border: {e}")
                self.rainbow_border = None  # Continue without rainbow border

            # Frosted glass background
            effect = AppKit.NSVisualEffectView.alloc().initWithFrame_(
                AppKit.NSMakeRect(2, 2, window_width - 4, window_height - 4)
            )
            effect.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
            effect.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
            effect.setState_(AppKit.NSVisualEffectStateActive)
            effect.setWantsLayer_(True)
            effect.layer().setCornerRadius_(18.0)
            effect.layer().setMasksToBounds_(True)
            container.addSubview_(effect)

            # Set content view
            self.window.setContentView_(container)

            # Scrollable text input
            scroll_frame = AppKit.NSMakeRect(12, 12, window_width - 28, window_height - 24)
            self.scroll_view = AppKit.NSScrollView.alloc().initWithFrame_(scroll_frame)
            self.scroll_view.setBorderType_(AppKit.NSNoBorder)
            self.scroll_view.setHasVerticalScroller_(False)
            self.scroll_view.setHasHorizontalScroller_(False)
            self.scroll_view.setDrawsBackground_(False)
            effect.addSubview_(self.scroll_view)

            # Create the text view with proper configuration for cursor
            debug_log("Creating text view")
            text_frame = AppKit.NSMakeRect(0, 0, scroll_frame.size.width, scroll_frame.size.height)
            
            # IMPORTANT: Use the correct initialization method based on your CategoryTaskView implementation
            self.text_view = CategoryTaskView.alloc().initWithFrame_callback_storage_(
                text_frame, self.callback, self.storage
            )
            
            if not self.text_view:
                debug_log("Failed to create text view")
                raise RuntimeError("Failed to create text view")
            
            # Give the text view a reference to this window controller for escape handling
            debug_log("Setting window controller reference in text view")
            self.text_view.window_controller = self
            
            self.text_view.setTextContainerInset_(
                AppKit.NSMakeSize(5, (scroll_frame.size.height - 20) / 2)
            )
            self.scroll_view.setDocumentView_(self.text_view)

            # Autocomplete view (hidden initially)
            ac_frame = AppKit.NSMakeRect(12, window_height - 12, window_width - 28, 0)
            self.autocomplete_view = AutocompleteView.alloc().initWithFrame_(ac_frame)
            self.autocomplete_view.setCallback_(self.handleAutocompleteSelection_)
            self.autocomplete_view.setHidden_(True)
            effect.addSubview_(self.autocomplete_view)

            # Key event monitor for ESC/ENTER
            debug_log("Starting event monitor")
            self.text_view.startEventMonitor()

            # Start rainbow animation
            if self.rainbow_border:
                debug_log("Starting rainbow animation")
                self.rainbow_border.startAnimation()

            # Show and focus
            debug_log("Setting window focus")
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            self.window.orderFrontRegardless()
            self.window.makeKeyWindow()
            self.window.makeKeyAndOrderFront_(None)
            self.window.makeFirstResponder_(self.text_view)

            # Ensure focus persists
            AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.1, self, 'ensureFocus:', None, False
            )

            debug_log("TextInputWindow: Window created successfully")
            return True
        except Exception as e:
            debug_log(f"TextInputWindow: Error creating window: {e}")
            
            # Cleanup any partially created resources
            if hasattr(self, 'blur_window') and self.blur_window:
                debug_log("Cleaning up blur window after error")
                try:
                    self.blur_window.close()
                    self.blur_window = None
                except:
                    pass
            
            return False
        
    def canBecomeKeyWindow(self):
        return True
    def canBecomeMainWindow(self):
        return True
    
    def ensureFocus_(self, timer):
        """Ensure text view has focus"""
        if self.window and self.text_view:
            debug_log("Ensuring focus on text view...")
            
            # 1. Force app to front again
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            
            # 2. Force window to front
            self.window.orderFrontRegardless()
            self.window.makeKeyAndOrderFront_(None)

            
            # 3. Force it to be key window
            self.window.makeKeyWindow()
            
            # 4. Force focus on text view
            if not self.window.makeFirstResponder_(self.text_view):
                debug_log("Failed to make text view first responder in ensureFocus_!")
            else:
                debug_log("Successfully set focus to text view")
    
    def handleAutocompleteSelection_(self, result):
        """Handle selection from autocomplete view"""
        if hasattr(result, 'name'):
            # Handle category selection
            if hasattr(result, 'color'):  # It's a category
                self.text_view.selected_category = result
                self.text_view.category_mode = False
                self.text_view.updateDisplayWithCategory()
            else:  # It's a task
                # If we have a category selected, format accordingly
                if self.text_view.selected_category:
                    self.text_view.setString_(f"@{self.text_view.selected_category.name} {result.name}")
                else:
                    self.text_view.setString_(result.name)
                
                self.text_view.updateTextStyling()
            
            # Position cursor at the end
            self.text_view.setSelectedRange_(AppKit.NSMakeRange(len(self.text_view.string()), 0))
            
            # Hide autocomplete
            self.autocomplete_view.setHidden_(True)
            
            # Focus text view
            self.window.makeFirstResponder_(self.text_view)
    
    def updateAutocompleteResults_(self, results):
        """Update the autocomplete view with new results"""
        if not self.autocomplete_view:
            return
        
        self.autocomplete_view.setResults_(results)
        
        if results:
            # Adjust window height to accommodate autocomplete view
            window_frame = self.window.frame()
            autocomplete_height = self.autocomplete_view.frame().size.height
            
            # Calculate new positions
            autocomplete_y = window_frame.size.height - 12 - autocomplete_height
            
            # Update autocomplete view position
            autocomplete_frame = self.autocomplete_view.frame()
            autocomplete_frame.origin.y = autocomplete_y
            self.autocomplete_view.setFrame_(autocomplete_frame)
            
            # Extend window height
            self.window.setFrame_display_animate_(
                AppKit.NSMakeRect(
                    window_frame.origin.x,
                    window_frame.origin.y - autocomplete_height,
                    window_frame.size.width,
                    window_frame.size.height + autocomplete_height
                ),
                True,
                True
            )
        else:
            # Restore original window size if no results
            window_frame = self.window.frame()
            
            # Check if we need to adjust height
            if window_frame.size.height > 60:
                self.window.setFrame_display_animate_(
                    AppKit.NSMakeRect(
                        window_frame.origin.x,
                        window_frame.origin.y + self.autocomplete_view.frame().size.height,
                        window_frame.size.width,
                        60  # Original height
                    ),
                    True,
                    True
                )
    
    def highlightAutocompleteIndex_(self, index):
        """Highlight a specific index in the autocomplete view"""
        if self.autocomplete_view:
            self.autocomplete_view.setHighlightedIndex_(index)
    
    # NSWindowDelegate methods

    def windowDidBecomeKey_(self, notification):
        """Called when window gains focus"""
        print("test")
        if notification.object() == self.window:
            debug_log("Window gained focus")
            self.window_focused = True
            if self.rainbow_border:
                self.rainbow_border.startAnimation()
                    
    def windowDidResignKey_(self, notification):
            """Called when window loses focus"""
            debug_log("Window lost focus - closing input window")
            # Only handle if it's our window
            if notification.object() == self.window:
                # Close the window immediately
                self.close_window()
    
    def windowShouldClose_(self, sender):
        """Handle window closing"""
        debug_log("Window should close")
        if self.callback:
            self.callback(None)
        return True
    
    def windowWillClose_(self, notification):
        """Clean up resources when window closes"""
        debug_log("Window will close")
        
        # Stop the event monitor
        if self.text_view:
            self.text_view.stopEventMonitor()
        
        # Remove delegate to avoid cycles
        if self.window:
            self.window.setDelegate_(None)
    
    def close_window(self):
        """Safely close the window and clean up all resources"""
        debug_log("TextInputWindow: close_window called")
        try:
            # First check if window exists
            if not self.window:
                self.active = False
                debug_log("Window already closed")
                return
            
            # Store local references
            window = self.window
            blur_window = self.blur_window if hasattr(self, 'blur_window') else None
            callback = self.callback
            
            # Stop event monitor FIRST before closing anything
            if self.text_view:
                debug_log("Stopping event monitor")
                try:
                    self.text_view.stopEventMonitor()
                    self.text_view.active = False  # Critical: disable any event processing
                except Exception as e:
                    debug_log(f"Error stopping event monitor: {e}")
            
            # Stop rainbow animation if active
            if hasattr(self, 'rainbow_border') and self.rainbow_border:
                try:
                    self.rainbow_border.stopAnimation()
                except Exception as e:
                    debug_log(f"Error stopping rainbow animation: {e}")
            
            # Clear all references to avoid retain cycles
            self.window.setDelegate_(None)  # Remove delegate first
            
            # Call the callback with None (cancelled)
            if callback:
                try:
                    debug_log("Calling callback with None (window closing)")
                    # Save reference for later to avoid early cleanup
                    temp_callback = callback
                    self.callback = None  # Clear the reference
                    temp_callback(None)  # Use the saved reference
                except Exception as e:
                    debug_log(f"Error calling callback during window close: {e}")
            
            # Now close the windows
            try:
                debug_log("Hiding main window")
                window.orderOut_(None)  # This immediately hides the window
                
                # Close the blur window if it exists
                debug_log("Checking for blur window")
                if blur_window:
                    debug_log("Closing blur window")
                    blur_window.orderOut_(None)
                    blur_window.close()
                    self.blur_window = None
                
                # Ensure the app returns to accessory mode
                app = AppKit.NSApplication.sharedApplication()
                app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
                
                debug_log("Closing main window")
                window.close()  # This actually closes the window
                
                # Important: Clear these references AFTER closing windows
                self.window = None
                self.text_view = None
                self.autocomplete_view = None
                self.scroll_view = None
                self.active = False

            except Exception as e:
                debug_log(f"Error closing window: {e}")
            
            debug_log("Window closed successfully")
        except Exception as e:
            debug_log(f"Error in close_window: {e}")
    
    def dealloc(self):
        """Clean up resources"""
        debug_log("TextInputWindow: dealloc called")
        
        # Stop timer if still active
        if self.activation_timer:
            self.activation_timer.invalidate()
            self.activation_timer = None
        
        # Remove notification observer
        nc = AppKit.NSNotificationCenter.defaultCenter()
        nc.removeObserver_(self)
        
        # Call super dealloc
        objc.super(TextInputWindow, self).dealloc()

class BlurOverlayWindow(AppKit.NSWindow):
    """A window that provides a very subtle full-screen dimming effect"""
    
    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self = objc.super(BlurOverlayWindow, self).initWithContentRect_styleMask_backing_defer_(
            rect, style, backing, defer
        )
        if self is None:
            return None
        
        debug_log("Initializing BlurOverlayWindow")
        
        # Configure the window
        self.setOpaque_(False)
        self.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.setHasShadow_(False)
        self.setLevel_(AppKit.NSStatusWindowLevel - 1)  # Just below the main window
        self.setIgnoresMouseEvents_(True)  # Allow clicking through
        self.setAlphaValue_(0.7)  # Make the whole window slightly transparent
        
        # OPTION 1: Use NSVisualEffectView with ultraLight material for minimal blur
        content_view = AppKit.NSVisualEffectView.alloc().initWithFrame_(rect)
        if hasattr(AppKit.NSVisualEffectMaterial, 'sheet'):  # Use sheet material which is very subtle
            content_view.setMaterial_(AppKit.NSVisualEffectMaterial.sheet)
        else:
            content_view.setMaterial_(AppKit.NSVisualEffectMaterialLight)  # Fallback to light
            
        content_view.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        content_view.setState_(AppKit.NSVisualEffectStateActive)
        content_view.setWantsLayer_(True)
        
        # Add an extremely subtle tint
        overlay = AppKit.NSView.alloc().initWithFrame_(rect)
        overlay.setWantsLayer_(True)
        
        # Just a hint of darkening (1% opacity)
        overlay.layer().setBackgroundColor_(
            AppKit.NSColor.blackColor().colorWithAlphaComponent_(0.3).CGColor()
        )
        content_view.addSubview_(overlay)
        
        self.setContentView_(content_view)
        
        debug_log("BlurOverlayWindow initialized successfully")
        return self
    
    def orderOut_(self, sender):
        """Override to ensure the window is properly hidden"""
        debug_log("BlurOverlayWindow: orderOut_ called")
        objc.super(BlurOverlayWindow, self).orderOut_(sender)
    
    def close(self):
        """Override to ensure the window is properly closed"""
        debug_log("BlurOverlayWindow: close called")
        # objc.super(BlurOverlayWindow, self).close()
        pass