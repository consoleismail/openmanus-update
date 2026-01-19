"""Calendar integration for context awareness."""

from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.integrations.base import IntegrationBase
from app.context.models import CalendarEvent
from app.logger import logger


class CalendarClient(IntegrationBase):
    """Abstract base class for calendar integrations."""
    
    name: str = "calendar"
    
    @abstractmethod
    async def get_events(
        self,
        start_time: datetime,
        end_time: datetime,
        max_results: int = 50
    ) -> List[CalendarEvent]:
        """Get events in a time range."""
        pass
    
    @abstractmethod
    async def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        """Get a specific event by ID."""
        pass
    
    async def get_upcoming_events(
        self,
        hours_ahead: int = 24,
        max_results: int = 10
    ) -> List[CalendarEvent]:
        """Get upcoming events."""
        now = datetime.now()
        end_time = now + timedelta(hours=hours_ahead)
        return await self.get_events(now, end_time, max_results)


class GoogleCalendarClient(CalendarClient):
    """
    Google Calendar integration.
    
    Uses Google Calendar API to fetch events and provide
    context for the proactive agent.
    """
    
    name: str = "google_calendar"
    
    # OAuth credentials
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None
    
    # Internal state
    _service: Any = None
    _connected: bool = False
    
    class Config:
        arbitrary_types_allowed = True
    
    async def connect(self) -> bool:
        """Connect to Google Calendar API."""
        try:
            # This is a placeholder - real implementation would
            # use google-api-python-client and oauth2client
            logger.info("Connecting to Google Calendar...")
            
            # In production:
            # from google.oauth2.credentials import Credentials
            # from googleapiclient.discovery import build
            # 
            # creds = Credentials(
            #     token=None,
            #     refresh_token=self.refresh_token,
            #     client_id=self.client_id,
            #     client_secret=self.client_secret,
            #     token_uri="https://oauth2.googleapis.com/token"
            # )
            # self._service = build('calendar', 'v3', credentials=creds)
            
            self._connected = True
            logger.info("Connected to Google Calendar")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Google Calendar: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Google Calendar."""
        self._service = None
        self._connected = False
        logger.info("Disconnected from Google Calendar")
    
    async def health_check(self) -> bool:
        """Check if the connection is healthy."""
        return self._connected
    
    async def get_events(
        self,
        start_time: datetime,
        end_time: datetime,
        max_results: int = 50
    ) -> List[CalendarEvent]:
        """Get events from Google Calendar."""
        if not self._connected:
            await self.connect()
        
        events = []
        
        try:
            # Placeholder - real implementation would call API:
            # result = self._service.events().list(
            #     calendarId='primary',
            #     timeMin=start_time.isoformat() + 'Z',
            #     timeMax=end_time.isoformat() + 'Z',
            #     maxResults=max_results,
            #     singleEvents=True,
            #     orderBy='startTime'
            # ).execute()
            # 
            # for item in result.get('items', []):
            #     event = self._parse_event(item)
            #     events.append(event)
            
            logger.debug(f"Fetched {len(events)} events from Google Calendar")
            
        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}")
        
        return events
    
    async def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        """Get a specific event."""
        if not self._connected:
            await self.connect()
        
        try:
            # Placeholder - real implementation would call:
            # item = self._service.events().get(
            #     calendarId='primary',
            #     eventId=event_id
            # ).execute()
            # return self._parse_event(item)
            pass
            
        except Exception as e:
            logger.error(f"Error fetching event {event_id}: {e}")
        
        return None
    
    def _parse_event(self, item: Dict) -> CalendarEvent:
        """Parse a Google Calendar event into our model."""
        # Parse start time
        start = item.get('start', {})
        start_time = datetime.fromisoformat(
            start.get('dateTime', start.get('date', '')).replace('Z', '+00:00')
        )
        
        # Parse end time
        end = item.get('end', {})
        end_time = datetime.fromisoformat(
            end.get('dateTime', end.get('date', '')).replace('Z', '+00:00')
        )
        
        # Get attendees
        attendees = [
            a.get('email', '')
            for a in item.get('attendees', [])
        ]
        
        return CalendarEvent(
            id=item.get('id', ''),
            title=item.get('summary', 'No Title'),
            start_time=start_time,
            end_time=end_time,
            location=item.get('location'),
            description=item.get('description'),
            attendees=attendees,
            is_all_day='date' in start,
        )


class MockCalendarClient(CalendarClient):
    """
    Mock calendar client for testing.
    
    Returns sample events for testing the proactive agent.
    """
    
    name: str = "mock_calendar"
    
    _mock_events: List[CalendarEvent] = Field(default_factory=list)
    
    async def connect(self) -> bool:
        """Connect (always succeeds for mock)."""
        return True
    
    async def disconnect(self) -> None:
        """Disconnect."""
        pass
    
    async def health_check(self) -> bool:
        """Health check (always healthy)."""
        return True
    
    async def get_events(
        self,
        start_time: datetime,
        end_time: datetime,
        max_results: int = 50
    ) -> List[CalendarEvent]:
        """Get mock events."""
        # Return events that fall within the time range
        return [
            e for e in self._mock_events
            if start_time <= e.start_time <= end_time
        ][:max_results]
    
    async def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        """Get a specific mock event."""
        for event in self._mock_events:
            if event.id == event_id:
                return event
        return None
    
    def add_mock_event(self, event: CalendarEvent) -> None:
        """Add a mock event."""
        self._mock_events.append(event)
    
    def clear_mock_events(self) -> None:
        """Clear all mock events."""
        self._mock_events.clear()
    
    @classmethod
    def with_sample_events(cls) -> "MockCalendarClient":
        """Create a mock client with sample events."""
        client = cls()
        
        now = datetime.now()
        
        # Add sample events
        client.add_mock_event(CalendarEvent(
            id="1",
            title="Team Standup",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=1, minutes=30),
            location="Conference Room A",
        ))
        
        client.add_mock_event(CalendarEvent(
            id="2",
            title="Client Meeting",
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
            location="123 Main St, Downtown",
            requires_travel=True,
        ))
        
        client.add_mock_event(CalendarEvent(
            id="3",
            title="Project Review",
            start_time=now + timedelta(hours=6),
            end_time=now + timedelta(hours=7),
            location="Zoom Meeting",
        ))
        
        return client
