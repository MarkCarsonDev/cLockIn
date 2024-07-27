import rumps
import datetime
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Path to the OAuth 2.0 client secrets file downloaded from the Google Cloud Console
CLIENT_SECRETS_FILE = 'path_to_your_client_secrets.json'
SCOPES = ['https://www.googleapis.com/auth/calendar']

class MenuApp(rumps.App):
    def __init__(self):
        super(MenuApp, self).__init__("Clock-In App")
        self.title = "Clock-In"
        self.menu = ["Sign in with Google", "What are you working on?", "Start", "Pause", "Stop"]
        self.current_event = None
        self.credentials = None
        self.calendar_service = None

    @rumps.clicked("Sign in with Google")
    def sign_in_with_google(self, _):
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
        self.credentials = credentials
        self.calendar_service = build('calendar', 'v3', credentials=credentials)
        rumps.notification("Signed in", "Successfully signed in to Google", "")

    @rumps.clicked("What are you working on?")
    def set_event_title(self, _):
        if not self.credentials:
            rumps.alert("Sign in first")
            return
        response = rumps.Window("Enter your task", "Task Title").run()
        if response.clicked:
            self.current_event = {
                'summary': response.text,
                'start': {'dateTime': None, 'timeZone': 'UTC'},
                'end': {'dateTime': None, 'timeZone': 'UTC'}
            }
            rumps.notification("Task Set", "Current task set to", response.text)

    @rumps.clicked("Start")
    def start_event(self, _):
        if not self.credentials:
            rumps.alert("Sign in first")
            return
        if not self.current_event:
            rumps.alert("Set a task first")
            return
        self.current_event['start']['dateTime'] = datetime.datetime.utcnow().isoformat() + 'Z'
        rumps.notification("Event Started", "Started working on", self.current_event['summary'])

    @rumps.clicked("Pause")
    def pause_event(self, _):
        if not self.credentials:
            rumps.alert("Sign in first")
            return
        if not self.current_event or not self.current_event['start']['dateTime']:
            rumps.alert("Start an event first")
            return
        self.current_event['end']['dateTime'] = datetime.datetime.utcnow().isoformat() + 'Z'
        self.add_event_to_google_calendar()
        rumps.notification("Event Paused", "Paused working on", self.current_event['summary'])
        self.current_event['start']['dateTime'] = None

    @rumps.clicked("Stop")
    def stop_event(self, _):
        if not self.credentials:
            rumps.alert("Sign in first")
            return
        if not self.current_event or not self.current_event['start']['dateTime']:
            rumps.alert("Start an event first")
            return
        self.current_event['end']['dateTime'] = datetime.datetime.utcnow().isoformat() + 'Z'
        self.add_event_to_google_calendar()
        rumps.notification("Event Stopped", "Stopped working on", self.current_event['summary'])
        self.current_event = None

    def add_event_to_google_calendar(self):
        if not self.current_event:
            return
        event = self.calendar_service.events().insert(calendarId='primary', body=self.current_event).execute()
        print(f"Event created: {event.get('htmlLink')}")

if __name__ == "__main__":
    MenuApp().run()
