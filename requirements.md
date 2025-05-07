# cLockIn - Time Tracking Application Requirements Document

## 1. Executive Summary

cLockIn is a macOS menu bar application designed to track time spent on various tasks and projects. The application integrates with Google Calendar for synchronization and optionally with Discord for rich presence updates. This document outlines the comprehensive requirements for the enhanced version of cLockIn, which expands upon the original functionality to provide a more robust task categorization system and timesheet functionality primarily geared toward consulting work.

## 2. System Overview

### 2.1 Current System Capabilities

* Time tracking through the macOS menu bar
* Google Calendar integration for logging tasks
* Discord rich presence integration
* Simple task entry and tracking
* Basic task duration visibility
* Run at startup capability

### 2.2 Enhanced System Requirements

* Hierarchical organization of tasks under categories
* Advanced task input with autocomplete functionality
* Global keyboard shortcut for quick task entry
* Export capabilities for timesheet generation
* Extended task history and reporting
* Category-based color coding and visualization

## 3. Detailed Functional Requirements

### 3.1 Data Model

#### 3.1.1 Category

* **Definition** : A grouping mechanism primarily used for consulting clients
* **Properties** :
* Name (string, unique identifier)
* Color (auto-generated based on name hash, consistent)
* Associated tasks (collection)
* **Functionality** :
* Create, retrieve, update categories
* Generate consistent color based on name
* Format for Google Calendar events
* Export data in CSV format

#### 3.1.2 Task

* **Definition** : A specific activity that is tracked
* **Properties** :
* Name (string)
* Category (optional reference to Category)
* Time entries (collection)
* **Relationships** :
* Category (0..1) ← Task (0.. *) ← TimeEntry (1..* )
* **Functionality** :
* Calculate total duration across all time entries
* Calculate current active duration
* Start/pause/stop tracking
* Format for display and export

#### 3.1.3 TimeEntry

* **Definition** : A specific time period spent on a task
* **Properties** :
* Start time (datetime with timezone)
* End time (optional datetime with timezone)
* Duration (calculated)
* **Functionality** :
* Calculate duration
* Convert to calendar event format
* Export in various formats

#### 3.1.4 Storage

* **Location** : Local filesystem at ~/.clockin/
* **Format** : JSON-based data store
* **Persistence** : Unencrypted local storage
* **Functionality** :
* Load data on application start
* Save data after each state change
* Maintain backward compatibility
* Export data in CSV format

### 3.2 User Interface

#### 3.2.1 Menu Bar Component

* **Display** : Show current task name and elapsed time
* **Extended Display** : Show both current session time and total task time when appropriate
* **Menu Structure** :
* Current/recent tasks section
* Play/pause/stop controls for active task
* Categories submenu with associated tasks
* Export options for each category
* Preferences section
* Quit option

#### 3.2.2 Task Input Interface

* **Appearance** :
* Spotlight-style floating window
* Dark, semi-transparent with frosted glass effect
* Rounded corners and modern macOS aesthetic
* Position centered near the top of the screen
* **Core Functionality** :
* Single text field for input
* Keyboard-driven workflow (no buttons)
* Parse '@' symbol for category selection
* Tab completion for categories and tasks
* Visual differentiation between category and task components
* Animation for appearance/disappearance

#### 3.2.3 Autocomplete Component

* **Appearance** :
* Dropdown below the input field
* Same styling as the main input window
* Scrollable list with subtle highlighting
* **Functionality** :
* Filter suggestions based on current input
* Tab cycling through available options
* Visual indicators for selection
* Category/task differentiation
* Display task duration in suggestions

#### 3.2.4 Visual Styling

* **Categories** :
* Display with [@Category] format where the square brackets are just this guide's representation of a rounded and colored border/fill behind the category.
* Background color derived from category name
* Consistent color generation algorithm
* Text color optimized for contrast
* **Tasks** :
* Display with (Task) format where the parentheses are this guide's representation of a rounded and slightly tinted border/fill behind the task
* Light gray background for active task
* Clear visual hierarchy between category and task

### 3.3 Interaction Flow

#### 3.3.1 Global Shortcut

* **Default** : CMD+SHIFT+CTRL+T
* **Behavior** : Bring up task input window from anywhere in the system
* **Configuration** : Toggle in preferences menu

#### 3.3.2 Task Entry

* **Basic Flow** :

1. Activate via global shortcut or menu bar
2. Type directly for uncategorized task
3. Use @ prefix for category selection
4. Press Enter to confirm
5. Escape to cancel

