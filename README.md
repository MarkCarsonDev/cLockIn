# cLockIn

cLockIn is a lightweight macOS menu bar application designed to help you track your work tasks effortlessly. With seamless integration with Google Calendar and optional rich presence updates to Discord, this open-source tool is perfect for anyone looking to manage their time effectively and share their activity status.

## Features

- **Task & Category Management**: Organize your work with categories and tasks for better time tracking.
- **Global Keyboard Shortcut**: Quickly start tasks from anywhere with a customizable global keyboard shortcut (⌘+⇧+⌃+T by default).
- **Smart Autocomplete**: Easily navigate through your existing categories and tasks while typing.
- **Google Calendar Integration**: Sync your tasks with Google Calendar and keep your schedule up-to-date.
- **Discord Rich Presence**: Optionally show your current task and elapsed time on Discord.
- **CSV Export**: Export timesheets for each category in various formats.
- **Run at Startup**: Automatically launch cLockIn when you log in.

## Installation

### Prerequisites

- Python 3.12 (earlier versions likely work but are untested)
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

### Getting Started

1. **Sign In with Google**: Click on the menu bar icon and select "Sign in with Google" to authenticate and sync with Google Calendar.
2. **Start a Task**: Use the global keyboard shortcut (⌘+⇧+⌃+T by default) or click "Start New Task" from the menu bar dropdown.

### Task Input

The task input window supports a powerful syntax for categorizing your work:

- Type normally to create an uncategorized task
- Start with `@` to enter a category
- Press `Tab` to cycle through existing categories or tasks
- Press `Enter` to confirm a selection
- Press `Escape` to cancel

Examples:

- `@Client A <Enter> Design Homepage <Enter>` - Creates "Design Homepage" task in "Client A" category
- `@<Tab><Enter> Meeting Notes <Enter>` - Selects first category and creates "Meeting Notes" task in it
- `<Tab><Tab><Enter>` - Cycles through and selects an existing task

### Managing Tasks

- **Pause/Stop**: Use the menu to pause or stop the current task
- **Resume**: Select a recent or existing task from the menu to resume it
- **View Stats**: The menu shows total time spent on each task

### Exporting Data

For each category, you can export time data in various CSV formats:

- **Simple CSV**: Basic summary of total time spent on each task
- **Detailed CSV**: Breakdown of individual time entries with start/end times
- **Weekly CSV**: Weekly timesheet with days as columns

## Contributing

I welcome contributions from the community! If you have ideas for features or improvements, please feel free to open an issue or submit a pull request.

## License

This project isn't licensed... pretty please don't steal and claim as your own?

## Acknowledgements

Special thanks to the developers of the libraries and APIs used in this project, including Rumps, Google Auth, and PyPresence.