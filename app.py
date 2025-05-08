import rumps
import datetime
import os
import pwd
import json
import objc
from dateutil import parser
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import subprocess
from Cocoa import NSTextField, NSApp, NSWindow, NSRect, NSButton, NSObject, NSBackingStoreBuffered, NSPoint, NSWindowCollectionBehaviorMoveToActiveSpace, NSMenu, NSMenuItem
from Quartz import CGShieldingWindowLevel
import AppKit
from pypresence import Presence
from dotenv import load_dotenv

# Import custom components
from models import Category, Task, DataStorage
from textinput import TextInputWindow
from shortcut_manager import ShortcutManager
from csv_export import CSVExporter

# Load environment variables
load_dotenv('.env.local')
try:
    DISCORD_APP_CLIENT_ID = os.getenv('DISCORD_APP_CLIENT_ID')
except:
    DISCORD_APP_CLIENT_ID = None

# Get macOS username
OS_USERNAME = pwd.getpwuid(os.getuid()).pw_name

# Path to the OAuth 2.0 client secrets file downloaded from the Google Cloud Console
CLIENT_SECRETS_FILE = 'google_client_secrets.json'
SCOPES = ['openid', 'https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/userinfo.email']
CREDENTIALS_FILE = 'token.json'
LAUNCH_AGENT_FILE = os.path.expanduser(f'~/Library/LaunchAgents/com.{OS_USERNAME}.clockinapp.plist')
SHELL_SCRIPT_FILE = os.path.abspath(f'run_clockin_app.sh')
DEFAULT_TITLE = ""
CALENDAR_TITLE = "cLockIn"

# # Global shortcut key combination
SHORTCUT_KEY = 'T'
SHORTCUT_MODIFIERS = ['CTRL', 'SHIFT', 'CMD']


