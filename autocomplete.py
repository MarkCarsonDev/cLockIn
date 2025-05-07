import AppKit
import objc
from typing import List, Optional, Callable, Tuple
import Cocoa

class AutocompleteTextView(AppKit.NSTextView):
    """A custom text view subclass to handle keyboard input more directly"""
    def initWithFrame_callback_storage_(self, frame, callback, storage):
        self = objc.super(AutocompleteTextView, self).initWithFrame_(frame)
        if self is None:
            return None
        
        self.callback = callback
        self.storage = storage
        self.category_mode = False
        self.task_mode = False
        self.selected_category = None
        self.autocomplete_options = []
        self.current_autocomplete_index = -1
        
        # Configure the text view
        self.setEditable_(True)
        self.setSelectable_(True)
        self.setRichText_(False)
        self.setFont_(AppKit.NSFont.systemFontOfSize_(14.0))
        self.setTextColor_(AppKit.NSColor.whiteColor())
        self.setDrawsBackground_(True)
        self.setBackgroundColor_(AppKit.NSColor.blackColor().colorWithAlphaComponent_(0.2))
        
        # Use rounded border
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(8.0)
        self.layer().setBorderWidth_(1.0)
        self.layer().setBorderColor_(AppKit.NSColor.whiteColor().colorWithAlphaComponent_(0.3).CGColor())
        
        # Set placeholder
        self.setPlaceholderString_("What are you working on?")
        
        return self
    
    def keyDown_(self, event):
        """Override keyDown to handle special keys"""
        key_code = event.keyCode()
        chars = event.characters()
        print(f"TextView key down: {key_code}, chars: '{chars}'")
        
        # Handle Escape key
        if key_code == 53:  # Escape key
            print("TextView: Escape pressed")
            if self.callback:
                self.callback(None)
            return
        
        # Handle Return/Enter key
        if key_code == 36:  # Return key
            print("TextView: Return pressed")
            text = self.string()
            
            if text.startswith("@") and not self.selected_category:
                # Process category selection
                category_name = text[1:].strip()
                if category_name:
                    self.selected_category = self.storage.add_category(category_name)
                    self.category_mode = False
                    self.task_mode = True
                    # Update display with selected category
                    self.setString_(f"[@{self.selected_category.name}] ")
                    return
            else:
                # Process task
                task_name = text
                if self.selected_category:
                    # Extract task part
                    category_text = f"[@{self.selected_category.name}] "
                    if text.startswith(category_text):
                        task_name = text[len(category_text):].strip()
                        if task_name.startswith("(") and task_name.endswith(")"):
                            task_name = task_name[1:-1]  # Remove parentheses
                
                if task_name:
                    print(f"Creating task: {task_name} with category: {self.selected_category}")
                    task = self.storage.get_or_create_task(task_name, self.selected_category)
                    task.start()  # Start the task immediately
                    self.storage.save()
                    if self.callback:
                        self.callback(task)
                    return
        
        # Handle Tab key for autocomplete
        if key_code == 48:  # Tab key
            print("TextView: Tab pressed")
            # Add autocomplete handling here if needed
            # For now, let it advance through fields
            super(AutocompleteTextView, self).keyDown_(event)
            return
            
        # For all other keys, let the superclass handle it
        super(AutocompleteTextView, self).keyDown_(event)

    def setPlaceholderString_(self, placeholder):
        """Set a placeholder string"""
        if hasattr(self, 'textStorage') and self.textStorage():
            attrs = {
                AppKit.NSForegroundColorAttributeName: AppKit.NSColor.grayColor(),
                AppKit.NSFontAttributeName: self.font()
            }
            self._placeholder = AppKit.NSAttributedString.alloc().initWithString_attributes_(
                placeholder, attrs
            )
        
    def drawRect_(self, rect):
        """Draw the view and placeholder if needed"""
        super(AutocompleteTextView, self).drawRect_(rect)
        
        # Draw placeholder if text is empty
        if hasattr(self, '_placeholder') and len(self.string()) == 0:
            rect = self.bounds()
            rect.origin.x += 5  # Add some padding
            rect.origin.y += 2  # Adjust for baseline
            self._placeholder.drawInRect_(rect)