* **Category Mode** :
* Enter with @ as first character
* Tab to cycle through existing categories
* Enter to confirm selection
* Backspace to delete and exit category mode
* **Task Mode** :
* After category selection or directly
* Tab to cycle through existing tasks
* Enter to confirm selection
* Backspace to delete (whole task if selected via Tab)
* **Example Input Sequences** :

1. `@ABC Consulting <ENTER> Design homepage <ENTER>` - Create and start a new task (Design homepage) in a category (ABC Consulting)
2. `@<TAB><TAB><ENTER> Meeting notes <ENTER>` - Select category via Tab and create new task
3. `<TAB><TAB><ENTER>` - Select and restart an existing uncategorized task
4. `@<TAB><ENTER><BACKSPACE>@<TAB><ENTER>New task <ENTER>` - Change category selection

#### 3.3.3 Task Management

* **Start Task** :
* Begin tracking time for a new or existing task
* Update menu bar with task name and timer
* **Pause Task** :
* Stop the timer but maintain the task as current
* Create a Google Calendar entry for the completed segment
* Update menu bar to indicate paused state
* **Stop Task** :
* Complete the task and create Google Calendar entry
* Clear current task state
* Update Discord presence if enabled

#### 3.3.4 Data Export

* **Format Options** :
* Simple CSV: task_name;total_time_spent
* Detailed CSV: task_name;start_time;end_time;duration
* Weekly CSV: Date-based columns with task rows
* **Export Flow** :

1. Select category from menu
2. Choose export format
3. File is automatically saved to Downloads folder
4. File is opened with default application

### 3.4 External Integrations

#### 3.4.1 Google Calendar

* **Authentication** : OAuth 2.0 with proper scopes
* **Calendar Creation** : Custom "cLockIn" calendar
* **Event Format** :
* Task name: "@CATEGORY_NAME/TASK_NAME" or "TASK_NAME"
* Time: Start and end times for each time entry
* Color: Derived from category color

#### 3.4.2 Discord Rich Presence

* **Authentication** : Using client ID from .env.local file
* **Display Format** :
* Details: Task name with category prefix
* State: Total time spent
* Start Time: Beginning of current session
* Large Image: App icon
* Large Text: "Locked in"

## 4. Technical Requirements

### 4.1 Architecture

* **Pattern** : Object-oriented architecture with clear separation of concerns
* **Components** :
* Data models (Category, Task, TimeEntry)
* Storage management
* UI components (menu bar, input window, autocomplete)
* Integration adapters (Google, Discord)
* Export utilities

### 4.2 Application Structure

* **Core Files** :
* app.py: Main application logic
* models.py: Data model definitions
* textinput.py: Custom input window
* autocomplete.py: Autocomplete functionality
* shortcut_manager.py: Global shortcut handling
* csv_export.py: Timesheet export utilities

### 4.3 Dependencies

* **Required Libraries** :
* rumps: Menu bar functionality
* PyObjC: macOS Cocoa integration
* google-auth/google-api-python-client: Google Calendar integration
* pypresence: Discord rich presence
* python-dateutil: Date handling
* python-dotenv: Environment configuration

### 4.4 Compatibility

* **Operating System** : macOS only
* **Python Version** : 3.12 (3.9+ compatible)
* **Accessibility** : Requires accessibility permissions for global shortcut

### 4.5 Performance

* **Memory Footprint** : Minimal (<100MB)
* **CPU Usage** : <1% during idle, <5% during active use
* **Storage** : <10MB for application, varies for task history

## 5. User Experience Requirements

### 5.1 Usability

* **Learning Curve** : Minimal, discoverable through menu exploration
* **Keyboard Efficiency** : Primary workflows accessible via keyboard only
* **Visual Feedback** : Clear indication of current state and available actions

### 5.2 Accessibility

* **Color Contrast** : Ensure readable text against auto-generated colors
* **Keyboard Navigation** : Complete functionality via keyboard

### 5.3 Error Handling

* **Network Issues** : Graceful degradation when Google/Discord unavailable
* **Data Integrity** : Prevent data loss through regular saving
* **User Errors** : Clear error messages and recovery paths

## 6. Security and Privacy

### 6.1 Data Storage

* **Local Storage** : Unencrypted JSON in user's home directory
* **Google Data** : OAuth 2.0 token stored locally
* **Access Control** : Normal file system permissions

### 6.2 Third-Party Access

* **Google Calendar** : Limited to explicitly granted permissions
* **Discord** : Limited to rich presence updates
* **API Usage** : Following best practices for API authorization

## 7. Quality Assurance

### 7.1 Testing Scenarios

* **Task Creation** : Various combinations of category and task inputs
* **Autocomplete** : Testing with existing categories and tasks
* **Time Tracking** : Accuracy of duration calculations
* **Export** : Validation of CSV format correctness
* **Integration** : Verify Google Calendar entries match expected format

