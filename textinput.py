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
        """Stop monitoring key events"""
        if not self.running:
            return
        
        try:
            if self.event_tap:
                # Disable the event tap
                Quartz.CGEventTapEnable(self.event_tap, False)
                
                # Remove source from run loop
                if self.run_loop_source:
                    Quartz.CFRunLoopRemoveSource(
                        Quartz.CFRunLoopGetCurrent(),
                        self.run_loop_source,
                        Quartz.kCFRunLoopCommonModes
                    )
                    del self.run_loop_source
                    self.run_loop_source = None
                
                # Release the event tap
                del self.event_tap
                self.event_tap = None
            
            self.running = False
            debug_log("Event monitor stopped")
        
        except Exception as e:
            debug_log(f"Error stopping event monitor: {e}")
    
    def _event_callback(self, proxy, event_type, event, refcon):
        """Callback for CGEventTap to handle key events"""
        try:
            if event_type != Quartz.kCGEventKeyDown:
                return event
            
            # Get keycode and modifiers from the event
            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            chars = Cocoa.NSEvent.eventWithCGEvent_(event).characters()
            
            # Track an internal state
            # We'll set this when the window appears and clear it when closed/cancelled
            if (not self.target or 
                not hasattr(self.target, 'active') or 
                not self.target.active):
                return event
            
            debug_log(f"Key event: keycode={keycode}, chars='{chars}'")
            
            # Forward to target if it exists and has process_key_event method
            if hasattr(self.target, 'process_key_event'):
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
        
        # Set up insertion point color
        self.setInsertionPointColor_(AppKit.NSColor.textColor())
        
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
    
    def dealloc(self):
        """Clean up resources"""
        debug_log("CategoryTaskView: dealloc called")
        # Stop event monitor
        if self.event_monitor:
            self.event_monitor.stop()

        
        self.active = False
        
        # Remove notification observer
        nc = AppKit.NSNotificationCenter.defaultCenter()
        nc.removeObserver_(self)
        
        objc.super(CategoryTaskView, self).dealloc()
    
    def startEventMonitor(self):
        """Start monitoring keyboard events"""
        if self.event_monitor:
            result = self.event_monitor.start()
            debug_log(f"Event monitor start result: {result}")
            return result
        return False
    
    def stopEventMonitor(self):
        """Stop monitoring keyboard events"""
        if self.event_monitor:
            self.event_monitor.stop()
    
    def process_key_event(self, keycode, chars, event):
        """Process a key event from the global event monitor"""
        debug_log(f"Process key event: keycode={keycode}, chars='{chars}'")
        
        # IMPORTANT: We're removing the window.isKeyWindow check since we're 
        # using a global event monitor and we want to process events regardless

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
            window = self.window()
            debug_log("Escape key detected - closing window directly")
            if window and hasattr(window, 'close'):
                debug_log("Calling self.close() directly")
                window.close()
            elif self.callback:
                debug_log("Calling callback with None for window close")
                self.callback(None)
            return True  # Consume the event
        

        # Handle Backspace/Delete key with improved behavior
        if keycode == 51:  # Backspace key
            debug_log("Backspace key detected")
            
            # Get current text and selection
            text = self.string()
            selected_range = self.selectedRange()
            
            # Case 1: Selection exists - delete it
            if selected_range.length > 0:
                new_text = text[:selected_range.location] + text[selected_range.location + selected_range.length:]
                self.setString_(new_text)
                self.setSelectedRange_(AppKit.NSMakeRange(selected_range.location, 0))
                self.updateTextStyling()
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
            
            # Case 3: At the "@" character in category mode
            if self.category_mode and text.startswith("@") and selected_range.location == 1:
                # Exit category mode
                self.category_mode = False
                self.setString_(text[1:].lstrip())
                self.updateTextStyling()
                return True
            
            # Case 4: Standard backspace - delete previous character
            if selected_range.location > 0:
                new_text = text[:selected_range.location - 1] + text[selected_range.location:]
                self.setString_(new_text)
                self.setSelectedRange_(AppKit.NSMakeRange(selected_range.location - 1, 0))
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
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.placeholderTextColor()
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
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.placeholderTextColor()
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
        
        # Filter categories by search text if present
        if search_text:
            filtered_categories = [c for c in categories if search_text in c.name.lower()]
        else:
            filtered_categories = categories
        
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
        self.border_width = 2.0
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
            
            # Create color for this segment
            color = AppKit.NSColor.colorWithCalibratedHue_saturation_brightness_alpha_(
                hue, 0.7, 0.9, 0.8  # Pastel colors (higher brightness, lower saturation)
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
            color = AppKit.NSColor.colorWithCalibratedHue_saturation_brightness_alpha_(
                (i / segments + self.hue_offset) % 1.0,
                0.8,  # saturation
                0.9,  # brightness
                1.0   # alpha
            )
            color.set()
            AppKit.NSBezierPath.strokeLineFromPoint_toPoint_(
                AppKit.NSMakePoint(x1, y1),
                AppKit.NSMakePoint(x2, y2)
            )

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
        
        # Try to create the window
        success = self.createWindow()
        if not success:
            debug_log("TextInputWindow: createWindow failed")
            return None
        
        debug_log("TextInputWindow: initialization complete")
        return self

    def createWindow(self):
        """Create the input window with a modern Spotlight-style appearance and rainbow border"""
        try:
            debug_log("TextInputWindow: createWindow called")

            # Get screen dimensions
            screen_rect = AppKit.NSScreen.mainScreen().frame()
            window_width = 500
            window_height = 60

            # Position window near the top of the screen
            window_x = (screen_rect.size.width - window_width) / 2
            window_y = screen_rect.size.height * 0.8  # Position at 80% from bottom
            window_frame = AppKit.NSMakeRect(window_x, window_y, window_width, window_height)

            # Always use NSPanel
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
            # self.window.setLevel_(Quartz.CGShieldingWindowLevel())
            # self.window.setLevel_(AppKit.NSFloatingWindowLevel)
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

            # Rainbow border
            self.rainbow_border = RainbowBorderView.alloc().initWithFrame_(
                AppKit.NSMakeRect(-2, -2, window_width + 4, window_height + 4)
            )
            container.addSubview_(self.rainbow_border)

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

            text_frame = AppKit.NSMakeRect(0, 0, scroll_frame.size.width, scroll_frame.size.height)
            self.text_view = CategoryTaskView.alloc().initWithFrame_callback_storage_(
                text_frame, self.callback, self.storage
            )
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
            self.text_view.startEventMonitor()

            # Start rainbow animation
            self.rainbow_border.startAnimation()

            # Show and focus
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            self.window.orderFrontRegardless()
            self.window.makeKeyWindow()
            self.window.makeKeyAndOrderFront_(None)
            self.window.makeFirstResponder_(self.text_view)

            # Ensure focus persists briefly
            AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.1, self, 'ensureFocus:', None, False
            )

            debug_log("TextInputWindow: Window created successfully")
            return True
        except Exception as e:
            debug_log(f"TextInputWindow: Error creating window: {e}")
            return False
        
    def canBecomeKeyWindow(self):
        return True
    def canBecomeMainWindow(self):
        return True

    def windowDidResignKey_(self, notification):
        # Close on focus loss as if ESC pressed
        print("BRUH")
        self.close_window()
    
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
        debug_log("Window lost focus—closing input")  
        """Called when window loses focus"""
        self.close_window()
        if notification.object() == self.window:
            debug_log("Window lost focus")
            self.window_focused = False
            window = self.window
            # close window
            if window and hasattr(window, "close"):
                window.close()

        if self.text_view:
            self.text_view.stopEventMonitor()
        
        # Pause rainbow animation when not focused
        if self.rainbow_border:
            self.rainbow_border.stopAnimation()
    
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
        """Safely close the window"""
        debug_log("TextInputWindow: close_window called")
        try:
            # First check if window exists
            if not self.window:
                debug_log("Window already closed")
                return
            
            # Store local references
            window = self.window
            callback = self.callback
            
            # Stop event monitor
            if self.text_view:
                try:
                    self.text_view.stopEventMonitor()
                except Exception as e:
                    debug_log(f"Error stopping event monitor: {e}")
            
            # Clear all references to avoid retain cycles
            self.window = None
            self.text_view = None
            self.autocomplete_view = None
            self.scroll_view = None
            self.callback = None  # Clear the callback reference
            
            # Call the callback after clearing references
            if callback:
                try:
                    debug_log("Calling callback with None (window closing)")
                    callback(None)  # Use the stored reference
                except Exception as e:
                    debug_log(f"Error calling callback during window close: {e}")
            
            # Now close the window using orderOut instead of close for more reliability
            try:
                debug_log("Closing window using orderOut")
                window.orderOut_(None)  # This immediately hides the window
                window.close()  # This actually closes the window
            except Exception as e:
                debug_log(f"Error closing window: {e}")
            
            debug_log("Window closed successfully")
        except Exception as e:
            debug_log(f"Error in close_window: {e}")