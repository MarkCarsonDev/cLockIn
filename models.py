import json
import os
import hashlib
import colorsys
import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import rumps
class Category:
    def __init__(self, name: str):
        self.name = name.strip()
        self.color = self.generate_color_from_name()
        
    def generate_color_from_name(self) -> str:
        """Generate a consistent color based on the category name"""
        # Hash the name to get a consistent numeric value
        hash_obj = hashlib.md5(self.name.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        # Use the hash to generate HSL values - keeping saturation and lightness constant
        # for consistent readability
        hue = hash_int % 360 / 360.0
        saturation = 0.6  # Medium saturation
        lightness = 0.7   # Relatively light for good contrast with text
        
        # Convert HSL to RGB
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        
        # Convert to hex
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'color': self.color
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Category':
        category = cls(data['name'])
        if 'color' in data:
            category.color = data['color']
        return category


@dataclass
class TimeEntry:
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    
    # In TimeEntry class
    def duration(self) -> float:
        """Return duration in seconds, or 0 if the entry is not complete"""
        if not self.end_time:
            return 0
        
        # Ensure both times are in UTC for consistent calculations
        start_utc = self.start_time.astimezone(datetime.timezone.utc)
        end_utc = self.end_time.astimezone(datetime.timezone.utc)
        
        return (end_utc - start_utc).total_seconds()

    
    def to_dict(self) -> Dict:
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TimeEntry':
        return cls(
            start_time=datetime.datetime.fromisoformat(data['start_time']),
            end_time=datetime.datetime.fromisoformat(data['end_time']) if data.get('end_time') else None
        )


class Task:
    def __init__(self, name: str, category: Optional[Category] = None):
        self.name = name.strip()
        self.category = category
        self.time_entries: List[TimeEntry] = []
    
    def total_duration(self) -> float:
        """Return the total duration of all completed time entries in seconds"""
        return sum(entry.duration() for entry in self.time_entries if entry.end_time)
    
    def current_duration(self) -> float:
        """Return the duration of the current active time entry in seconds, or 0 if none"""
        current = self.current_entry()
        if current and not current.end_time:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            start_utc = current.start_time.astimezone(datetime.timezone.utc)
            return (now_utc - start_utc).total_seconds()
        return 0
    
    def full_duration(self) -> float:
        """Return the total duration including the current active entry"""
        return self.total_duration() + self.current_duration()
    
    def current_entry(self) -> Optional[TimeEntry]:
        """Return the current active time entry, if any"""
        if self.time_entries and not self.time_entries[-1].end_time:
            return self.time_entries[-1]
        return None
    
    def is_active(self) -> bool:
        """Check if this task has an active time entry"""
        return self.current_entry() is not None
    
    def start(self) -> None:
        """Start a new time entry for this task"""
        self.time_entries.append(TimeEntry(
            start_time=datetime.datetime.now(datetime.timezone.utc)
        ))
    
    def pause(self) -> None:
        """Pause the current time entry if active"""
        current = self.current_entry()
        if current:
            current.end_time = datetime.datetime.now(datetime.timezone.utc)
    
    def format_for_calendar(self) -> str:
        """Format task name for Google Calendar, including category if present"""
        if self.category:
            return f"@{self.category.name}/{self.name}"
        return self.name
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'category': self.category.to_dict() if self.category else None,
            'time_entries': [entry.to_dict() for entry in self.time_entries]
        }
    
    @classmethod
    def from_dict(cls, data: Dict, categories: Dict[str, Category]) -> 'Task':
        category = None
        if data.get('category'):
            category_name = data['category'].get('name') if isinstance(data['category'], dict) else data['category']
            category = categories.get(category_name)
        
        task = cls(data['name'], category)
        
        # Recreate time entries
        if 'time_entries' in data:
            task.time_entries = [TimeEntry.from_dict(entry_data) for entry_data in data['time_entries']]
        
        return task