class TextInputContainer(AppKit.NSView):
    """Container view to hold the text view and manage its layout"""
    def initWithFrame_(self, frame):
        self = objc.super(TextInputContainer, self).initWithFrame_(frame)
        if self is None:
            return None
            
        self.text_view = None
        self.callback = None
        self.storage = None
        
        # Set appearance
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(10.0)
        self.layer().setBorderWidth_(1.0)
        self.layer().setBorderColor_(AppKit.NSColor.whiteColor().colorWithAlphaComponent_(0.3).CGColor())
        self.layer().setBackgroundColor_(AppKit.NSColor.blackColor().colorWithAlphaComponent_(0.2).CGColor())
        
        return self
        
    def setupTextViewWithCallback_storage_(self, callback, storage):
        """Set up the text view with the given callback and storage"""
        self.callback = callback
        self.storage = storage
        
        # Create a scroll view to hold the text view
        scroll_frame = AppKit.NSInsetRect(self.bounds(), 5, 5)
        scroll_view = AppKit.NSScrollView.alloc().initWithFrame_(scroll_frame)
        scroll_view.setBorderType_(AppKit.NSNoBorder)
        scroll_view.setHasVerticalScroller_(True)
        scroll_view.setHasHorizontalScroller_(False)
        scroll_view.setAutohidesScrollers_(True)
        scroll_view.setDrawsBackground_(False)
        
        # Calculate the text view frame
        text_frame = AppKit.NSMakeRect(
            0, 0, 
            AppKit.NSWidth(scroll_frame), 
            AppKit.NSHeight(scroll_frame)
        )
        
        # Create and configure the text view
        self.text_view = AutocompleteTextView.alloc().initWithFrame_callback_storage_(
            text_frame, callback, storage
        )
        
        # Set up the scroll view
        scroll_view.setDocumentView_(self.text_view)
        self.addSubview_(scroll_view)
        
        # Save references
        self.scroll_view = scroll_view
        
        return self.text_view

