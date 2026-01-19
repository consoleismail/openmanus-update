"""Trigger models for proactive agent system."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Priority(int, Enum):
    """Trigger priority levels."""
    
    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10


class TriggerType(str, Enum):
    """Types of triggers."""
    
    RULE_BASED = "rule_based"
    ML_PREDICTED = "ml_predicted"
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    THRESHOLD_BASED = "threshold_based"


class Trigger(BaseModel):
    """Represents a trigger that can initiate a workflow."""
    
    id: str
    name: str
    type: TriggerType = TriggerType.RULE_BASED
    priority: Priority = Priority.NORMAL
    workflow_id: str
    
    # Condition that must be met
    condition: str = ""
    
    # Additional data for the workflow
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    # Timing controls
    cooldown_seconds: int = 300  # Minimum time between firings
    last_fired: Optional[datetime] = None
    max_fires_per_day: int = 10
    fires_today: int = 0
    
    # Status
    enabled: bool = True
    
    def can_fire(self) -> bool:
        """Check if the trigger can fire based on cooldown and limits."""
        if not self.enabled:
            return False
        
        if self.fires_today >= self.max_fires_per_day:
            return False
        
        if self.last_fired:
            elapsed = (datetime.now() - self.last_fired).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False
        
        return True
    
    def mark_fired(self) -> None:
        """Mark the trigger as having fired."""
        self.last_fired = datetime.now()
        self.fires_today += 1
    
    def reset_daily_count(self) -> None:
        """Reset the daily fire count."""
        self.fires_today = 0


class TriggerResult(BaseModel):
    """Result of evaluating a trigger."""
    
    trigger: Trigger
    fired: bool
    reason: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)
    context_snapshot: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


class TriggerQueue(BaseModel):
    """Priority queue for pending triggers."""
    
    triggers: List[TriggerResult] = Field(default_factory=list)
    
    def add(self, result: TriggerResult) -> None:
        """Add a trigger result to the queue, maintaining priority order."""
        self.triggers.append(result)
        self.triggers.sort(key=lambda t: t.trigger.priority.value, reverse=True)
    
    def pop(self) -> Optional[TriggerResult]:
        """Remove and return the highest priority trigger."""
        if self.triggers:
            return self.triggers.pop(0)
        return None
    
    def peek(self) -> Optional[TriggerResult]:
        """Return the highest priority trigger without removing it."""
        if self.triggers:
            return self.triggers[0]
        return None
    
    def clear(self) -> None:
        """Clear all pending triggers."""
        self.triggers.clear()
    
    def __len__(self) -> int:
        return len(self.triggers)
    
    def __bool__(self) -> bool:
        return bool(self.triggers)