class DataStorage:
    def __init__(self, storage_file: str = "clockin_data.json"):
        self.storage_file = os.path.expanduser(f"~/.clockin/{storage_file}")
        self.categories: Dict[str, Category] = {}
        self.tasks: List[Task] = []
        self.time_zone = None  # Default time zone is None (will fall back to system default)
        self.load()
    
    # Add these new methods
    def set_time_zone(self, time_zone_name: str) -> None:
        """Set the preferred time zone"""
        self.time_zone = time_zone_name
        self.save()
    
    def get_time_zone(self) -> str:
        """Get the preferred time zone"""
        return self.time_zone
    
    def ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists"""
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        
    def _handle_corrupted_data(self):
        """Handle corrupted data by backing up and initializing empty data"""
        backup_file = f"{self.storage_file}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            if os.path.exists(self.storage_file):
                import shutil
                shutil.copy2(self.storage_file, backup_file)
                print(f"Corrupted data file backed up to {backup_file}")
        except Exception as e:
            print(f"Failed to backup corrupted data: {e}")
        
        # Initialize empty data
        self.categories = {}
        self.tasks = []
        
        # Show notification to user
        rumps.notification(
            "Data Error",
            "Could not load your task data. A backup has been created.",
            f"Backup file: {backup_file}"
        )

    def save(self) -> None:
        """Save data to storage file"""
        self.ensure_storage_dir()
        
        data = {
            'categories': [cat.to_dict() for cat in self.categories.values()],
            'tasks': [task.to_dict() for task in self.tasks],
            'time_zone': self.time_zone  # Add time zone to saved data
        }
        
        # Write to a temporary file first, then rename for atomic operation
        temp_file = f"{self.storage_file}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # On Unix systems like macOS, rename is an atomic operation
            import os
            if os.path.exists(self.storage_file):
                os.replace(temp_file, self.storage_file)
            else:
                os.rename(temp_file, self.storage_file)
        except Exception as e:
            print(f"Error saving data: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    def load(self) -> None:
        """Load data from storage file with enhanced error handling"""
        self.ensure_storage_dir()
        if not os.path.exists(self.storage_file):
            return
        
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Recreate categories
            self.categories = {}
            for cat_data in data.get('categories', []):
                if isinstance(cat_data, dict):
                    category = Category.from_dict(cat_data)
                    self.categories[category.name] = category
                else:
                    # Handle old format where categories were just strings
                    category = Category(cat_data)
                    self.categories[category.name] = category
            
            # Recreate tasks
            self.tasks = []
            for task_data in data.get('tasks', []):
                task = Task.from_dict(task_data, self.categories)
                self.tasks.append(task)
                
            # Load time zone
            self.time_zone = data.get('time_zone')
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON data: {e}")
            self._handle_corrupted_data()
        except Exception as e:
            print(f"Error loading data: {e}")
            self._handle_corrupted_data()
    
    def add_category(self, name: str) -> Category:
        """Add a new category or return existing one with sanitized name"""
        # Sanitize name: remove leading/trailing whitespace and control characters
        name = ''.join(c for c in name.strip() if c.isprintable() or c.isspace())
        
        if not name:
            # If name is empty after sanitization, use a default name
            name = f"Category {len(self.categories) + 1}"
        
        if name not in self.categories:
            self.categories[name] = Category(name)
            self.save()
        return self.categories[name]
    
    def get_categories(self) -> List[Category]:
        """Return sorted list of categories"""
        return sorted(self.categories.values(), key=lambda c: c.name)
    
    def get_tasks(self, category: Optional[Category] = None) -> List[Task]:
        """Return tasks, optionally filtered by category"""
        if category:
            return [t for t in self.tasks if t.category and t.category.name == category.name]
        return [t for t in self.tasks if not t.category]  # Only uncategorized tasks
    
    def get_all_tasks(self) -> List[Task]:
        """Return all tasks"""
        return self.tasks
    
    def add_task(self, name: str, category: Optional[Category] = None) -> Task:
        """Add a new task with sanitized name"""
        # Sanitize name: remove leading/trailing whitespace and control characters
        name = ''.join(c for c in name.strip() if c.isprintable() or c.isspace())
        
        if not name:
            # If name is empty after sanitization, use a default name
            name = f"Task {len(self.tasks) + 1}"
        
        task = Task(name=name, category=category)
        self.tasks.append(task)
        self.save()
        return task
    
    def find_task(self, name: str, category: Optional[Category] = None) -> Optional[Task]:
        """Find a task by name and optional category"""
        for task in self.tasks:
            if task.name.lower() == name.lower():
                if (category is None and task.category is None) or \
                   (category and task.category and task.category.name == category.name):
                    return task
        return None
    
    def get_or_create_task(self, name: str, category: Optional[Category] = None) -> Task:
        """Find an existing task or create a new one"""
        task = self.find_task(name, category)
        if not task:
            task = self.add_task(name, category)
        return task
    
    def get_active_task(self) -> Optional[Task]:
        """Return the currently active task, if any"""
        for task in self.tasks:
            if task.is_active():
                return task
        return None
    
    def export_category_csv(self, category: Category) -> str:
        """Export a CSV for the given category"""
        tasks = self.get_tasks(category)
        if not tasks:
            return ""
        
        csv_content = "task_name;total_time_spent\n"
        for task in tasks:
            total_seconds = task.full_duration()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            csv_content += f"{task.name};{hours}h {minutes}m\n"
        
        return csv_content