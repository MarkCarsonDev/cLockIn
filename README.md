To run this app you will need to create your own Google cloud credentials

1. Google Cloud Setup
First, set up OAuth 2.0 credentials on the Google Cloud Console:

Create a new project or select an existing project.

Enable the Google Calendar API:

Go to APIs & Services > Library.
Enable the Google Calendar API.
Create OAuth 2.0 credentials:

Go to APIs & Services > Credentials.
- Click Create Credentials > OAuth 2.0 Client IDs.
- Configure the consent screen if prompted.
    - Include the permission to create and modify secondary Calendars
- Set the application type to Desktop app.

Download the credentials JSON file and store it securely in `google_client_secrets.json`.