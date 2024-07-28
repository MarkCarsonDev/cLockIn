# cLockIn

cLockIn is a lightweight macOS menu bar application designed to help you track your work tasks effortlessly. With seamless integration with Google Calendar and optional rich presence updates to Discord, this open-source tool is perfect for anyone looking to manage their time effectively and share their activity status.

## Features

- **Task Tracking**: Easily create and manage tasks directly from your menu bar.
- **Google Calendar Integration**: Sync your tasks with Google Calendar and keep your schedule up-to-date.
- **Discord Rich Presence**: Optionally show your current task and elapsed time on Discord.
- **Preferences**: Customize the app to run at startup and control Discord presence visibility.

## Installation

### Prerequisites

- Python 3.12
- Google Cloud credentials for Calendar API
- (Optional) Discord application credentials for rich presence

### Setup

1. **Clone the Repository**

   ```bash
   git clone https://github.com/MarkCarsonDev/clockin.git
   cd clock-in-app
   ```

2. **Create a Virtual Environment and Install Dependencies**

   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Google Cloud Setup**

   First, set up OAuth 2.0 credentials on the Google Cloud Console:

   - Create a new project or select an existing project.
   - Enable the Google Calendar API:
     - Go to APIs & Services > Library.
     - Enable the Google Calendar API.
   - Create OAuth 2.0 credentials:
     - Go to APIs & Services > Credentials.
     - Click Create Credentials > OAuth 2.0 Client IDs.
     - Configure the consent screen if prompted.
     - Include the permission to create and modify secondary Calendars.
     - Set the application type to Desktop app.
   - Download the credentials JSON file and store it securely in `google_client_secrets.json`.

4. **Discord Setup (Optional)**

   - Create a new application on the [Discord Developer Portal](https://discord.com/developers/applications).
   - Copy the Client ID.

5. **Environment Variables**

   Create a `.env.local` file in the project directory with the following content:

   ```env
   DISCORD_APP_CLIENT_ID=your_discord_client_id
   ```

6. **Run the App**

   ```bash
   python app.py
   ```

## Usage

Once the app is running:

1. **Sign In with Google**: Click on the menu bar icon and select "Sign in with Google" to authenticate and sync with Google Calendar.
2. **Start a Task**: Click the play button to create and start a new task. You’ll be prompted to enter the task description.
3. **Pause/Stop a Task**: Use the pause and stop buttons to manage your current task.
4. **Preferences**: Access the "Preferences" menu to enable/disable running the app at startup and to control Discord rich presence visibility.

## Contributing

We welcome contributions from the community! If you have ideas for features or improvements, please feel free to open an issue or submit a pull request.

## License

This project isn't licensed... pretty please don't steal and claim as your own?

## Acknowledgements

Special thanks to the developers of the libraries and APIs used in this project, including Rumps, Google Auth, and PyPresence.