class AutocompleteTextInput(AppKit.NSTextField):
    # Declare Objective-C instance variables
    callback = objc.ivar('callback')
    storage = objc.ivar('storage')
    category_mode = objc.ivar('category_mode')
    task_mode = objc.ivar('task_mode')
    selected_category = objc.ivar('selected_category')
    autocomplete_options = objc.ivar('autocomplete_options')
    current_autocomplete_index = objc.ivar('current_autocomplete_index')
    autocomplete_container = objc.ivar('autocomplete_container')
    
    @objc.python_method
    def initWithFrame_callback_storage_(self, frame, callback, storage):
        """Initialize the autocomplete text input field"""
        # Convert frame to NSRect if it's a tuple
        if isinstance(frame, tuple):
            # Handle both ((x, y), (width, height)) and (x, y, width, height) formats
            if len(frame) == 2 and isinstance(frame[0], tuple) and isinstance(frame[1], tuple):
                origin, size = frame
                frame = AppKit.NSMakeRect(origin[0], origin[1], size[0], size[1])
            elif len(frame) == 4:
                frame = AppKit.NSMakeRect(frame[0], frame[1], frame[2], frame[3])
        
        # Initialize using the proper super method
        self = objc.super(AutocompleteTextInput, self).initWithFrame_(frame)
        if self is None:
            return None
        
        # Set instance variables
        self.callback = callback
        self.storage = storage
        self.category_mode = False
        self.task_mode = False
        self.selected_category = None
        self.autocomplete_options = []
        self.current_autocomplete_index = -1
        
        # Setup field appearance - modern macOS Spotlight style
        self.setPlaceholderString_("What are you working on?")
        self.setBezeled_(True)
        self.setBezelStyle_(AppKit.NSTextFieldRoundedBezel)  # Use a standard rounded bezel for better input handling
        self.setDrawsBackground_(True)  # CRITICAL: Must be true for input to work
        self.setBackgroundColor_(AppKit.NSColor.textBackgroundColor().colorWithAlphaComponent_(0.8))
        
        # Setup text attributes
        self.setTextColor_(AppKit.NSColor.textColor())
        self.setFont_(AppKit.NSFont.systemFontOfSize_(14.0))
        
        # Enable necessary behaviors for text input
        self.setEditable_(True)
        self.setSelectable_(True)
        self.setEnabled_(True)
        
        # Set action for Enter key
        self.setTarget_(self)
        self.setAction_(self.textFieldAction_)
        
        return self
    
    def textFieldAction_(self, sender):
        """Handle Return/Enter key press"""
        text = self.stringValue()
        print(f"Text field action with text: {text}")
        
        if text:
            # Create the task
            task = self.storage.get_or_create_task(text, None)  # Simple task without category for now
            task.start()
            self.storage.save()
            
            # Call the callback
            if self.callback:
                self.callback(task)
        else:
            # Empty text, just cancel
            if self.callback:
                self.callback(None)
    
    def becomeFirstResponder(self):
        """Called when the field becomes first responder"""
        result = objc.super(AutocompleteTextInput, self).becomeFirstResponder()
        if result:
            print("Text field TRULY gained focus!")
            
            # Force the system to create a field editor for us - this is crucial for input
            field_editor = self.window().fieldEditor_forObject_(True, self)
            if field_editor:
                print("Field editor actually created and ready!")
        return result
    
    def keyDown_(self, event):
        """Handle key events - this is a fallback, most keys should be handled by the field editor"""
        try:
            key_code = event.keyCode()
            chars = event.characters()
            print(f"Direct keyDown in text field: {chars} (code: {key_code})")
            
            # Handle Escape key
            if key_code == 53:  # Escape key
                print("Escape key pressed in text field")
                if self.callback:
                    self.callback(None)
                return
            
            # Let super handle all other keys
            super(AutocompleteTextInput, self).keyDown_(event)
        except Exception as e:
            print(f"Error in keyDown_: {e}")
            super(AutocompleteTextInput, self).keyDown_(event)
    
    def apply_input_styling(self):
        """Apply visual styling to indicate category vs task"""
        text = self.stringValue()
        
        # If we're starting a category with @
        if text.startswith("@") and not self.selected_category:
            # Replace the text with styled version showing brackets
            styled_text = text
            attr_string = self.create_styled_string_for_category_input(styled_text)
            self.setAttributedStringValue_(attr_string)
            
            # Restore cursor position
            if self.currentEditor():
                cursor_pos = self.currentEditor().selectedRange().location
                self.currentEditor().setSelectedRange_(AppKit.NSMakeRange(cursor_pos, 0))
        
        # If we have a selected category, style it properly
        elif self.selected_category:
            # Show the category in brackets with proper styling
            category_part = f"[@{self.selected_category.name}]"
            
            # Get the task part (if any)
            task_part = text[len(category_part):].strip() if text.startswith(category_part) else text
            if task_part and not task_part.startswith("("):
                task_part = f"({task_part})"
            
            # Combine with a space between
            styled_text = category_part
            if task_part:
                styled_text += f" {task_part}"
            
            # Create the attributed string
            attr_string = self.create_styled_string_with_category(self.selected_category, task_part)
            self.setAttributedStringValue_(attr_string)
            
            # Restore cursor position
            if self.currentEditor():
                cursor_pos = self.currentEditor().selectedRange().location
                self.currentEditor().setSelectedRange_(AppKit.NSMakeRange(cursor_pos, 0))
        
        # If we're just entering a task directly (no category)
        elif not text.startswith("@") and text:
            # Style with parentheses
            styled_text = f"({text})"
            attr_string = self.create_styled_string_for_task(text)
            self.setAttributedStringValue_(attr_string)
            
            # Restore cursor position
            if self.currentEditor():
                cursor_pos = self.currentEditor().selectedRange().location
                self.currentEditor().setSelectedRange_(AppKit.NSMakeRange(cursor_pos, 0))
    
    def create_styled_string_for_category_input(self, text):
        """Create an attributed string for category input mode"""
        attr_string = AppKit.NSMutableAttributedString.alloc().initWithString_(text)
        
        # Apply styling to the whole string
        attr_string.addAttribute_value_range_(
            AppKit.NSForegroundColorAttributeName,
            AppKit.NSColor.whiteColor(),
            AppKit.NSMakeRange(0, len(text))
        )
        
        # Enhanced styling to make it look like [@ ... ]
        if len(text) > 1:  # Only if there's more than just @
            bracket_attrs = {
                AppKit.NSForegroundColorAttributeName: AppKit.NSColor.lightGrayColor(),
                AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(14.0)
            }
            
            # Create temporary string to insert brackets visually
            temp_string = AppKit.NSMutableAttributedString.alloc().initWithString_(f"[{text}]")
            
            # Style the brackets
            for attr, value in bracket_attrs.items():
                temp_string.addAttribute_value_range_(attr, value, AppKit.NSMakeRange(0, 1))
                temp_string.addAttribute_value_range_(attr, value, AppKit.NSMakeRange(len(text) + 1, 1))
            
            return temp_string
        
        return attr_string
    
    def create_styled_string_with_category(self, category, task_text=""):
        """Create an attributed string showing selected category and task"""
        category_text = f"[@{category.name}]"
        full_text = category_text
        
        if task_text:
            if not task_text.startswith("("):
                task_text = f"({task_text})"
            full_text += f" {task_text}"
        
        attr_string = AppKit.NSMutableAttributedString.alloc().initWithString_(full_text)
        
        # Style the category part (with color)
        category_color = AppKit.NSColor.colorWithHexString_(category.color)
        
        # Category brackets styling
        bracket_range_start = AppKit.NSMakeRange(0, 1)  # [
        bracket_range_end = AppKit.NSMakeRange(len(category_text) - 1, 1)  # ]
        
        attr_string.addAttribute_value_range_(
            AppKit.NSForegroundColorAttributeName,
            AppKit.NSColor.lightGrayColor(),
            bracket_range_start
        )
        attr_string.addAttribute_value_range_(
            AppKit.NSForegroundColorAttributeName,
            AppKit.NSColor.lightGrayColor(),
            bracket_range_end
        )
        
        # Category name styling (inside brackets)
        category_range = AppKit.NSMakeRange(1, len(category_text) - 2)
        attr_string.addAttribute_value_range_(
            AppKit.NSForegroundColorAttributeName,
            category_color,
            category_range
        )
        attr_string.addAttribute_value_range_(
            AppKit.NSBackgroundColorAttributeName,
            category_color.colorWithAlphaComponent_(0.2),
            category_range
        )
        
        # Style the task part if present
        if task_text:
            task_start = len(category_text) + 1  # +1 for the space
            
            # Task parentheses styling
            if task_text.startswith("(") and task_text.endswith(")"):
                paren_range_start = AppKit.NSMakeRange(task_start, 1)  # (
                paren_range_end = AppKit.NSMakeRange(len(full_text) - 1, 1)  # )
                
                attr_string.addAttribute_value_range_(
                    AppKit.NSForegroundColorAttributeName,
                    AppKit.NSColor.lightGrayColor(),
                    paren_range_start
                )
                attr_string.addAttribute_value_range_(
                    AppKit.NSForegroundColorAttributeName,
                    AppKit.NSColor.lightGrayColor(),
                    paren_range_end
                )
                
                # Task name styling (inside parentheses)
                task_name_range = AppKit.NSMakeRange(task_start + 1, len(task_text) - 2)
                attr_string.addAttribute_value_range_(
                    AppKit.NSForegroundColorAttributeName,
                    AppKit.NSColor.whiteColor(),
                    task_name_range
                )
                
                # Light gray background for task
                attr_string.addAttribute_value_range_(
                    AppKit.NSBackgroundColorAttributeName,
                    AppKit.NSColor.darkGrayColor().colorWithAlphaComponent_(0.3),
                    task_name_range
                )
        
        return attr_string
    
    def create_styled_string_for_task(self, text):
        """Create an attributed string for task input (no category)"""
        # Add parentheses around the task text
        full_text = f"({text})"
        attr_string = AppKit.NSMutableAttributedString.alloc().initWithString_(full_text)
        
        # Style the parentheses
        paren_range_start = AppKit.NSMakeRange(0, 1)  # (
        paren_range_end = AppKit.NSMakeRange(len(full_text) - 1, 1)  # )
        
        attr_string.addAttribute_value_range_(
            AppKit.NSForegroundColorAttributeName,
            AppKit.NSColor.lightGrayColor(),
            paren_range_start
        )
        attr_string.addAttribute_value_range_(
            AppKit.NSForegroundColorAttributeName,
            AppKit.NSColor.lightGrayColor(),
            paren_range_end
        )
        
        # Style the task name
        task_range = AppKit.NSMakeRange(1, len(text))
        attr_string.addAttribute_value_range_(
            AppKit.NSForegroundColorAttributeName,
            AppKit.NSColor.whiteColor(),
            task_range
        )
        attr_string.addAttribute_value_range_(
            AppKit.NSBackgroundColorAttributeName,
            AppKit.NSColor.darkGrayColor().colorWithAlphaComponent_(0.3),
            task_range
        )
        
        return attr_string
    
    def handle_category_tab(self):
        """Handle tab key in category mode to cycle through categories"""
        # Get all categories for autocomplete
        categories = self.storage.get_categories()
        if not categories:
            return
        
        # Initialize options if empty
        if not self.autocomplete_options:
            self.autocomplete_options = categories
            self.current_autocomplete_index = -1
        
        # Cycle to the next option
        self.current_autocomplete_index = (self.current_autocomplete_index + 1) % len(self.autocomplete_options)
        selected_category = self.autocomplete_options[self.current_autocomplete_index]
        
        # Update the text field with the selected category
        self.stringValue_(f"@{selected_category.name}")
        self.apply_input_styling()
        
        # Update the table selection
        self.autocomplete_table.selectRowIndexes_byExtendingSelection_(
            AppKit.NSIndexSet.indexSetWithIndex_(self.current_autocomplete_index),
            False
        )
        
        # Scroll to the selected row
        self.autocomplete_table.scrollRowToVisible_(self.current_autocomplete_index)
        
        # Position cursor at the end
        if self.currentEditor():
            self.currentEditor().setSelectedRange_(AppKit.NSMakeRange(len(self.stringValue()), 0))
    
    def handle_task_tab(self):
        """Handle tab key in task mode to cycle through tasks"""
        # Get the relevant tasks based on selected category
        if self.selected_category:
            tasks = self.storage.get_tasks(self.selected_category)
        else:
            tasks = self.storage.get_tasks()  # Uncategorized tasks
        
        if not tasks:
            return
        
        # Initialize options if empty
        if not self.autocomplete_options:
            self.autocomplete_options = tasks
            self.current_autocomplete_index = -1
        
        # Cycle to the next option
        self.current_autocomplete_index = (self.current_autocomplete_index + 1) % len(self.autocomplete_options)
        selected_task = self.autocomplete_options[self.current_autocomplete_index]
        
        # Update the text field with the selected task
        if self.selected_category:
            # When category is already selected, just update the task part
            self.stringValue_(f"[@{self.selected_category.name}] ({selected_task.name})")
        else:
            # When no category is selected, just show the task
            self.selected_category = selected_task.category  # In case this task has a category
            if selected_task.category:
                self.stringValue_(f"[@{selected_task.category.name}] ({selected_task.name})")
            else:
                self.stringValue_(f"({selected_task.name})")
        
        # Update styling
        self.apply_input_styling()
        
        # Update the table selection
        self.autocomplete_table.selectRowIndexes_byExtendingSelection_(
            AppKit.NSIndexSet.indexSetWithIndex_(self.current_autocomplete_index),
            False
        )
        
        # Scroll to the selected row
        self.autocomplete_table.scrollRowToVisible_(self.current_autocomplete_index)
        
        # Position cursor at the end
        if self.currentEditor():
            self.currentEditor().setSelectedRange_(AppKit.NSMakeRange(len(self.stringValue()), 0))
    
    def update_category_autocomplete(self):
        """Update autocomplete options for categories"""
        text = self.stringValue()
        if text.startswith("@"):
            # Extract the search text (after @ symbol)
            search_text = text[1:].strip().lower()
            categories = self.storage.get_categories()
            
            # Filter categories by search text
            if search_text:
                self.autocomplete_options = [c for c in categories if search_text in c.name.lower()]
            else:
                self.autocomplete_options = categories
            
            self.current_autocomplete_index = -1
            self.update_autocomplete_view()
    
    def update_task_autocomplete(self):
        """Update autocomplete options for tasks"""
        text = self.stringValue()
        
        # If we have a selected category, get tasks for that category
        if self.selected_category:
            category_text = f"[@{self.selected_category.name}]"
            if text.startswith(category_text):
                # Extract the search text (after category part)
                search_text = text[len(category_text):].strip().lower()
                if search_text.startswith("(") and search_text.endswith(")"):
                    search_text = search_text[1:-1]  # Remove parentheses
                
                tasks = self.storage.get_tasks(self.selected_category)
                
                # Filter tasks by search text
                if search_text:
                    self.autocomplete_options = [t for t in tasks if search_text in t.name.lower()]
                else:
                    self.autocomplete_options = tasks
            else:
                self.autocomplete_options = []
        else:
            # No category selected, search uncategorized tasks
            search_text = text.strip().lower()
            if search_text.startswith("(") and search_text.endswith(")"):
                search_text = search_text[1:-1]  # Remove parentheses
            
            tasks = self.storage.get_tasks()  # Uncategorized tasks
            
            # Filter tasks by search text
            if search_text:
                self.autocomplete_options = [t for t in tasks if search_text in t.name.lower()]
            else:
                self.autocomplete_options = tasks
        
        self.current_autocomplete_index = -1
        self.update_autocomplete_view()
    
    def update_autocomplete_view(self):
        """Update the autocomplete dropdown view"""
        if self.autocomplete_options:
            # Update the table delegate with new options
            self.table_delegate.options = self.autocomplete_options
            self.autocomplete_table.reloadData()
            
            # Show the autocomplete container
            self.autocomplete_container.setHidden_(False)
        else:
            # Hide the container if no options
            self.autocomplete_container.setHidden_(True)
    
    def update_display_with_selected_category(self):
        """Update the text field with the selected category"""
        if self.selected_category:
            # Format with visual styling (brackets)
            self.stringValue_(f"[@{self.selected_category.name}] ")
            self.apply_input_styling()
            
            # Position cursor after the category part
            if self.currentEditor():
                self.currentEditor().setSelectedRange_(AppKit.NSMakeRange(len(self.stringValue()), 0))


