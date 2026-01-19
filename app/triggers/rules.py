"""Rules-based trigger engine for proactive agents."""

import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from app.context.models import UserContext, UserState
from app.triggers.models import Trigger, TriggerResult, TriggerType, Priority
from app.logger import logger


class RuleCondition(BaseModel):
    """A single condition in a rule."""
    
    field: str  # Dot-notation path to context field
    operator: str  # eq, ne, gt, lt, gte, lte, contains, in, within_minutes
    value: Any
    
    def evaluate(self, context: UserContext) -> bool:
        """Evaluate this condition against the context."""
        try:
            actual_value = self._get_field_value(context, self.field)
            return self._compare(actual_value, self.operator, self.value)
        except Exception as e:
            logger.debug(f"Error evaluating condition {self.field}: {e}")
            return False
    
    def _get_field_value(self, obj: Any, path: str) -> Any:
        """Get a nested field value using dot notation."""
        parts = path.split(".")
        current = obj
        
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                raise ValueError(f"Cannot find {part} in {type(current)}")
        
        return current
    
    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compare values using the specified operator."""
        if operator == "eq":
            return actual == expected
        elif operator == "ne":
            return actual != expected
        elif operator == "gt":
            return actual > expected
        elif operator == "lt":
            return actual < expected
        elif operator == "gte":
            return actual >= expected
        elif operator == "lte":
            return actual <= expected
        elif operator == "contains":
            return expected in actual
        elif operator == "in":
            return actual in expected
        elif operator == "within_minutes":
            # Check if a datetime is within X minutes from now
            if isinstance(actual, datetime):
                diff = (actual - datetime.now()).total_seconds() / 60
                return 0 <= diff <= expected
            return False
        elif operator == "is_true":
            return bool(actual)
        elif operator == "is_false":
            return not bool(actual)
        elif operator == "exists":
            return actual is not None
        elif operator == "matches":
            return bool(re.match(expected, str(actual)))
        else:
            raise ValueError(f"Unknown operator: {operator}")


class Rule(BaseModel):
    """A rule that can trigger a workflow."""
    
    id: str
    name: str
    description: str = ""
    
    # Conditions (all must be true for rule to fire)
    conditions: List[RuleCondition] = Field(default_factory=list)
    
    # Any-of conditions (at least one must be true)
    any_conditions: List[RuleCondition] = Field(default_factory=list)
    
    # Associated workflow and trigger settings
    workflow_id: str
    priority: Priority = Priority.NORMAL
    cooldown_seconds: int = 300
    max_fires_per_day: int = 10
    
    # Payload template (values can reference context fields)
    payload_template: Dict[str, str] = Field(default_factory=dict)
    
    enabled: bool = True
    
    def evaluate(self, context: UserContext) -> bool:
        """
        Evaluate all conditions against the context.
        
        Returns True if:
        - All conditions are True AND
        - At least one any_condition is True (if any_conditions is not empty)
        """
        if not self.enabled:
            return False
        
        # All conditions must be true
        for condition in self.conditions:
            if not condition.evaluate(context):
                return False
        
        # At least one any_condition must be true (if specified)
        if self.any_conditions:
            any_true = any(c.evaluate(context) for c in self.any_conditions)
            if not any_true:
                return False
        
        return True
    
    def build_payload(self, context: UserContext) -> Dict[str, Any]:
        """Build the trigger payload from the template and context."""
        payload = {}
        
        for key, template in self.payload_template.items():
            try:
                # Simple template substitution using {field.path} syntax
                value = template
                for match in re.finditer(r'\{([^}]+)\}', template):
                    field_path = match.group(1)
                    field_value = self._get_context_value(context, field_path)
                    value = value.replace(match.group(0), str(field_value))
                payload[key] = value
            except Exception as e:
                logger.warning(f"Error building payload for {key}: {e}")
                payload[key] = template
        
        return payload
    
    def _get_context_value(self, context: UserContext, path: str) -> Any:
        """Get a value from context using dot notation."""
        parts = path.split(".")
        current = context
        
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current


class RulesEngine:
    """Engine for evaluating rules against user context."""
    
    def __init__(self):
        """Initialize the rules engine."""
        self.rules: Dict[str, Rule] = {}
        self._trigger_states: Dict[str, Dict] = {}  # Track trigger firing state
    
    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self.rules[rule.id] = rule
        self._trigger_states[rule.id] = {
            "last_fired": None,
            "fires_today": 0,
            "last_reset": datetime.now().date()
        }
        logger.debug(f"Added rule: {rule.name} ({rule.id})")
    
    def remove_rule(self, rule_id: str) -> None:
        """Remove a rule from the engine."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            del self._trigger_states[rule_id]
    
    def evaluate(self, context: UserContext) -> List[TriggerResult]:
        """
        Evaluate all rules against the current context.
        
        Args:
            context: Current user context
            
        Returns:
            List of TriggerResults for rules that fired
        """
        self._reset_daily_counts_if_needed()
        
        results = []
        
        for rule_id, rule in self.rules.items():
            if not self._can_fire(rule_id, rule):
                continue
            
            if rule.evaluate(context):
                # Create trigger from rule
                trigger = Trigger(
                    id=f"trigger_{rule_id}_{datetime.now().timestamp()}",
                    name=rule.name,
                    type=TriggerType.RULE_BASED,
                    priority=rule.priority,
                    workflow_id=rule.workflow_id,
                    condition=str([c.dict() for c in rule.conditions]),
                    payload=rule.build_payload(context),
                    cooldown_seconds=rule.cooldown_seconds,
                    max_fires_per_day=rule.max_fires_per_day
                )
                
                result = TriggerResult(
                    trigger=trigger,
                    fired=True,
                    reason=f"Rule '{rule.name}' conditions met",
                    confidence=1.0,
                    context_snapshot={"state": context.state.value}
                )
                
                self._mark_fired(rule_id)
                results.append(result)
                logger.info(f"Rule fired: {rule.name}")
        
        return results
    
    def _can_fire(self, rule_id: str, rule: Rule) -> bool:
        """Check if a rule can fire based on cooldown and limits."""
        state = self._trigger_states.get(rule_id, {})
        
        # Check daily limit
        if state.get("fires_today", 0) >= rule.max_fires_per_day:
            return False
        
        # Check cooldown
        last_fired = state.get("last_fired")
        if last_fired:
            elapsed = (datetime.now() - last_fired).total_seconds()
            if elapsed < rule.cooldown_seconds:
                return False
        
        return True
    
    def _mark_fired(self, rule_id: str) -> None:
        """Mark a rule as having fired."""
        if rule_id in self._trigger_states:
            self._trigger_states[rule_id]["last_fired"] = datetime.now()
            self._trigger_states[rule_id]["fires_today"] += 1
    
    def _reset_daily_counts_if_needed(self) -> None:
        """Reset daily fire counts at midnight."""
        today = datetime.now().date()
        
        for rule_id, state in self._trigger_states.items():
            if state.get("last_reset") != today:
                state["fires_today"] = 0
                state["last_reset"] = today


