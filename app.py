import rumps
import datetime
import os
import json
import objc
from dateutil import parser
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import subprocess
from Cocoa import NSTextField, NSApp, NSApplicationActivationPolicyRegular, NSWindow, NSRect, NSView, NSButton, NSAlert, NSApplication, NSObject

# Path to the OAuth 2.0 client secrets file downloaded from the Google Cloud Console
CLIENT_SECRETS_FILE = 'google_client_secrets.json'
SCOPES = ['openid', 'https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/userinfo.email']
CREDENTIALS_FILE = 'token.json'
LAUNCH_AGENT_FILE = os.path.expanduser('~/Library/LaunchAgents/com.yourusername.clockinapp.plist')
SHELL_SCRIPT_FILE = 'run_clockin_app.sh'

class MenuApp(rumps.App):
    def __init__(self):
        super(MenuApp, self).__init__("Clock-In App", quit_button=None)
        self.title = "cLockIn"
        self.icon = "icon.png"
        self.credentials = None
        self.calendar_service = None
        self.current_event = None
        self.user_email = None

        self.load_credentials()

        self.sign_in_item = rumps.MenuItem("Sign in with Google", callback=self.sign_in_with_google)
        self.start_item = rumps.MenuItem("⏵", callback=self.start_event)
        self.pause_item = rumps.MenuItem("⏸", callback=self.pause_event)
        self.stop_item = rumps.MenuItem("⏹", callback=self.stop_event)
        self.run_at_startup_item = rumps.MenuItem("Run at Startup", callback=self.toggle_run_at_startup)
        self.run_at_startup_item.state = self.is_run_at_startup_enabled()

        self.menu = [self.sign_in_item, self.run_at_startup_item, None, rumps.MenuItem("Quit", callback=rumps.quit_application)]

        self.update_button_states()
        self.timer = rumps.Timer(self.update_title, 1)  # Timer to update the title every second
        self.timer.start()

    def load_credentials(self):
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE, 'r') as token:
                self.credentials = Credentials.from_authorized_user_info(json.load(token), SCOPES)
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            self.calendar_service = build('calendar', 'v3', credentials=self.credentials)
            self.user_email = self.get_user_email()

    def save_credentials(self):
        with open(CREDENTIALS_FILE, 'w') as token:
            token.write(self.credentials.to_json())

    def update_button_states(self):
        self.menu.clear()
        self.menu["Sign in with Google"] = self.sign_in_item
        self.menu["Run at Startup"] = self.run_at_startup_item
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

    def update_title(self, _=None):
        if self.current_event and self.current_event['start']['dateTime']:
            start_time = parser.isoparse(self.current_event['start']['dateTime'])
            elapsed_time = datetime.datetime.now(datetime.timezone.utc) - start_time
            hours, remainder = divmod(elapsed_time.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            self.title = f"{self.current_event['summary']} • for {int(hours)}h{int(minutes)}m"
        elif self.current_event and not self.current_event['start']['dateTime']:
            self.title = f"{self.current_event['summary']} • ⏸"
        else:
            self.title = "cLockIn"

    def sign_in_with_google(self, _):
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
        self.credentials = credentials
        self.calendar_service = build('calendar', 'v3', credentials=credentials)
        self.user_email = self.get_user_email()
        self.save_credentials()
        rumps.notification("Signed in", "Successfully signed in to Google", "")
        self.update_button_states()

    def get_user_email(self):
        try:
            service = build('oauth2', 'v2', credentials=self.credentials)
            user_info = service.userinfo().get().execute()
            return user_info['email']
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def set_event_title(self):
        response = self.create_text_input_window()
        if response:
            self.current_event = {
                'summary': response,
                'start': {'dateTime': None, 'timeZone': 'UTC'},
                'end': {'dateTime': None, 'timeZone': 'UTC'}
            }
            rumps.notification("Task Set", "Current task set to", response)
            self.update_button_states()

    def create_text_input_window(self):
        NSApp.activateIgnoringOtherApps_(True)
        alert = NSAlert.alloc().init()
        alert.setMessageText_("What are you working on?")
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        text_input = NSTextField.alloc().initWithFrame_(((0, 0), (300, 24)))
        alert.setAccessoryView_(text_input)

        response = alert.runModal()
        if response == 1000:  # OK clicked
            return text_input.stringValue()
        return None

    def start_event(self, _):
        if not self.credentials:
            rumps.alert("Sign in first")
            return
        if not self.current_event:
            self.set_event_title()
        if not self.current_event['summary']:
            rumps.alert("Set a task first")
            return
        self.current_event['start']['dateTime'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rumps.notification("Event Started", "Started working on", self.current_event['summary'])
        self.update_button_states()

    def pause_event(self, _):
        if not self.credentials:
            rumps.alert("Sign in first")
            return
        if not self.current_event or not self.current_event['start']['dateTime']:
            rumps.alert("Start an event first")
            return
        self.current_event['end']['dateTime'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.add_event_to_google_calendar()
        rumps.notification("Event Paused", "Paused working on", self.current_event['summary'])
        self.current_event['start']['dateTime'] = None
        self.update_button_states()

    def stop_event(self, _):
        if not self.credentials:
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

    def add_event_to_google_calendar(self):
        if not self.current_event:
            return
        event = self.calendar_service.events().insert(calendarId='primary', body=self.current_event).execute()
        print(f"Event created: {event.get('htmlLink')}")

    def is_run_at_startup_enabled(self):
        return os.path.exists(LAUNCH_AGENT_FILE)

    def toggle_run_at_startup(self, sender):
        if sender.state:
            self.disable_run_at_startup()
        else:
            self.enable_run_at_startup()
        sender.state = not sender.state

    def enable_run_at_startup(self):
        self.create_shell_script()
        self.create_launch_agent_plist()
        subprocess.run(["launchctl", "load", LAUNCH_AGENT_FILE])

    def disable_run_at_startup(self):
        if os.path.exists(LAUNCH_AGENT_FILE):
            subprocess.run(["launchctl", "unload", LAUNCH_AGENT_FILE])
            os.remove(LAUNCH_AGENT_FILE)
        if os.path.exists(SHELL_SCRIPT_FILE):
            os.remove(SHELL_SCRIPT_FILE)

    def create_shell_script(self):
        script_content = f"""#!/bin/bash
source venv/bin/activate
python3.12 app.py
"""
        with open(SHELL_SCRIPT_FILE, 'w') as script_file:
            script_file.write(script_content)
        os.chmod(SHELL_SCRIPT_FILE, 0o755)  # Make the script executable

    def create_launch_agent_plist(self):
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yourusername.clockinapp</string>
    <key>ProgramArguments</key>
    <array>
        <string>{SHELL_SCRIPT_FILE}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/clockinapp.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/clockinapp.err</string>
</dict>
</plist>
"""
        with open(LAUNCH_AGENT_FILE, 'w') as plist_file:
            plist_file.write(plist_content)

if __name__ == "__main__":
    MenuApp().run()