class AutocompleteTableDelegate(AppKit.NSObject):
    # Declare Objective-C instance variables
    options = objc.ivar('options')
    text_input = objc.ivar('text_input')
    
    @objc.python_method
    def init(self):
        """Initialize the table delegate"""
        self = objc.super(AutocompleteTableDelegate, self).init()
        if self is None:
            return None
        self.options = []
        self.text_input = None
        return self
    
    # Data source methods
    def numberOfRowsInTableView_(self, tableView):
        return len(self.options)
    
    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        if 0 <= row < len(self.options):
            option = self.options[row]
            if hasattr(option, 'name'):
                return option.name
        return ""
    
    # Delegate methods
    def tableView_viewForTableColumn_row_(self, tableView, column, row):
        if 0 <= row < len(self.options):
            option = self.options[row]
            
            # Create a cell view
            identifier = "AutocompleteCell"
            cell_view = tableView.makeViewWithIdentifier_owner_(identifier, self)
            
            if cell_view is None:
                # Create a new cell if none exists
                cell_view = AppKit.NSTableCellView.alloc().init()
                cell_view.setIdentifier_(identifier)
                
                # Create the text field for the cell
                text_field = AppKit.NSTextField.alloc().initWithFrame_(
                    AppKit.NSMakeRect(0, 0, tableView.frame().size.width, 20)
                )
                text_field.setBezeled_(False)
                text_field.setDrawsBackground_(False)
                text_field.setEditable_(False)
                text_field.setSelectable_(False)
                
                # Add the text field to the cell
                cell_view.addSubview_(text_field)
                cell_view.setTextField_(text_field)
            
            # Configure the cell
            text_field = cell_view.textField()
            
            # Set the text
            if hasattr(option, 'name'):
                text = option.name
                
                # For categories, add color indicator
                if hasattr(option, 'color') and option.color:
                    # Create attributed string with color
                    attr_text = AppKit.NSMutableAttributedString.alloc().initWithString_(text)
                    color = AppKit.NSColor.colorWithHexString_(option.color)
                    
                    # Apply color styling
                    attr_text.addAttribute_value_range_(
                        AppKit.NSForegroundColorAttributeName,
                        color,
                        AppKit.NSMakeRange(0, len(text))
                    )
                    
                    text_field.setAttributedStringValue_(attr_text)
                else:
                    text_field.setStringValue_(text)
            else:
                text_field.setStringValue_("")
            
            return cell_view
        
        return None
    
    def tableViewSelectionDidChange_(self, notification):
        # Handle selection change in the table
        table_view = notification.object()
        selected_row = table_view.selectedRow()
        
        if selected_row >= 0 and selected_row < len(self.options):
            selected_option = self.options[selected_row]
            
            # Update the text input based on selection
            if self.text_input:
                if self.text_input.category_mode:
                    # Category selection
                    if hasattr(selected_option, 'name'):
                        self.text_input.stringValue_(f"@{selected_option.name}")
                        self.text_input.apply_input_styling()
                else:
                    # Task selection
                    if hasattr(selected_option, 'name'):
                        if hasattr(selected_option, 'category') and selected_option.category:
                            # Task with category
                            self.text_input.selected_category = selected_option.category
                            self.text_input.stringValue_(f"[@{selected_option.category.name}] ({selected_option.name})")
                        else:
                            # Task without category
                            self.text_input.stringValue_(f"({selected_option.name})")
                        
                        self.text_input.apply_input_styling()
                
                # Position cursor at the end
                if self.text_input.currentEditor():
                    self.text_input.currentEditor().setSelectedRange_(
                        AppKit.NSMakeRange(len(self.text_input.stringValue()), 0)
                    )


# Extension to NSColor for creating colors from hex strings
# Helper function for creating NSColor from hex
def color_with_hex_string(cls, hex_string):
    """Create an NSColor from a hex string (e.g., '#FF0000')"""
    if not hex_string or not hex_string.startswith('#'):
        return AppKit.NSColor.whiteColor()
    
    # Remove # prefix
    hex_string = hex_string[1:]
    
    # Parse hex values
    r_hex = hex_string[0:2]
    g_hex = hex_string[2:4]
    b_hex = hex_string[4:6]
    
    try:
        r = int(r_hex, 16) / 255.0
        g = int(g_hex, 16) / 255.0
        b = int(b_hex, 16) / 255.0
        
        return AppKit.NSColor.colorWithRed_green_blue_alpha_(r, g, b, 1.0)
    except:
        return AppKit.NSColor.whiteColor()

# Add the method to NSColor class
AppKit.NSColor.colorWithHexString_ = classmethod(color_with_hex_string)