"""Context Engine - Synthesizes user context from multiple data sources."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field

from app.context.models import (
    UserContext,
    UserState,
    CalendarEvent,
    EnvironmentContext,
    TaskContext,
    TimeContext,
    Location,
    PendingTask,
)
from app.logger import logger


class ContextCache(BaseModel):
    """Cache for context data with TTL."""
    
    data: Optional[UserContext] = None
    last_updated: Optional[datetime] = None
    ttl_seconds: int = 60
    
    def is_valid(self) -> bool:
        """Check if cached data is still valid."""
        if not self.data or not self.last_updated:
            return False
        return (datetime.now() - self.last_updated).total_seconds() < self.ttl_seconds
    
    def set(self, context: UserContext) -> None:
        """Update cache with new context."""
        self.data = context
        self.last_updated = datetime.now()
    
    def get(self) -> Optional[UserContext]:
        """Get cached context if valid."""
        return self.data if self.is_valid() else None
    
    def invalidate(self) -> None:
        """Invalidate the cache."""
        self.data = None
        self.last_updated = None


class ContextEngine:
    """
    Synthesizes user context from multiple data sources.
    
    The Context Engine aggregates data from calendar, email, location,
    and other sources to build a comprehensive understanding of the
    user's current situation and upcoming needs.
    """
    
    def __init__(
        self,
        calendar_client: Optional[Any] = None,
        email_client: Optional[Any] = None,
        location_service: Optional[Any] = None,
        cache_ttl: int = 60
    ):
        """
        Initialize the Context Engine.
        
        Args:
            calendar_client: Client for calendar integration
            email_client: Client for email integration
            location_service: Service for location data
            cache_ttl: Cache time-to-live in seconds
        """
        self.calendar_client = calendar_client
        self.email_client = email_client
        self.location_service = location_service
        self.cache = ContextCache(ttl_seconds=cache_ttl)
        self._listeners: List[callable] = []
        
    async def get_current_context(self, use_cache: bool = True) -> UserContext:
        """
        Get the current user context.
        
        Args:
            use_cache: Whether to use cached context if available
            
        Returns:
            Comprehensive UserContext object
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get()
            if cached:
                logger.debug("Returning cached context")
                return cached
        
        # Gather data from all sources concurrently
        calendar_data, location_data, task_data = await asyncio.gather(
            self._get_calendar_data(),
            self._get_location_data(),
            self._get_task_data(),
            return_exceptions=True
        )
        
        # Handle any errors in data fetching
        if isinstance(calendar_data, Exception):
            logger.warning(f"Failed to get calendar data: {calendar_data}")
            calendar_data = {"events": [], "current_event": None}
            
        if isinstance(location_data, Exception):
            logger.warning(f"Failed to get location data: {location_data}")
            location_data = None
            
        if isinstance(task_data, Exception):
            logger.warning(f"Failed to get task data: {task_data}")
            task_data = {"pending": [], "current": None}
        
        # Synthesize context
        context = self._synthesize_context(calendar_data, location_data, task_data)
        
        # Update cache
        self.cache.set(context)
        
        # Notify listeners
        await self._notify_listeners(context)
        
        return context
    
    async def _get_calendar_data(self) -> Dict[str, Any]:
        """Fetch calendar data from the calendar client."""
        if not self.calendar_client:
            return {"events": [], "current_event": None}
        
        try:
            # Get events for the next 24 hours
            now = datetime.now()
            end_time = now + timedelta(hours=24)
            
            events = await self.calendar_client.get_events(
                start_time=now,
                end_time=end_time
            )
            
            # Find current event
            current_event = None
            for event in events:
                if event.start_time <= now <= event.end_time:
                    current_event = event
                    break
            
            return {
                "events": events,
                "current_event": current_event
            }
        except Exception as e:
            logger.error(f"Error fetching calendar data: {e}")
            raise
    
    async def _get_location_data(self) -> Optional[Location]:
        """Fetch current location from the location service."""
        if not self.location_service:
            return None
        
        try:
            return await self.location_service.get_current_location()
        except Exception as e:
            logger.error(f"Error fetching location data: {e}")
            raise
    
    async def _get_task_data(self) -> Dict[str, Any]:
        """Extract task data from email and other sources."""
        tasks = []
        current_task = None
        
        if self.email_client:
            try:
                # Extract action items from recent emails
                email_tasks = await self.email_client.extract_action_items()
                tasks.extend(email_tasks)
            except Exception as e:
                logger.warning(f"Error extracting email tasks: {e}")
        
        return {
            "pending": tasks,
            "current": current_task
        }
    
    def _synthesize_context(
        self,
        calendar_data: Dict[str, Any],
        location_data: Optional[Location],
        task_data: Dict[str, Any]
    ) -> UserContext:
        """
        Synthesize a comprehensive context from all data sources.
        
        Args:
            calendar_data: Calendar events and current event
            location_data: Current location
            task_data: Pending and current tasks
            
        Returns:
            Synthesized UserContext
        """
        # Create time context
        time_context = TimeContext()
        
        # Create environment context
        environment = EnvironmentContext(
            current_location=location_data
        )
        
        # Create task context
        task_context = TaskContext(
            pending_tasks=task_data.get("pending", []),
            current_task=task_data.get("current")
        )
        
        # Process calendar events
        events = calendar_data.get("events", [])
        current_event = calendar_data.get("current_event")
        
        # Mark events that require travel
        if location_data:
            for event in events:
                if event.location:
                    event.requires_travel = self._requires_travel(
                        location_data,
                        event.location
                    )
        
        # Infer user state
        state = self._infer_state(
            current_event=current_event,
            upcoming_events=events[:5],
            time_context=time_context,
            location=location_data
        )
        
        # Calculate confidence score
        confidence = self._calculate_confidence(
            has_calendar=bool(self.calendar_client),
            has_location=location_data is not None,
            has_tasks=bool(task_data.get("pending"))
        )
        
        return UserContext(
            state=state,
            time_context=time_context,
            environment=environment,
            task_context=task_context,
            current_event=current_event,
            upcoming_events=events[:10],
            last_updated=datetime.now(),
            confidence_score=confidence
        )
    
    def _infer_state(
        self,
        current_event: Optional[CalendarEvent],
        upcoming_events: List[CalendarEvent],
        time_context: TimeContext,
        location: Optional[Location]
    ) -> UserState:
        """
        Infer the user's current state from available data.
        
        Args:
            current_event: Currently ongoing event
            upcoming_events: List of upcoming events
            time_context: Current time context
            location: Current location
            
        Returns:
            Inferred UserState
        """
        # If in a meeting
        if current_event:
            title_lower = current_event.title.lower()
            if any(word in title_lower for word in ["meeting", "call", "sync", "standup"]):
                return UserState.IN_MEETING
            return UserState.BUSY
        
        # Check if traveling to next event
        if upcoming_events and location:
            next_event = upcoming_events[0]
            if next_event.requires_travel and next_event.starts_within(60):
                return UserState.TRAVELING
        
        # Check time-based states
        if not time_context.is_work_hours:
            return UserState.AVAILABLE
        
        # Default to working during work hours
        if time_context.is_work_hours:
            return UserState.WORKING
        
        return UserState.IDLE
    
    def _requires_travel(self, current: Location, destination: str) -> bool:
        """
        Determine if travel is required to reach a destination.
        
        Args:
            current: Current location
            destination: Destination address/name
            
        Returns:
            True if travel is likely required
        """
        # Simple heuristic: if destination is specified, assume travel needed
        # In a real implementation, this would use geocoding and distance calculation
        if not destination:
            return False
        
        # Skip virtual meetings
        virtual_keywords = ["zoom", "teams", "meet", "webex", "virtual", "online", "remote"]
        if any(kw in destination.lower() for kw in virtual_keywords):
            return False
        
        return True
    
    def _calculate_confidence(
        self,
        has_calendar: bool,
        has_location: bool,
        has_tasks: bool
    ) -> float:
        """
        Calculate confidence score based on available data sources.
        
        Args:
            has_calendar: Whether calendar data is available
            has_location: Whether location data is available
            has_tasks: Whether task data is available
            
        Returns:
            Confidence score between 0 and 1
        """
        score = 0.5  # Base score
        
        if has_calendar:
            score += 0.25
        if has_location:
            score += 0.15
        if has_tasks:
            score += 0.1
        
        return min(score, 1.0)
    
    def add_listener(self, callback: callable) -> None:
        """Add a listener for context updates."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: callable) -> None:
        """Remove a context update listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    async def _notify_listeners(self, context: UserContext) -> None:
        """Notify all listeners of a context update."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(context)
                else:
                    listener(context)
            except Exception as e:
                logger.error(f"Error notifying context listener: {e}")
    
    def invalidate_cache(self) -> None:
        """Invalidate the context cache."""
        self.cache.invalidate()
        logger.debug("Context cache invalidated")
