"""Context data models for proactive agents."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserState(str, Enum):
    """Possible user states inferred from context."""
    
    IDLE = "idle"
    WORKING = "working"
    IN_MEETING = "in_meeting"
    TRAVELING = "traveling"
    BUSY = "busy"
    AVAILABLE = "available"
    DO_NOT_DISTURB = "do_not_disturb"


class CalendarEvent(BaseModel):
    """Represents a calendar event."""
    
    id: str
    title: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    attendees: List[str] = Field(default_factory=list)
    is_all_day: bool = False
    requires_travel: bool = False
    
    @property
    def duration_minutes(self) -> int:
        """Calculate event duration in minutes."""
        return int((self.end_time - self.start_time).total_seconds() / 60)
    
    def starts_within(self, minutes: int) -> bool:
        """Check if event starts within the given minutes."""
        now = datetime.now()
        time_until_start = (self.start_time - now).total_seconds() / 60
        return 0 <= time_until_start <= minutes


class Location(BaseModel):
    """Represents a geographic location."""
    
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    name: Optional[str] = None
    
    def distance_to(self, other: "Location") -> Optional[float]:
        """Calculate distance to another location in kilometers."""
        if not all([self.latitude, self.longitude, other.latitude, other.longitude]):
            return None
        
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth's radius in km
        
        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        lat2, lon2 = radians(other.latitude), radians(other.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c


class PendingTask(BaseModel):
    """Represents a pending task or action item."""
    
    id: str
    title: str
    source: str  # e.g., "email", "calendar", "manual"
    priority: int = Field(default=0, ge=0, le=10)
    due_date: Optional[datetime] = None
    context: Optional[str] = None
    
    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.due_date:
            return False
        return datetime.now() > self.due_date


class TimeContext(BaseModel):
    """Temporal context information."""
    
    current_time: datetime = Field(default_factory=datetime.now)
    day_of_week: str = ""
    is_weekend: bool = False
    is_work_hours: bool = False
    time_of_day: str = ""  # morning, afternoon, evening, night
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.day_of_week:
            self.day_of_week = self.current_time.strftime("%A")
        self.is_weekend = self.current_time.weekday() >= 5
        
        hour = self.current_time.hour
        self.is_work_hours = 9 <= hour < 18 and not self.is_weekend
        
        if 5 <= hour < 12:
            self.time_of_day = "morning"
        elif 12 <= hour < 17:
            self.time_of_day = "afternoon"
        elif 17 <= hour < 21:
            self.time_of_day = "evening"
        else:
            self.time_of_day = "night"


class EnvironmentContext(BaseModel):
    """Environmental context information."""
    
    current_location: Optional[Location] = None
    weather: Optional[Dict[str, Any]] = None
    connectivity: str = "online"  # online, offline, limited
    device_type: str = "desktop"  # desktop, mobile, tablet


class TaskContext(BaseModel):
    """Context about current and pending tasks."""
    
    current_task: Optional[str] = None
    pending_tasks: List[PendingTask] = Field(default_factory=list)
    recently_completed: List[str] = Field(default_factory=list)
    blocked_tasks: List[str] = Field(default_factory=list)
    
    @property
    def overdue_count(self) -> int:
        """Count of overdue tasks."""
        return sum(1 for t in self.pending_tasks if t.is_overdue)
    
    @property
    def high_priority_count(self) -> int:
        """Count of high priority tasks (priority >= 7)."""
        return sum(1 for t in self.pending_tasks if t.priority >= 7)


class UserContext(BaseModel):
    """Comprehensive user context aggregating all context sources."""
    
    state: UserState = UserState.AVAILABLE
    time_context: TimeContext = Field(default_factory=TimeContext)
    environment: EnvironmentContext = Field(default_factory=EnvironmentContext)
    task_context: TaskContext = Field(default_factory=TaskContext)
    
    # Calendar data
    current_event: Optional[CalendarEvent] = None
    upcoming_events: List[CalendarEvent] = Field(default_factory=list)
    
    # Metadata
    last_updated: datetime = Field(default_factory=datetime.now)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    
    def get_next_event_requiring_travel(self) -> Optional[CalendarEvent]:
        """Get the next upcoming event that requires travel."""
        for event in self.upcoming_events:
            if event.requires_travel and event.location:
                return event
        return None
    
    def has_conflict(self, start: datetime, end: datetime) -> bool:
        """Check if there's a calendar conflict in the given time range."""
        for event in self.upcoming_events:
            if (start < event.end_time) and (end > event.start_time):
                return True
        return False
    
    def to_summary(self) -> str:
        """Generate a human-readable context summary."""
        parts = [
            f"State: {self.state.value}",
            f"Time: {self.time_context.time_of_day} on {self.time_context.day_of_week}",
        ]
        
        if self.current_event:
            parts.append(f"Currently in: {self.current_event.title}")
        
        if self.upcoming_events:
            next_event = self.upcoming_events[0]
            parts.append(f"Next: {next_event.title} at {next_event.start_time.strftime('%H:%M')}")
        
        if self.task_context.pending_tasks:
            parts.append(f"Pending tasks: {len(self.task_context.pending_tasks)}")
            if self.task_context.overdue_count > 0:
                parts.append(f"Overdue: {self.task_context.overdue_count}")
        
        return " | ".join(parts)