# Pre-defined rules for common scenarios

TRAVEL_ADVISORY_RULE = Rule(
    id="travel_advisory",
    name="Travel Advisory",
    description="Notify user about upcoming meetings that require travel",
    conditions=[
        RuleCondition(
            field="upcoming_events.0.requires_travel",
            operator="is_true",
            value=True
        ),
        RuleCondition(
            field="upcoming_events.0.start_time",
            operator="within_minutes",
            value=60
        ),
    ],
    workflow_id="travel_advisory",
    priority=Priority.HIGH,
    cooldown_seconds=1800,  # 30 minutes
    payload_template={
        "event_title": "{upcoming_events.0.title}",
        "event_location": "{upcoming_events.0.location}",
        "event_time": "{upcoming_events.0.start_time}",
    }
)

MEETING_PREP_RULE = Rule(
    id="meeting_prep",
    name="Meeting Preparation",
    description="Suggest preparation for upcoming important meetings",
    conditions=[
        RuleCondition(
            field="upcoming_events.0.start_time",
            operator="within_minutes",
            value=30
        ),
    ],
    any_conditions=[
        RuleCondition(
            field="upcoming_events.0.title",
            operator="contains",
            value="review"
        ),
        RuleCondition(
            field="upcoming_events.0.title",
            operator="contains",
            value="presentation"
        ),
        RuleCondition(
            field="upcoming_events.0.title",
            operator="contains",
            value="interview"
        ),
    ],
    workflow_id="meeting_prep",
    priority=Priority.NORMAL,
    cooldown_seconds=3600,
    payload_template={
        "event_title": "{upcoming_events.0.title}",
    }
)

DEADLINE_REMINDER_RULE = Rule(
    id="deadline_reminder",
    name="Deadline Reminder",
    description="Remind user about approaching task deadlines",
    conditions=[
        RuleCondition(
            field="task_context.high_priority_count",
            operator="gt",
            value=0
        ),
        RuleCondition(
            field="state",
            operator="ne",
            value=UserState.IN_MEETING
        ),
    ],
    workflow_id="deadline_reminder",
    priority=Priority.HIGH,
    cooldown_seconds=7200,  # 2 hours
    payload_template={}
)
