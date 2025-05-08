import os
import csv
import datetime
import subprocess
from typing import Dict, List, Optional
import rumps
import zoneinfo

from models import Category, Task, DataStorage

class CSVExporter:
    """Class for exporting task data to CSV files"""
    def __init__(self, storage: DataStorage):
        self.storage = storage
        self.export_dir = os.path.expanduser("~/Downloads")
        
        # Ensure export directory exists
        try:
            os.makedirs(self.export_dir, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not ensure export directory exists: {e}")
            # Fall back to desktop if Downloads doesn't exist
            self.export_dir = os.path.expanduser("~/Desktop")
            try:
                os.makedirs(self.export_dir, exist_ok=True)
            except Exception as e:
                print(f"Warning: Could not ensure fallback export directory exists: {e}")
                # Fall back to current directory as last resort
                self.export_dir = os.getcwd()

    def get_preferred_timezone(self):
        """Get the preferred timezone or system default"""
        tz_name = self.storage.get_time_zone()
        if tz_name:
            try:
                return zoneinfo.ZoneInfo(tz_name)
            except Exception as e:
                print(f"Error getting time zone {tz_name}: {e}")
        
        # Fall back to system default
        return datetime.datetime.now().astimezone().tzinfo
    
    def convert_datetime_to_preferred_timezone(self, dt):
        """Convert a datetime to the preferred timezone"""
        if dt is None:
            return None
        
        # Make sure it has a timezone (use UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        
        # Convert to preferred timezone
        preferred_tz = self.get_preferred_timezone()
        return dt.astimezone(preferred_tz)

    def export_category_timesheet(self, category: Category) -> Optional[str]:
        """Export a simple CSV for the given category with improved error handling"""
        if not category:
            return None
        
        # Get tasks for this category
        tasks = self.storage.get_tasks(category)
        if not tasks:
            print(f"No tasks found for category: {category.name}")
            rumps.notification("Export Failed", f"No tasks found for category: {category.name}", "")
            return None
        
        # Create filename with timestamp using preferred timezone
        preferred_tz = self.get_preferred_timezone()
        timestamp = datetime.datetime.now().astimezone(preferred_tz).strftime("%Y%m%d_%H%M%S")
        
        # Sanitize filename by removing invalid characters
        category_name = ''.join(c for c in category.name if c.isalnum() or c in ' _-')
        filename = f"{category_name.replace(' ', '_')}_timesheet_{timestamp}.csv"
        filepath = os.path.join(self.export_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                # Write header row
                writer.writerow(['task_name', 'total_time_spent', 'timezone'])
                
                # Get timezone name for display
                tz_name = getattr(preferred_tz, 'key', str(preferred_tz))
                
                # Write task data rows
                for task in tasks:
                    total_seconds = task.full_duration()
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    time_str = f"{hours}h {minutes}m"
                    writer.writerow([task.name, time_str, tz_name])
            
            print(f"CSV exported successfully to {filepath} using {tz_name} timezone")
            return filepath
        except PermissionError:
            print(f"Permission denied when writing to {filepath}")
            rumps.notification("Export Failed", f"Permission denied when writing to {filepath}", "")
            return None
        except Exception as e:
            print(f"Error exporting CSV: {e}")
            rumps.notification("Export Failed", f"Error: {str(e)}", "")
            return None

    def export_detailed_timesheet(self, category: Category) -> Optional[str]:
        """Export a detailed timesheet CSV with individual time entries"""
        if not category:
            return None
        
        # Get tasks for this category
        tasks = self.storage.get_tasks(category)
        if not tasks:
            print(f"No tasks found for category: {category.name}")
            return None
        
        # Create filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{category.name.replace(' ', '_')}_detailed_{timestamp}.csv"
        filepath = os.path.join(self.export_dir, filename)
        
        try:
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                # Write header row
                writer.writerow(['Task','Day', 'Start', 'End', 'Duration'])
                
                # Get the preferred timezone for display
                preferred_tz = self.get_preferred_timezone()
                tz_name = getattr(preferred_tz, 'key', str(preferred_tz))
                
                # Write detailed time entry data
                for task in tasks:
                    for entry in task.time_entries:
                        if entry.end_time:  # Only include completed entries
                            # Convert times to preferred timezone
                            start_time_local = self.convert_datetime_to_preferred_timezone(entry.start_time)
                            end_time_local = self.convert_datetime_to_preferred_timezone(entry.end_time)
                            
                            # Format the times in the preferred timezone
                            calendar_day = start_time_local.strftime("%V %a %d/%m/%Y")
                            start_time_str = start_time_local.strftime("%Y-%m-%d %H:%M:%S")
                            end_time_str = end_time_local.strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Duration remains the same (calculated from UTC times)
                            duration_seconds = entry.duration()
                            hours = int(duration_seconds // 3600)
                            minutes = int((duration_seconds % 3600) // 60)
                            time_str = f"{hours}h {minutes}m"
                            
                            writer.writerow([task.name, calendar_day, start_time_str, end_time_str, time_str])
            
            print(f"Detailed CSV exported successfully to {filepath}")
            return filepath
        except Exception as e:
            print(f"Error exporting detailed CSV: {e}")
            return None
    
    def export_weekly_timesheet(self, category: Category) -> Optional[str]:
        """Export a weekly timesheet CSV with days as columns, using preferred timezone"""
        if not category:
            return None
        
        # Get tasks for this category
        tasks = self.storage.get_tasks(category)
        if not tasks:
            print(f"No tasks found for category: {category.name}")
            return None
        
        # Get start of the current week (Monday) in the preferred timezone
        preferred_tz = self.get_preferred_timezone()
        now_local = datetime.datetime.now().astimezone(preferred_tz)
        today = now_local.date()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        
        # Create a list of dates for the week
        dates = [(start_of_week + datetime.timedelta(days=i)) for i in range(7)]
        date_strs = [date.strftime("%Y-%m-%d") for date in dates]
        
        # Create filename with timestamp
        timestamp = now_local.strftime("%Y%m%d_%H%M%S")
        filename = f"{category.name.replace(' ', '_')}_weekly_{timestamp}.csv"
        filepath = os.path.join(self.export_dir, filename)
        
        try:
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                
                # Write header row with dates
                header = ['task_name'] + [date.strftime("%a %d/%m") for date in dates] + ['Total']
                writer.writerow(header)
                
                # Prepare data structure for organizing time entries by day
                task_days = {}
                
                # Process all time entries
                for task in tasks:
                    task_days[task.name] = {date_str: 0 for date_str in date_strs}
                    
                    for entry in task.time_entries:
                        if entry.end_time:  # Only include completed entries
                            # Convert start time to preferred timezone
                            local_start_time = self.convert_datetime_to_preferred_timezone(entry.start_time)
                            
                            # Get the date of this entry in local time
                            entry_date = local_start_time.date()
                            entry_date_str = entry_date.strftime("%Y-%m-%d")
                            
                            # If this date is in our week, add the duration
                            if entry_date_str in date_strs:
                                task_days[task.name][entry_date_str] += entry.duration()
                
                # Write task data rows
                for task_name, day_durations in task_days.items():
                    row = [task_name]
                    
                    # Add duration for each day
                    for date_str in date_strs:
                        seconds = day_durations[date_str]
                        if seconds > 0:
                            hours = int(seconds // 3600)
                            minutes = int((seconds % 3600) // 60)
                            row.append(f"{hours}h {minutes}m")
                        else:
                            row.append("")
                    
                    # Add total row
                    total_seconds = sum(day_durations.values())
                    if total_seconds > 0:
                        total_hours = int(total_seconds // 3600)
                        total_minutes = int((total_seconds % 3600) // 60)
                        row.append(f"{total_hours}h {total_minutes}m")
                    else:
                        row.append("")
                    
                    writer.writerow(row)
            
            print(f"Weekly CSV exported successfully to {filepath} using {getattr(preferred_tz, 'key', str(preferred_tz))} timezone")
            return filepath
        except Exception as e:
            print(f"Error exporting weekly CSV: {e}")
            return None
    
    def open_csv_file(self, filepath: str) -> bool:
        """Open the exported CSV file with the default application"""
        if not filepath or not os.path.exists(filepath):
            return False
        
        try:
            # On macOS, use 'open' command
            subprocess.run(['open', filepath])
            return True
        except Exception as e:
            print(f"Error opening CSV file: {e}")
            return False