class MenuApp(rumps.App):
    def __init__(self):
        super(MenuApp, self).__init__("cLockIn", quit_button=None)
        if DEFAULT_TITLE != "": self.title = DEFAULT_TITLE
        self.icon = "icon.png"
        self.credentials = None
        self.calendar_service = None
        self.current_event = None
        self.user_email = None
        self.text_input_window = None
        self.calendar_id = None
        
        # Initialize the data storage
        self.storage = DataStorage()
        
        # Initialize the CSV exporter
        self.csv_exporter = CSVExporter(self.storage)
        
        # Initialize the shortcut manager
        self.shortcut_manager = ShortcutManager()

        # Discord integration
        self.discord_enabled = bool(DISCORD_APP_CLIENT_ID)
        self.rpc = None

        if self.discord_enabled:
            try:
                self.rpc = Presence(DISCORD_APP_CLIENT_ID)
                try:
                    self.rpc.connect()
                    print("Connected to Discord")
                except Exception as e:
                    print(f"Failed to connect to Discord: {e}")
                    self.discord_enabled = False
                    self.rpc = None
            except Exception as e:
                print(f"Failed to initialize Discord presence: {e}")
                self.discord_enabled = False
                self.rpc = None


        print("Initializing enhanced application...")
        self.load_credentials()
        
        # CRITICAL FIX: Deactivate any active tasks from previous sessions
        self.suspend_active_tasks_on_startup()

        # Setup menu items
        self.sign_in_item = rumps.MenuItem("Sign in with Google", callback=self.sign_in_with_google)
        self.start_item = rumps.MenuItem("⏵", callback=self.start_event)
        self.pause_item = rumps.MenuItem("⏸", callback=self.pause_event)
        self.stop_item = rumps.MenuItem("⏹", callback=self.stop_event)

        # Preferences menu items
        self.run_at_startup_item = rumps.MenuItem("Run at Startup", callback=self.toggle_run_at_startup)
        self.run_at_startup_item.state = self.is_run_at_startup_enabled()

        self.show_in_discord_item = rumps.MenuItem("Show in Discord", callback=self.toggle_discord_presence)
        self.show_in_discord_item.state = self.discord_enabled

        self.view_json_item = rumps.MenuItem("View Time Entry Data", callback=self.open_json_file)
        
        self.keyboard_shortcut_item = rumps.MenuItem(
            f"Keyboard Shortcut ({' + '.join(['⌘', '⇧', '⌃'])} + {SHORTCUT_KEY})", 
            callback=self.toggle_keyboard_shortcut
        )
        self.keyboard_shortcut_item.state = True
        
        self.sign_out_item = rumps.MenuItem("Sign Out", callback=self.sign_out)

        self.preferences_menu = rumps.MenuItem("Preferences")
        self.preferences_menu.add(self.run_at_startup_item)
        self.preferences_menu.add(self.show_in_discord_item)
        self.preferences_menu.add(self.keyboard_shortcut_item)
        self.preferences_menu.add(self.sign_out_item)
        self.preferences_menu.add(self.view_json_item)

        # Base menu
        self.menu = [
            self.sign_in_item, 
            None,  # Separator
            self.preferences_menu, 
            None,  # Separator
            rumps.MenuItem("Quit", callback=rumps.quit_application)
        ]

        # Register the global keyboard shortcut
        self.register_keyboard_shortcut()
        
        # Initialize UI
        self.update_button_states()
        self.timer = rumps.Timer(self.update_title, 15)  # Timer to update the title 
        self.timer.start()
        
        print("Enhanced application initialized.")
        self.set_accessory_mode()

    def suspend_active_tasks_on_startup(self):
        """Suspend any active tasks from previous sessions to prevent auto-restart"""
        try:
            active_task = self.storage.get_active_task()
            if active_task:
                print(f"Found active task from previous session: {active_task.name}")
                active_task.pause()  # This ends the current time entry
                self.storage.save()
                print(f"Suspended active task: {active_task.name}")
        except Exception as e:
            print(f"Error suspending active tasks: {e}")

    def set_accessory_mode(self):
        """Set application to accessory mode (icon only in menu bar)"""
        print("Setting application to accessory mode...")
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        print("Application set to accessory mode.")

    def unregister_keyboard_shortcut(self):
        """Unregister the global keyboard shortcut"""
        self.shortcut_manager.unregister_all()

    def toggle_keyboard_shortcut(self, sender):
        """Toggle the keyboard shortcut on/off"""
        sender.state = not sender.state
        if sender.state:
            self.register_keyboard_shortcut()
        else:
            self.unregister_keyboard_shortcut()


    def load_credentials(self):
        """Load Google API credentials"""
        print("Loading credentials...")
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE, 'r') as token:
                self.credentials = Credentials.from_authorized_user_info(json.load(token), SCOPES)
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                except Exception as e:
                    print(f"Failed to refresh credentials: {e}")
                    self.credentials = None
            if not self.credentials or not self.credentials.valid:
                self.sign_in_with_google(None)
            else:
                self.calendar_service = build('calendar', 'v3', credentials=self.credentials)
                self.user_email = self.get_user_email()
                self.create_clockin_calendar()
        print("Credentials loaded.")

    def save_credentials(self):
        """Save Google API credentials"""
        print("Saving credentials...")
        with open(CREDENTIALS_FILE, 'w') as token:
            token.write(self.credentials.to_json())
        print("Credentials saved.")

    def sign_out(self, _):
        """Sign out of Google account"""
        print("Signing out...")
        if os.path.exists(CREDENTIALS_FILE):
            os.remove(CREDENTIALS_FILE)
        self.credentials = None
        self.calendar_service = None
        self.user_email = None
        self.update_button_states()
        rumps.notification("Signed out", "Successfully signed out of Google", "")
        print("Signed out.")

    def update_button_states(self):
        """Update the menu items based on current state"""
        print("Updating button states...")
        self.menu.clear()
        
        # Add sign in/user info item
        if self.credentials and self.credentials.valid:
            self.sign_in_item.title = self.user_email if self.user_email else "Signed In"
            self.sign_in_item.set_callback(None)
            self.menu.add(self.sign_in_item)
            
            # Add separator before task controls
            self.menu.add(None)
            
            # Get active task from storage if any
            active_task = self.storage.get_active_task()
            
            # If we have an active task from storage
            if active_task:
                # Show pause and stop buttons
                self.menu.add(rumps.MenuItem(f"Pause '{active_task.name}'", callback=self.pause_event))
                self.menu.add(rumps.MenuItem(f"Stop '{active_task.name}'", callback=self.stop_event))
            else:
                # Show start button if no active task
                self.menu.add(rumps.MenuItem("Start New Task", callback=self.show_task_input))
            
            # Add separator before task list
            self.menu.add(None)
            
            # Add recent tasks section if we have any tasks
            all_tasks = self.storage.get_all_tasks()
            if all_tasks:
                recent_tasks = sorted(
                    [t for t in all_tasks if t.time_entries], 
                    key=lambda t: t.time_entries[-1].start_time if t.time_entries else datetime.datetime.min,
                    reverse=True
                )[:5]  # Get up to 5 most recent
                
                if recent_tasks:
                    recent_tasks_menu = rumps.MenuItem("Recent Tasks")
                    
                    for task in recent_tasks:
                        # Format task name with category if present
                        task_name = task.name
                        if task.category:
                            task_name = f"@{task.category.name}/{task.name}"
                        
                        # Calculate total duration
                        total_seconds = task.full_duration()
                        hours = int(total_seconds // 3600)
                        minutes = int((total_seconds % 3600) // 60)
                        
                        # Create menu item with time info
                        task_item = rumps.MenuItem(
                            f"{task_name} ({hours}h {minutes}m)",
                            callback=lambda x, t=task: self.start_existing_task(t)
                        )
                        recent_tasks_menu.add(task_item)
                    
                    self.menu.add(recent_tasks_menu)
                    self.menu.add(None)  # Add separator after recent tasks
            
            # Add categories section
            categories = self.storage.get_categories()
            if categories:
                categories_menu = rumps.MenuItem("Categories")
                
                for category in categories:
                    category_menu = rumps.MenuItem(category.name)
                    
                    # Add tasks for this category
                    tasks = self.storage.get_tasks(category)
                    for task in tasks:
                        # Calculate total duration
                        total_seconds = task.total_duration()
                        hours = int(total_seconds // 3600)
                        minutes = int((total_seconds % 3600) // 60)
                        
                        task_item = rumps.MenuItem(
                            f"{task.name} ({hours}h {minutes}m)",
                            callback=lambda x, t=task: self.start_existing_task(t)
                        )
                        category_menu.add(task_item)
                    
                    if tasks:
                        category_menu.add(None)  # Add separator before export
                    
                    # Add export options for this category
                    export_menu = rumps.MenuItem("Export Timesheet")
                    
                    export_menu.add(rumps.MenuItem(
                        "Simple CSV", 
                        callback=lambda x, c=category: self.export_simple_csv(c)
                    ))
                    
                    export_menu.add(rumps.MenuItem(
                        "Detailed CSV", 
                        callback=lambda x, c=category: self.export_detailed_csv(c)
                    ))
                    
                    export_menu.add(rumps.MenuItem(
                        "Weekly CSV", 
                        callback=lambda x, c=category: self.export_weekly_csv(c)
                    ))
                    
                    category_menu.add(export_menu)
                    categories_menu.add(category_menu)
                
                self.menu.add(categories_menu)
                self.menu.add(None)  # Add separator after categories
        else:
            # Not signed in
            self.sign_in_item.title = "Sign in with Google"
            self.sign_in_item.set_callback(self.sign_in_with_google)
            self.menu.add(self.sign_in_item)
        
        # Add preferences and quit
        self.menu.add(self.preferences_menu)
        self.menu.add(None)  # Separator
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))
        
        # Update the title
        self.update_title()
        print("Button states updated.")

    def update_title(self, _=None):
        """Update the menu bar title based on current task"""
        active_task = self.storage.get_active_task()
        
        if not active_task:
            self.title = DEFAULT_TITLE
            if self.rpc and self.discord_enabled:
                self.rpc.clear()
            return
        
        print("Updating title...")
        
        # Get the current time entry
        current_entry = active_task.current_entry()
        if current_entry:
            # Calculate elapsed time
            elapsed_time = datetime.datetime.now(datetime.timezone.utc) - current_entry.start_time
            hours, remainder = divmod(elapsed_time.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            
            # Calculate total time including previous entries
            total_seconds = active_task.full_duration()
            total_hours = int(total_seconds // 3600)
            total_minutes = int((total_seconds % 3600) // 60)
            
            # Format the title
            if total_hours > hours or total_minutes > minutes:
                # Show both current session and total time
                self.title = (
                    f"{active_task.name} • {int(hours)}h {int(minutes)}m "
                    f"(total: {total_hours}h {total_minutes}m)"
                ) if hours >= 1 else (
                    f"{active_task.name} • {int(minutes)}m "
                    f"(total: {total_hours}h {total_minutes}m)"
                )
            else:
                # Just show current session time (same as total)
                self.title = (
                    f"{active_task.name} • {int(hours)}h {int(minutes)}m"
                ) if hours >= 1 else (
                    f"{active_task.name} • {int(minutes)}m"
                )

                    # Update Discord presence
            if self.rpc and self.discord_enabled:
                try:
                    details = active_task.name
                    if active_task.category:
                        details = f"@{active_task.category.name}/{active_task.name}"
                    
                    self.rpc.update(
                        details=details[:128],  # Discord has a character limit
                        state=f"Total: {total_hours}h {total_minutes}m",
                        start=int(current_entry.start_time.timestamp()),
                        large_image="icon",  # Replace with image key of choice
                        large_text="Locked in",
                    )
                except Exception as e:
                    print(f"Error updating Discord presence: {e}")
                    # Don't disable Discord presence on error, just log it
        else:
            self.title = DEFAULT_TITLE
            if self.rpc and self.discord_enabled:
                self.rpc.clear()
                
        print(f"Title updated to: {self.title}")

    def sign_in_with_google(self, _):
        """Sign in with Google account with improved error handling"""
        print("Signing in with Google...")
        try:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                error_msg = f"Google client secrets file not found at {CLIENT_SECRETS_FILE}."
                print(error_msg)

                return
            
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            try:
                credentials = flow.run_local_server(port=0)
                self.credentials = credentials
                self.calendar_service = build('calendar', 'v3', credentials=credentials)
                self.user_email = self.get_user_email()
                self.save_credentials()
                self.create_clockin_calendar()
                self.update_button_states()
                print("Signed in with Google.")
            except Exception as e:
                error_msg = f"Authentication failed: {str(e)}"
                print(error_msg)
                rumps.notification(
                    "Google Sign-In Failed",
                    error_msg,
                    "Please try again or check your internet connection."
                )
        except Exception as e:
            error_msg = f"Error setting up authentication: {str(e)}"
            print(error_msg)
            rumps.notification(
                "Google Sign-In Failed",
                error_msg,
                "Please check your client secrets file and try again."
            )

    def add_task_to_google_calendar(self, task):
        """Add a task to Google Calendar with retry logic"""
        print(f"Adding task to Google Calendar: {task.name}")
        
        # Get the last time entry (which should be the one we just completed)
        if not task.time_entries or not task.time_entries[-1].end_time:
            print("No completed time entry to add to calendar.")
            return
        
        if not self.calendar_service or not self.calendar_id:
            print("Google Calendar service not available or calendar ID not set.")
            return
        
        time_entry = task.time_entries[-1]
        
        # Create the event for Google Calendar
        event = {
            'summary': task.format_for_calendar(),
            'start': {
                'dateTime': time_entry.start_time.isoformat(),
                'timeZone': 'UTC'
            },
            'end': {
                'dateTime': time_entry.end_time.isoformat(),
                'timeZone': 'UTC'
            }
        }
        
        # If task has a category, set color ID
        if task.category:
            # Convert category color to Google Calendar color ID (approximate)
            color_id = self.get_color_id_for_hex(task.category.color)
            if color_id:
                event['colorId'] = color_id
        
        # Add to calendar with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                created_event = self.calendar_service.events().insert(
                    calendarId=self.calendar_id, 
                    body=event
                ).execute()
                print(f"Event created: {created_event.get('htmlLink')}")
                return
            except Exception as e:
                print(f"Error adding event to calendar (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    # Last attempt failed
                    rumps.notification(
                        "Calendar Event Failed",
                        f"Could not add task '{task.name}' to Google Calendar.",
                        "Please check your internet connection."
                    )
                else:
                    # Sleep before retry
                    import time
                    time.sleep(1)

    def get_user_email(self):
        """Get user email from Google API"""
        print("Getting user email...")
        try:
            service = build('oauth2', 'v2', credentials=self.credentials)
            user_info = service.userinfo().get().execute()
            print(f"User email: {user_info['email']}")
            return user_info['email']
        except Exception as e:
            print(f"An error occurred while getting user email: {e}")
            return None

    def create_clockin_calendar(self):
        """Create or find the cLockIn calendar in Google Calendar"""
        print("Creating cLockIn calendar if it doesn't exist...")
        calendar_list = self.calendar_service.calendarList().list().execute()
        for calendar_entry in calendar_list['items']:
            if calendar_entry['summary'] == CALENDAR_TITLE:
                self.calendar_id = calendar_entry['id']
                print(f"cLockIn calendar already exists with ID: {self.calendar_id}")
                return

        calendar = {
            'summary': CALENDAR_TITLE,
            'timeZone': 'UTC'
        }
        created_calendar = self.calendar_service.calendars().insert(body=calendar).execute()
        self.calendar_id = created_calendar['id']
        print(f"cLockIn calendar created with ID: {self.calendar_id}")

    def register_keyboard_shortcut(self):
        """Register the global keyboard shortcut"""
        print("Registering keyboard shortcut...")
        if self.keyboard_shortcut_item.state:
            try:
                # Clear any previous shortcut first
                self.shortcut_manager.unregister_all()
                
                # Register the new shortcut
                self.shortcut_manager.register_shortcut(
                    SHORTCUT_KEY, 
                    SHORTCUT_MODIFIERS, 
                    self.keyboard_shortcut_triggered
                )
                print(f"Keyboard shortcut {' + '.join(SHORTCUT_MODIFIERS)} + {SHORTCUT_KEY} registered")
            
            except Exception as e:
                print(f"Error registering keyboard shortcut: {e}")
                rumps.notification(
                    "Keyboard Shortcut Failed",
                    "Could not register the global shortcut. Check system permissions.",
                    "Go to System Preferences > Security & Privacy > Privacy > Accessibility"
                )
        else:
            # Unregister the shortcut if it's disabled
            self.shortcut_manager.unregister_all()
            print("Keyboard shortcut disabled")

    def keyboard_shortcut_triggered(self):
        """Handle the global keyboard shortcut being triggered with improved error handling"""
        try:
            print("Keyboard shortcut triggered")
            
            # Make sure we're active
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            
            # Show the task input window
            self.show_task_input()
        except Exception as e:
            print(f"Error handling keyboard shortcut: {e}")
            rumps.notification(
                "Error",
                "An error occurred when handling the keyboard shortcut.",
                str(e)
            )

    def show_task_input(self, _=None):
        """Show the task input window with improved error handling"""
        try:
            print("Showing task input window...")
            
            # Check if window already exists and close it first
            if hasattr(self, 'text_input_window') and self.text_input_window:
                print("Window already exists, closing it first.")
                self.text_input_window.close_window()
                self.text_input_window = None
            
            # Create a new instance of the window with callback and storage
            self.text_input_window = TextInputWindow.alloc().initWithCallback_storage_(
                self.handle_task_input,
                self.storage
            )
            
            # Check if initialization succeeded
            if not self.text_input_window:
                print("Failed to initialize task input window.")
                rumps.notification(
                    "Error",
                    "Could not create the task input window.",
                    "Please try again."
                )
                return
            
            print("Task input window created successfully.")
            
        except Exception as e:
            print(f"Error showing task input: {e}")
            rumps.notification(
                "Error",
                "An error occurred when showing the task input window.",
                str(e)
            )
            
            # Clean up any partial initialization
            if hasattr(self, 'text_input_window') and self.text_input_window:
                try:
                    self.text_input_window.close_window()
                except Exception:
                    pass
                self.text_input_window = None
    
    def handle_task_input(self, task):
        """Handle the result from the task input window with better error handling"""
        try:
            print(f"Handling task input: {task}")
            
            if task:
                # Set the task as current and update UI
                self.update_button_states()
                
                # Show notification
                task_name = task.name
                if task.category:
                    task_name = f"@{task.category.name}/{task.name}"
                
            else:
                # User cancelled, just update UI
                self.update_button_states()
            
            # Clear the window reference
            self.text_input_window = None
        except Exception as e:
            print(f"Error handling task input: {e}")
            rumps.notification(
                "Error",
                "An error occurred processing the task.",
                str(e)
            )
    
    def start_existing_task(self, task):
        """Start an existing task with improved error handling"""
        try:
            print(f"Starting existing task: {task.name}")
            
            # First stop any active task
            active_task = self.storage.get_active_task()
            if active_task:
                active_task.pause()
                
                # Add to Google Calendar
                if active_task.current_entry() and active_task.current_entry().end_time:
                    self.add_task_to_google_calendar(active_task)
            
            # Start the selected task
            task.start()
            self.storage.save()
            
            # Update UI
            self.update_button_states()
            
            # Show notification
            task_name = task.name
            if task.category:
                task_name = f"@{task.category.name}/{task.name}"
                
        except Exception as e:
            print(f"Error starting existing task: {e}")
            rumps.notification(
                "Error",
                f"Could not start task: {task.name}",
                str(e)
            )

    def start_event(self, _):
        """Start a new task (legacy method)"""
        print("Starting event (legacy method)...")
        
        # Just redirect to the new task input
        self.show_task_input()

    def pause_event(self, _):
        """Pause the current task with improved error handling"""
        try:
            print("Pausing event...")
            
            if not self.credentials:
                print("Not signed in, showing alert.")
                rumps.alert("Sign in first")
                return
            
            # Get the active task
            active_task = self.storage.get_active_task()
            if not active_task:
                print("No active task to pause.")
                rumps.alert("No active task to pause")
                return
            
            # Pause the task
            active_task.pause()
            
            # Add to Google Calendar
            self.add_task_to_google_calendar(active_task)
            
            # Save data
            self.storage.save()
            
            # Show notification
            task_name = active_task.name
            if active_task.category:
                task_name = f"@{active_task.category.name}/{task_name}"
                
            
            # Update UI
            self.update_button_states()
            print("Task paused.")
        except Exception as e:
            print(f"Error pausing task: {e}")
            rumps.notification(
                "Error",
                "Could not pause the current task.",
                str(e)
            )

    def stop_event(self, _):
        """Stop the current task with improved error handling"""
        try:
            print("Stopping event...")
            
            if not self.credentials:
                print("Not signed in, showing alert.")
                rumps.alert("Sign in first")
                return
            
            # Get the active task
            active_task = self.storage.get_active_task()
            if not active_task:
                print("No active task to stop.")
                rumps.alert("No active task to stop")
                return
            
            # Pause the task (which will end the current time entry)
            active_task.pause()
            
            # Add to Google Calendar
            self.add_task_to_google_calendar(active_task)
            
            # Save data
            self.storage.save()
            
            # Show notification
            task_name = active_task.name
            if active_task.category:
                task_name = f"@{active_task.category.name}/{task_name}"
                
            
            # Clear Discord presence
            if self.rpc and self.discord_enabled:
                self.rpc.clear()
            
            # Update UI
            self.update_button_states()
            print("Task stopped.")
        except Exception as e:
            print(f"Error stopping task: {e}")
            rumps.notification(
                "Error",
                "Could not stop the current task.",
                str(e)
            )

    def get_color_id_for_hex(self, hex_color):
        """Convert hex color to Google Calendar color ID (approximate mapping)"""
        # Google Calendar color IDs:
        # 1: Lavender, 2: Sage, 3: Grape, 4: Flamingo, 5: Banana
        # 6: Tangerine, 7: Peacock, 8: Graphite, 9: Blueberry, 10: Basil, 11: Tomato
        
        # Remove # if present
        if hex_color.startswith('#'):
            hex_color = hex_color[1:]
        
        # Convert to RGB
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Simple hue-based mapping
            import colorsys
            h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
            
            # Map hue to color ID (simplified)
            if h < 0.05 or h > 0.95:  # Red
                return "11"  # Tomato
            elif 0.05 <= h < 0.15:  # Orange
                return "6"   # Tangerine
            elif 0.15 <= h < 0.25:  # Yellow
                return "5"   # Banana
            elif 0.25 <= h < 0.4:   # Green
                return "10"  # Basil
            elif 0.4 <= h < 0.5:    # Teal
                return "7"   # Peacock
            elif 0.5 <= h < 0.7:    # Blue
                return "9"   # Blueberry
            elif 0.7 <= h < 0.8:    # Purple
                return "3"   # Grape
            elif 0.8 <= h < 0.95:   # Pink
                return "4"   # Flamingo
            else:
                return "1"   # Lavender (default)
        except:
            return None  # Default color

    def export_simple_csv(self, category):
        """Export a simple CSV for the given category"""
        filepath = self.csv_exporter.export_category_timesheet(category)
        if filepath:
            self.csv_exporter.open_csv_file(filepath)

    def export_detailed_csv(self, category):
        """Export a detailed CSV for the given category"""
        filepath = self.csv_exporter.export_detailed_timesheet(category)
        if filepath:
            self.csv_exporter.open_csv_file(filepath)

    def export_weekly_csv(self, category):
        """Export a weekly CSV for the given category"""
        filepath = self.csv_exporter.export_weekly_timesheet(category)
        if filepath:
            self.csv_exporter.open_csv_file(filepath)

    def is_run_at_startup_enabled(self):
        """Check if run at startup is enabled"""
        print("Checking if run at startup is enabled...")
        enabled = os.path.exists(LAUNCH_AGENT_FILE) and os.path.exists(SHELL_SCRIPT_FILE)
        print(f"Run at startup enabled: {enabled}")
        return enabled

    def toggle_run_at_startup(self, sender):
        """Toggle run at startup setting"""
        print("Toggling run at startup...")
        if sender.state:
            self.disable_run_at_startup()
        else:
            self.enable_run_at_startup()
        sender.state = not sender.state
        print("Run at startup toggled.")

    def enable_run_at_startup(self):
        """Enable run at startup"""
        print("Enabling run at startup...")
        self.create_shell_script()
        self.create_launch_agent_plist()
        subprocess.run(["launchctl", "load", LAUNCH_AGENT_FILE])
        print("Run at startup enabled.")

    def disable_run_at_startup(self):
        """Disable run at startup"""
        print("Disabling run at startup...")
        if os.path.exists(LAUNCH_AGENT_FILE):
            subprocess.run(["launchctl", "unload", LAUNCH_AGENT_FILE])
            os.remove(LAUNCH_AGENT_FILE)
        if os.path.exists(SHELL_SCRIPT_FILE):
            os.remove(SHELL_SCRIPT_FILE)
        print("Run at startup disabled.")

    def toggle_discord_presence(self, sender):
        """Toggle Discord rich presence"""
        print("Toggling Discord presence...")
        self.discord_enabled = not self.discord_enabled
        sender.state = self.discord_enabled

        if self.discord_enabled and self.rpc is None:
            try:
                self.rpc = Presence(DISCORD_APP_CLIENT_ID)
                self.rpc.connect()
            except Exception as e:
                print(f"Failed to connect to Discord: {e}")
                self.discord_enabled = False
                sender.state = False
        elif not self.discord_enabled and self.rpc:
            self.rpc.clear()
            self.rpc.close()
            self.rpc = None

        print(f"Discord presence toggled to {'enabled' if self.discord_enabled else 'disabled'}.")

    def open_json_file(self, _):
        """Open the storage JSON file in the default text editor"""
        print("Opening storage JSON file...")
        try:
            # Use the 'open' command on macOS to open the file with default application
            # try to open with 'code' first and if it fails, fall back to 'open'
            if not os.path.exists(self.storage.storage_file):
                print(f"Storage file does not exist: {self.storage.storage_file}")
                rumps.notification(
                    "Error",
                    "Storage file not found",
                    f"{self.storage.storage_file} does not exist."
                )
                return
            # Attempt to open with Visual Studio Code first
            try:
                subprocess.run(['code', self.storage.storage_file], check=True)
            except FileNotFoundError:
                # If 'code' is not found, fall back to 'open'
                print("'code' command not found, falling back to 'open'")
                subprocess.run(['open', self.storage.storage_file])
            except subprocess.CalledProcessError:
                # If 'code' fails, fall back to 'open' 
                subprocess.run(['open', self.storage.storage_file])
            print(f"Opened {self.storage.storage_file}")
        except Exception as e:
            print(f"Error opening JSON file: {e}")
            rumps.notification(
                "Error",
                f"Could not open {self.storage.storage_file}",
                str(e)
            )

    def create_shell_script(self):
        """Create the shell script for startup"""
        print("Creating shell script...")
        app_directory = os.path.dirname(os.path.abspath(__file__))
        script_content = f"""#!/bin/bash
cd {app_directory}
source venv/bin/activate
python3.12 app.py
"""
        with open(SHELL_SCRIPT_FILE, 'w') as script_file:
            script_file.write(script_content)
        os.chmod(SHELL_SCRIPT_FILE, 0o755)  # Make the script executable
        print("Shell script created.")

    def create_launch_agent_plist(self):
        """Create the launch agent plist for startup"""
        print("Creating launch agent plist...")
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{OS_USERNAME}.clockinapp</string>
    <key>ProgramArguments</key>
    <array>
        <string>{SHELL_SCRIPT_FILE}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/clockinapp.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/clockinapp.err</string>
</dict>
</plist>
"""
        with open(LAUNCH_AGENT_FILE, 'w') as plist_file:
            plist_file.write(plist_content)
        print("Launch agent plist created.")


if __name__ == "__main__":
    MenuApp().run()