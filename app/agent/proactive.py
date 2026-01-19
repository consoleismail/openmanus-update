"""Proactive Agent - Extended WorkCo with autonomous capabilities."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.agent.manus import WorkCo
from app.context.engine import ContextEngine
from app.context.models import UserContext
from app.triggers.engine import TriggerEngine
from app.triggers.rules import (
    RulesEngine,
    TRAVEL_ADVISORY_RULE,
    MEETING_PREP_RULE,
    DEADLINE_REMINDER_RULE,
)
from app.workflows.engine import WorkflowExecutor, ActionRegistry, register_builtin_actions
from app.workflows.templates.proactive import WORKFLOW_TEMPLATES
from app.logger import logger


class ProactiveWorkCo(WorkCo):
    """
    A proactive AI companion that anticipates user needs.
    
    Extends WorkCo with:
    - Context awareness (calendar, email, location)
    - Trigger-based proactive suggestions
    - Autonomous workflow execution
    - Notification system for user alerts
    
    The agent monitors user context and proactively suggests
    actions, prepares for meetings, and helps manage tasks.
    """
    
    name: str = "ProactiveWorkCo"
    description: str = """A proactive AI companion that anticipates your needs,
    monitors your context, and suggests actions before you ask."""
    
    # Proactive components
    context_engine: Optional[ContextEngine] = None
    trigger_engine: Optional[TriggerEngine] = None
    workflow_executor: Optional[WorkflowExecutor] = None
    
    # Configuration
    proactive_enabled: bool = True
    context_poll_interval: int = 60  # seconds
    
    # State tracking
    _proactive_loop_running: bool = False
    _proactive_task: Optional[asyncio.Task] = None
    _last_context: Optional[UserContext] = None
    _notification_queue: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
    
    async def initialize_proactive(self) -> None:
        """Initialize proactive components."""
        if self.context_engine is None:
            self.context_engine = ContextEngine()
        
        if self.trigger_engine is None:
            self.trigger_engine = TriggerEngine()
            
            # Register default rules
            self.trigger_engine.add_rule(TRAVEL_ADVISORY_RULE)
            self.trigger_engine.add_rule(MEETING_PREP_RULE)
            self.trigger_engine.add_rule(DEADLINE_REMINDER_RULE)
        
        if self.workflow_executor is None:
            action_registry = ActionRegistry()
            register_builtin_actions(action_registry)
            self.workflow_executor = WorkflowExecutor(action_registry)
        
        logger.info("ProactiveWorkCo initialized")
    
    async def start_proactive_loop(self) -> None:
        """Start the proactive monitoring loop."""
        if self._proactive_loop_running:
            logger.warning("Proactive loop already running")
            return
        
        await self.initialize_proactive()
        
        self._proactive_loop_running = True
        self._proactive_task = asyncio.create_task(self._proactive_loop())
        
        logger.info("Proactive monitoring started")
    
    async def stop_proactive_loop(self) -> None:
        """Stop the proactive monitoring loop."""
        self._proactive_loop_running = False
        
        if self._proactive_task:
            self._proactive_task.cancel()
            try:
                await self._proactive_task
            except asyncio.CancelledError:
                pass
            self._proactive_task = None
        
        logger.info("Proactive monitoring stopped")
    
    async def _proactive_loop(self) -> None:
        """Main proactive monitoring loop."""
        while self._proactive_loop_running:
            try:
                # Get current context
                context = await self.context_engine.get_current_context()
                self._last_context = context
                
                # Evaluate triggers
                triggered = await self.trigger_engine.evaluate(context)
                
                # Execute triggered workflows
                for trigger_result in triggered:
                    await self._handle_trigger(trigger_result, context)
                
            except Exception as e:
                logger.error(f"Error in proactive loop: {e}")
            
            await asyncio.sleep(self.context_poll_interval)
    
    async def _handle_trigger(self, trigger_result: Any, context: UserContext) -> None:
        """Handle a fired trigger by executing its workflow."""
        trigger = trigger_result.trigger
        
        logger.info(f"Trigger fired: {trigger.name}")
        
        # Get workflow for this trigger
        if trigger.workflow_id in WORKFLOW_TEMPLATES:
            workflow = WORKFLOW_TEMPLATES[trigger.workflow_id]
            
            # Execute workflow
            result = await self.workflow_executor.execute(
                workflow=workflow,
                context=context,
                initial_inputs=trigger.payload
            )
            
            # Handle workflow result
            if result.success:
                logger.info(f"Workflow completed: {workflow.name}")
            else:
                logger.warning(f"Workflow failed: {workflow.name} - {result.error}")
        else:
            # Queue notification for user
            await self._queue_notification(
                title=f"Suggestion: {trigger.name}",
                body=f"Based on your current context, you might want to: {trigger.name}",
                urgency="normal",
                metadata=trigger.payload
            )
    
    async def _queue_notification(
        self,
        title: str,
        body: str,
        urgency: str = "normal",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Queue a notification for the user."""
        notification = {
            "title": title,
            "body": body,
            "urgency": urgency,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self._notification_queue.append(notification)
        logger.info(f"Notification queued: {title}")
    
    async def get_pending_notifications(self) -> List[Dict[str, Any]]:
        """Get and clear pending notifications."""
        notifications = self._notification_queue.copy()
        self._notification_queue.clear()
        return notifications
    
    async def get_current_context(self) -> Optional[UserContext]:
        """Get the current user context."""
        if self._last_context:
            return self._last_context
        
        if self.context_engine:
            return await self.context_engine.get_current_context()
        
        return None
    
    async def get_proactive_suggestions(self) -> List[Dict[str, Any]]:
        """Get proactive suggestions based on current context."""
        suggestions = []
        
        context = await self.get_current_context()
        if not context:
            return suggestions
        
        # Check for upcoming events requiring attention
        if context.upcoming_events:
            next_event = context.upcoming_events[0]
            if next_event.starts_within(60):
                suggestions.append({
                    "type": "upcoming_event",
                    "title": f"Upcoming: {next_event.title}",
                    "description": f"Starts at {next_event.start_time.strftime('%H:%M')}",
                    "urgency": "high" if next_event.starts_within(15) else "normal"
                })
                
                if next_event.requires_travel:
                    suggestions.append({
                        "type": "travel_required",
                        "title": f"Travel needed for {next_event.title}",
                        "description": f"Location: {next_event.location}",
                        "urgency": "high"
                    })
        
        # Check for overdue tasks
        if context.task_context.overdue_count > 0:
            suggestions.append({
                "type": "overdue_tasks",
                "title": f"{context.task_context.overdue_count} overdue task(s)",
                "description": "Consider prioritizing these tasks",
                "urgency": "high"
            })
        
        # Check for high priority tasks
        if context.task_context.high_priority_count > 0:
            suggestions.append({
                "type": "priority_tasks",
                "title": f"{context.task_context.high_priority_count} high-priority task(s)",
                "description": "Focus time recommended",
                "urgency": "normal"
            })
        
        return suggestions
    
    async def think(self) -> bool:
        """
        Process current state with proactive awareness.
        
        Overrides WorkCo.think() to include proactive context.
        """
        # Check for pending notifications
        notifications = await self.get_pending_notifications()
        if notifications:
            # Add notifications to context
            notification_summary = "\n".join([
                f"- {n['title']}: {n['body']}"
                for n in notifications
            ])
            
            self.update_memory(
                "system",
                f"Proactive notifications:\n{notification_summary}"
            )
        
        # Get proactive suggestions
        suggestions = await self.get_proactive_suggestions()
        if suggestions:
            suggestion_summary = "\n".join([
                f"- [{s['urgency']}] {s['title']}: {s['description']}"
                for s in suggestions
            ])
            
            # Include in next step prompt
            original_prompt = self.next_step_prompt
            self.next_step_prompt = f"""Context Suggestions:
{suggestion_summary}

{original_prompt}"""
        
        # Call parent think
        result = await super().think()
        
        # Restore original prompt
        if suggestions:
            self.next_step_prompt = original_prompt
        
        return result
    
    async def cleanup(self) -> None:
        """Clean up proactive agent resources."""
        await self.stop_proactive_loop()
        await super().cleanup()


# Factory function
async def create_proactive_agent(**kwargs) -> ProactiveWorkCo:
    """
    Create and initialize a ProactiveWorkCo agent.
    
    Args:
        **kwargs: Arguments to pass to ProactiveWorkCo
        
    Returns:
        Initialized ProactiveWorkCo instance
    """
    agent = ProactiveWorkCo(**kwargs)
    await agent.initialize_proactive()
    
    # Optionally start proactive loop
    if agent.proactive_enabled:
        await agent.start_proactive_loop()
    
    return agent