### 7.2 Edge Cases

* **Long-Running Tasks** : Tasks spanning multiple days
* **Many Categories/Tasks** : Performance with large data sets
* **Special Characters** : Handling in names, exports, and integrations
* **System Sleep** : Proper handling of tracking during sleep/wake cycles

## 8. Implementation Guidelines

### 8.1 Code Organization

* **Object-Oriented** : Utilize classes for clean separation of concerns
* **File Structure** : Separate files for different components
* **Naming Conventions** : Clear, descriptive names following Python conventions

### 8.2 UI Implementation

* **Cocoa Integration** : Use PyObjC for native macOS components
* **Visual Styling** : Implement frosted glass effects and modern aesthetics
* **Animation** : Smooth transitions for window appearance/disappearance

### 8.3 Data Processing

* **Time Calculations** : Properly handle timezone-aware datetimes
* **String Parsing** : Robust parsing of user input with appropriate error handling
* **CSV Generation** : Properly formatted and escaped data

## 9. Deployment

### 9.1 Installation

* **Requirements** : Clear documentation of prerequisites
* **Setup Process** : Simple step-by-step instructions
* **Dependencies** : Managed via requirements.txt

### 9.2 Auto-Start

* **LaunchAgent** : Configuration for automatic startup
* **Permissions** : Clear instructions for required accessibility permissions

## Appendix A: Input Parsing Specification

### Category Mode Syntax

<pre><div class="relative group/copy rounded-lg"><div class="sticky opacity-0 group-hover/copy:opacity-100 top-2 py-2 h-12 w-0 float-right"><div class="absolute right-0 h-8 px-2 items-center inline-flex"><button class="inline-flex
  items-center
  justify-center
  relative
  shrink-0
  can-focus
  select-none
  disabled:pointer-events-none
  disabled:opacity-50
  disabled:shadow-none
  disabled:drop-shadow-none text-text-300
          border-transparent
          transition
          font-styrene
          duration-300
          ease-[cubic-bezier(0.165,0.85,0.45,1)]
          hover:bg-bg-400
          aria-pressed:bg-bg-400
          aria-checked:bg-bg-400
          aria-expanded:bg-bg-300
          hover:text-text-100
          aria-pressed:text-text-100
          aria-checked:text-text-100
          aria-expanded:text-text-100 h-8 w-8 rounded-md active:scale-95 backdrop-blur-md" type="button" aria-label="Copy to clipboard" data-state="closed"><div class="relative"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256" class="transition-all opacity-100 scale-100"><path d="M200,32H163.74a47.92,47.92,0,0,0-71.48,0H56A16,16,0,0,0,40,48V216a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V48A16,16,0,0,0,200,32Zm-72,0a32,32,0,0,1,32,32H96A32,32,0,0,1,128,32Zm72,184H56V48H82.75A47.93,47.93,0,0,0,80,64v8a8,8,0,0,0,8,8h80a8,8,0,0,0,8-8V64a47.93,47.93,0,0,0-2.75-16H200Z"></path></svg><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256" class="absolute top-0 left-0 transition-all opacity-0 scale-50"><path d="M229.66,77.66l-128,128a8,8,0,0,1-11.32,0l-56-56a8,8,0,0,1,11.32-11.32L96,188.69,218.34,66.34a8,8,0,0,1,11.32,11.32Z"></path></svg></div></button></div></div><div class=""><pre class="code-block__code !my-0 !rounded-lg !text-sm !leading-relaxed"><code><span><span>@CATEGORY_NAME  → Enters/creates a category
</span></span><span>[@CATEGORY_NAME] → Visual representation of selected category
</span><span><Tab> → Cycle through existing categories
</span><span><Enter> → Confirm category selection
</span><span><Backspace> → Delete character or entire category object if completed</span></code></pre></div></div></pre>

### Task Mode Syntax

