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
from Cocoa import NSTextField, NSApp, NSWindow, NSRect, NSButton, NSObject, NSBackingStoreBuffered, NSPoint, NSWindowCollectionBehaviorMoveToActiveSpace
from Quartz import CGShieldingWindowLevel
import AppKit
from pypresence import Presence
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
try:
    DISCORD_APP_CLIENT_ID = os.getenv('DISCORD_APP_CLIENT_ID')
except:
    DISCORD_APP_CLIENT_ID = None

# get macos username
OS_USERNAME = pwd.getpwuid(os.getuid()).pw_name

# Path to the OAuth 2.0 client secrets file downloaded from the Google Cloud Console
CLIENT_SECRETS_FILE = 'google_client_secrets.json'
SCOPES = ['openid', 'https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/userinfo.email']
CREDENTIALS_FILE = 'token.json'
LAUNCH_AGENT_FILE = os.path.expanduser(f'~/Library/LaunchAgents/com.{OS_USERNAME}.clockinapp.plist')
SHELL_SCRIPT_FILE = os.path.abspath(f'run_clockin_app.sh')
DEFAULT_TITLE = ""
CALENDAR_TITLE = "cLockIn"

class TextInputWindow(NSObject):
    def initWithCallback_(self, callback):
        self = super(TextInputWindow, self).init()
        if self is None:
            return None
        self.callback = callback
        self.window = None
        return self

    def createWindow(self):
        print("Creating text input window...")
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSRect((0, 0), (400, 0)),
            1 << 0,  # NSWindowStyleMaskBorderless
            NSBackingStoreBuffered,
            False
        )
        self.window.setLevel_(CGShieldingWindowLevel() + 1)  # Floating window above all others
        self.window.setCollectionBehavior_(NSWindowCollectionBehaviorMoveToActiveSpace)
        self.window.setTitleVisibility_(1)  # Hide title bar
        self.window.setTitlebarAppearsTransparent_(True)
        self.window.setBackgroundColor_(objc.nil)
        self.window.setOpaque_(False)
        self.window.setMovable_(False)
        self.window.setHasShadow_(True)
        self.window.setReleasedWhenClosed_(False)
        self.window.setCanHide_(False)

        # get screen dimensions
        screen = self.window.screen()
        screen_frame = screen.frame()
        screen_width = screen_frame.size.width
        screen_height = screen_frame.size.height
        # get window dimensions
        window_frame = self.window.frame()
        window_width = window_frame.size.width
        window_height = window_frame.size.height
        # calculate the position of the window
        x = (screen_width - window_width) / 2
        y = screen_height - window_height - 30
        self.window.setFrameOrigin_(NSPoint(x, y))

        content_view = self.window.contentView()
        
        self.text_input = NSTextField.alloc().initWithFrame_(((0, 0), (400, 30)))
        self.text_input.setPlaceholderString_("What are you working on?")
        self.text_input.setBezeled_(True)
        self.text_input.setBezelStyle_(1)
        self.text_input.setDrawsBackground_(False)
        self.text_input.setFocusRingType_(1)
        self.text_input.setWantsLayer_(True)
        self.text_input.layer().setZPosition_(3)
        self.text_input.setSelectable_(True)
        self.text_input.setAllowsEditingTextAttributes_(True)
        self.text_input.setEditable_(True)
        self.text_input.setSelectable_(True)
        self.text_input.setSelectable_(True)
        self.text_input.cell().setWraps_(False)

        content_view.addSubview_(self.text_input)

        start_button = NSButton.alloc().initWithFrame_(((230, 110), (80, 24)))
        start_button.setTitle_("Start")
        start_button.setBezelStyle_(4)
        start_button.setKeyEquivalent_("\r")  # Enter key triggers the button
        start_button.setTarget_(self)
        start_button.setAction_("startButtonClicked:")
        content_view.addSubview_(start_button)

        cancel_button = NSButton.alloc().initWithFrame_(((310, 110), (80, 24)))
        cancel_button.setTitle_("Cancel")
        cancel_button.setBezelStyle_(4)
        cancel_button.setKeyEquivalent_("\x1b")  # Escape key triggers the button
        cancel_button.setTarget_(self)
        cancel_button.setAction_("cancelButtonClicked:")
        content_view.addSubview_(cancel_button)

        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        print("Text input window created.")

    def startButtonClicked_(self, sender):
        print(f"Start button clicked: {sender}")
        self.callback(self.text_input.stringValue())
        self.close_window()

    def cancelButtonClicked_(self, sender):
        print(f"Cancel button clicked: {sender}")
        self.callback(None)
        self.close_window()

    def windowDidResignKey_(self, notification):
        print("Window resigned key, closing...")
        self.callback(None)
        self.close_window()

    def close_window(self):
        if self.window:
            print(f"Closing text input window... {self}")
            self.window.orderOut_(None)
            print("Text input window closed.")


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

        self.discord_enabled = bool(DISCORD_APP_CLIENT_ID)
        self.rpc = None

        if self.discord_enabled:
            try:
                self.rpc = Presence(DISCORD_APP_CLIENT_ID)
                self.rpc.connect()
            except Exception as e:
                print(f"Failed to connect to Discord: {e}")
                self.discord_enabled = False

        print("Initializing application...")
        self.load_credentials()

        self.sign_in_item = rumps.MenuItem("Sign in with Google", callback=self.sign_in_with_google)
        self.start_item = rumps.MenuItem("⏵", callback=self.start_event)
        self.pause_item = rumps.MenuItem("⏸", callback=self.pause_event)
        self.stop_item = rumps.MenuItem("⏹", callback=self.stop_event)

        self.run_at_startup_item = rumps.MenuItem("Run at Startup", callback=self.toggle_run_at_startup)
        self.run_at_startup_item.state = self.is_run_at_startup_enabled()

        self.show_in_discord_item = rumps.MenuItem("Show in Discord", callback=self.toggle_discord_presence)
        self.show_in_discord_item.state = self.discord_enabled
        self.sign_out_item = rumps.MenuItem("Sign Out", callback=self.sign_out)

        self.preferences_menu = rumps.MenuItem("Preferences")
        self.preferences_menu.add(self.run_at_startup_item)
        self.preferences_menu.add(self.show_in_discord_item)
        self.preferences_menu.add(self.sign_out_item)

        self.menu = [self.sign_in_item, self.preferences_menu, None, rumps.MenuItem("Quit", callback=rumps.quit_application)]

        self.update_button_states()
        self.timer = rumps.Timer(self.update_title, 15)  # Timer to update the title every second
        self.timer.start()
        print("Application initialized.")

        self.set_accessory_mode()

    def set_accessory_mode(self):
        print("Setting application to accessory mode...")
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        print("Application set to accessory mode.")


    def load_credentials(self):
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
        print("Saving credentials...")
        with open(CREDENTIALS_FILE, 'w') as token:
            token.write(self.credentials.to_json())
        print("Credentials saved.")

    def sign_out(self, _):
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
        print("Updating button states...")
        self.menu.clear()
        self.menu["Sign in with Google"] = self.sign_in_item
        self.menu["Preferences"] = self.preferences_menu
        self.menu.add(None)  # Add a separator
        
        if self.credentials and self.credentials.valid:
            self.sign_in_item.title = self.user_email if self.user_email else "Signed In"
            self.sign_in_item.set_callback(None)
            
            if self.current_event:
                if self.current_event['start']['dateTime']:
                    self.menu["Pause"] = self.pause_item
                    self.menu["Stop"] = self.stop_item
                else:
                    self.menu["Play"] = self.start_item
                    self.menu["Stop"] = self.stop_item
            else:
                self.menu["Play"] = self.start_item
        else:
            self.sign_in_item.title = "Sign in with Google"
            self.sign_in_item.set_callback(self.sign_in_with_google)

        self.menu.add(None)  # Add a separator
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))  # Add the Quit button at the end
        self.update_title()
        print("Button states updated.")
        # print FULL debug info
        print(f'FULL DEBUG\n\n\t\t\t----:\ncurrent_event: {self.current_event}\n\
              window: {self.text_input_window}\n\
                                    ')
        

    def update_title(self, _=None):
        if not self.current_event:
            self.title = DEFAULT_TITLE
            if self.rpc and self.discord_enabled:
                self.rpc.clear()
            return
        
        print("Updating title...")
        if self.current_event and self.current_event['start']['dateTime']:
            start_time = parser.isoparse(self.current_event['start']['dateTime'])
            elapsed_time = datetime.datetime.now(datetime.timezone.utc) - start_time
            hours, remainder = divmod(elapsed_time.total_seconds(), 3600)
            minutes, remainder_s = divmod(remainder, 60)
            self.title = f"{self.current_event['summary']} • for {int(hours)}h {int(minutes)}m" if hours >= 1 else f"{self.current_event['summary']} • for {int(minutes)}m"

            # Update Discord presence
            if self.rpc and self.discord_enabled:
                self.rpc.update(
                    details=self.current_event['summary'],
                    start=int(start_time.timestamp()),
                    large_image="icon", # Replace with image key of choice
                    large_text="Locked in",
                )

        elif self.current_event and not self.current_event['start']['dateTime']:
            self.title = f"{self.current_event['summary']} • ⏸"
        else:
            self.title = DEFAULT_TITLE
        print(f"Title updated to: {self.title}")

    def sign_in_with_google(self, _):
        print("Signing in with Google...")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
        self.credentials = credentials
        self.calendar_service = build('calendar', 'v3', credentials=credentials)
        self.user_email = self.get_user_email()
        self.save_credentials()
        self.create_clockin_calendar()
        rumps.notification("Signed in", "Successfully signed in to Google", "")
        self.update_button_states()
        print("Signed in with Google.")

    def get_user_email(self):
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

    def set_event_title(self):
        print("Setting event title...")
        print(f"self.text_input_window: {self.text_input_window}")

        if self.text_input_window:
            print("Window already exists, closing it first.")
            self.text_input_window.close_window()
        
        self.text_input_window = TextInputWindow.alloc().initWithCallback_(self.handle_window_response)
        print(f"self.text_input_window: {self.text_input_window}")
        self.text_input_window.performSelectorOnMainThread_withObject_waitUntilDone_("createWindow", None, True)

        print("Event title set.")


    def handle_window_response(self, response):
        print(f"Handling window response: {response}")
        if response:
            self.current_event = {
                'summary': response,
                'start': {'dateTime': None, 'timeZone': 'UTC'},
                'end': {'dateTime': None, 'timeZone': 'UTC'}
            }
            rumps.notification("Task Set", "Current task set to", response)
            # Start the event after setting the task
            self.start_event(None)

        self.update_button_states()
        print("Window response handled.")

    def start_event(self, _):
        print("Starting event...")
        if not self.credentials:
            print("Not signed in, showing alert.")
            rumps.alert("Sign in first")
            return
        if self.current_event and self.current_event['start']['dateTime']:
            print("An event is already running. Stopping it first.")
            self.stop_event(_)  # Pause the current event before starting a new one
        if not self.current_event:
            self.set_event_title()
            return
        if not self.current_event or not self.current_event['summary']:
            print("Event summary not set, showing alert.")
            rumps.alert("Set a task first")
            return
        self.current_event['start']['dateTime'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.current_event['end']['dateTime'] = None  # Clear end time if restarting
        rumps.notification("Event Started", "Started working on", self.current_event['summary'])
        self.update_button_states()
        print("Event started.")

    def pause_event(self, _):
        print("Pausing event...")
        if not self.credentials:
            print("Not signed in, showing alert.")
            rumps.alert("Sign in first")
            return
        if not self.current_event or not self.current_event['start']['dateTime']:
            print("No event to pause, showing alert.")
            rumps.alert("Start an event first")
            return
        self.current_event['end']['dateTime'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.add_event_to_google_calendar()
        rumps.notification("Event Paused", "Paused working on", self.current_event['summary'])
        self.current_event['start']['dateTime'] = None  # Mark event as paused
        self.update_button_states()
        print("Event paused.")


    def stop_event(self, _):
        # self.text_input_window = None
        print("Stopping event...")
        if not self.credentials:
            print("Not signed in, showing alert.")
            rumps.alert("Sign in first")
            return
        if self.current_event and self.current_event['start']['dateTime']:
            # Stopping an active event
            self.current_event['end']['dateTime'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.add_event_to_google_calendar()
        elif self.current_event and not self.current_event['start']['dateTime']:
            # Stopping a paused event, no need to create a new calendar event
            pass

        self.current_event = None
        self.update_button_states()
        if self.rpc and self.discord_enabled:
            self.rpc.clear()
        print("Event stopped.")

    def add_event_to_google_calendar(self):
        print("Adding event to Google Calendar...")
        if not self.current_event:
            print("No current event to add to calendar.")
            return
        event = self.calendar_service.events().insert(calendarId=self.calendar_id, body=self.current_event).execute()
        print(f"Event created: {event.get('htmlLink')}")

    def is_run_at_startup_enabled(self):
        print("Checking if run at startup is enabled...")
        enabled = os.path.exists(LAUNCH_AGENT_FILE) and os.path.exists(SHELL_SCRIPT_FILE)
        print(f"Run at startup enabled: {enabled}")
        return enabled

    def toggle_run_at_startup(self, sender):
        print("Toggling run at startup...")
        if sender.state:
            self.disable_run_at_startup()
        else:
            self.enable_run_at_startup()
        sender.state = not sender.state
        print("Run at startup toggled.")

    def enable_run_at_startup(self):
        print("Enabling run at startup...")
        self.create_shell_script()
        self.create_launch_agent_plist()
        subprocess.run(["launchctl", "load", LAUNCH_AGENT_FILE])
        print("Run at startup enabled.")

    def disable_run_at_startup(self):
        print("Disabling run at startup...")
        if os.path.exists(LAUNCH_AGENT_FILE):
            subprocess.run(["launchctl", "unload", LAUNCH_AGENT_FILE])
            os.remove(LAUNCH_AGENT_FILE)
        if os.path.exists(SHELL_SCRIPT_FILE):
            os.remove(SHELL_SCRIPT_FILE)
        print("Run at startup disabled.")

    def toggle_discord_presence(self, sender):
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

    def create_shell_script(self):
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