<pre><div class="relative group/copy rounded-lg"><div class="sticky opacity-0 group-hover/copy:opacity-100 top-2 py-2 h-12 w-0 float-right"><div class="absolute right-0 h-8 px-2 items-center inline-flex"><button class="inline-flex
  items-center
  justify-center
  relative
  shrink-0
  can-focus
  select-none
  disabled:pointer-events-none
  disabled:opacity-50
  disabled:shadow-none
  disabled:drop-shadow-none text-text-300
          border-transparent
          transition
          font-styrene
          duration-300
          ease-[cubic-bezier(0.165,0.85,0.45,1)]
          hover:bg-bg-400
          aria-pressed:bg-bg-400
          aria-checked:bg-bg-400
          aria-expanded:bg-bg-300
          hover:text-text-100
          aria-pressed:text-text-100
          aria-checked:text-text-100
          aria-expanded:text-text-100 h-8 w-8 rounded-md active:scale-95 backdrop-blur-md" type="button" aria-label="Copy to clipboard" data-state="closed"><div class="relative"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256" class="transition-all opacity-100 scale-100"><path d="M200,32H163.74a47.92,47.92,0,0,0-71.48,0H56A16,16,0,0,0,40,48V216a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V48A16,16,0,0,0,200,32Zm-72,0a32,32,0,0,1,32,32H96A32,32,0,0,1,128,32Zm72,184H56V48H82.75A47.93,47.93,0,0,0,80,64v8a8,8,0,0,0,8,8h80a8,8,0,0,0,8-8V64a47.93,47.93,0,0,0-2.75-16H200Z"></path></svg><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256" class="absolute top-0 left-0 transition-all opacity-0 scale-50"><path d="M229.66,77.66l-128,128a8,8,0,0,1-11.32,0l-56-56a8,8,0,0,1,11.32-11.32L96,188.69,218.34,66.34a8,8,0,0,1,11.32,11.32Z"></path></svg></div></button></div></div><div class=""><pre class="code-block__code !my-0 !rounded-lg !text-sm !leading-relaxed"><code><span><span>TASK_NAME → Direct task input
</span></span><span>(TASK_NAME) → Visual representation of task
</span><span><Tab> → Cycle through existing tasks
</span><span><Enter> → Confirm task and start timer
</span><span><Escape> → Cancel input</span></code></pre></div></div></pre>

### Combined Syntax Examples

<pre><div class="relative group/copy rounded-lg"><div class="sticky opacity-0 group-hover/copy:opacity-100 top-2 py-2 h-12 w-0 float-right"><div class="absolute right-0 h-8 px-2 items-center inline-flex"><button class="inline-flex
  items-center
  justify-center
  relative
  shrink-0
  can-focus
  select-none
  disabled:pointer-events-none
  disabled:opacity-50
  disabled:shadow-none
  disabled:drop-shadow-none text-text-300
          border-transparent
          transition
          font-styrene
          duration-300
          ease-[cubic-bezier(0.165,0.85,0.45,1)]
          hover:bg-bg-400
          aria-pressed:bg-bg-400
          aria-checked:bg-bg-400
          aria-expanded:bg-bg-300
          hover:text-text-100
          aria-pressed:text-text-100
          aria-checked:text-text-100
          aria-expanded:text-text-100 h-8 w-8 rounded-md active:scale-95 backdrop-blur-md" type="button" aria-label="Copy to clipboard" data-state="closed"><div class="relative"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256" class="transition-all opacity-100 scale-100"><path d="M200,32H163.74a47.92,47.92,0,0,0-71.48,0H56A16,16,0,0,0,40,48V216a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V48A16,16,0,0,0,200,32Zm-72,0a32,32,0,0,1,32,32H96A32,32,0,0,1,128,32Zm72,184H56V48H82.75A47.93,47.93,0,0,0,80,64v8a8,8,0,0,0,8,8h80a8,8,0,0,0,8-8V64a47.93,47.93,0,0,0-2.75-16H200Z"></path></svg><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256" class="absolute top-0 left-0 transition-all opacity-0 scale-50"><path d="M229.66,77.66l-128,128a8,8,0,0,1-11.32,0l-56-56a8,8,0,0,1,11.32-11.32L96,188.69,218.34,66.34a8,8,0,0,1,11.32,11.32Z"></path></svg></div></button></div></div><div class=""><pre class="code-block__code !my-0 !rounded-lg !text-sm !leading-relaxed"><code><span><span>[@ABC Consulting] (Design Homepage)
</span></span><span>(Meeting Notes)
</span><span>[@XYZ Inc] (Order supplies)</span></code></pre></div></div></pre>

## Appendix B: Color Generation Algorithm

The category color generation uses the following algorithm:

1. Create MD5 hash of the category name
2. Convert hash to integer
3. Use modulo to get a hue value (0-359)
4. Use fixed saturation (0.6) and lightness (0.7) values
5. Convert HSL to RGB and then to hex
6. Result is consistent for the same name

## Appendix C: Keyboard Shortcut Implementation

The global keyboard shortcut implementation uses:

1. CGEventTapCreate to monitor key events
2. Event filtering based on keycode and modifier flags
3. Callback invocation when shortcut is detected
4. Default configuration: CMD+SHIFT+CTRL+T

This requirements document provides a comprehensive overview of the cLockIn application, including both existing and enhanced functionality. It serves as a guide for implementation, testing, and future development of the application.
