"""Workflow execution engine for autonomous task execution."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.context.models import UserContext
from app.workflows.models import (
    Workflow,
    Step,
    StepStatus,
    WorkflowStatus,
    StepResult,
    WorkflowResult,
)
from app.logger import logger


class ActionRegistry:
    """Registry of available actions that workflows can execute."""
    
    def __init__(self):
        self._actions: Dict[str, Callable] = {}
    
    def register(self, name: str, action: Callable) -> None:
        """Register an action."""
        self._actions[name] = action
        logger.debug(f"Registered action: {name}")
    
    def get(self, name: str) -> Optional[Callable]:
        """Get an action by name."""
        return self._actions.get(name)
    
    def list_actions(self) -> List[str]:
        """List all registered action names."""
        return list(self._actions.keys())
    
    def has(self, name: str) -> bool:
        """Check if an action is registered."""
        return name in self._actions


class WorkflowExecutor:
    """
    Executes multi-step autonomous workflows.
    
    The executor manages:
    - Step-by-step execution
    - Input resolution from previous step results
    - Error handling and retries
    - User approval gates
    - Parallel step execution (when configured)
    """
    
    def __init__(self, action_registry: Optional[ActionRegistry] = None):
        """
        Initialize the workflow executor.
        
        Args:
            action_registry: Registry of available actions
        """
        self.action_registry = action_registry or ActionRegistry()
        self._running_workflows: Dict[str, Workflow] = {}
        self._notification_callback: Optional[Callable] = None
    
    def set_notification_callback(self, callback: Callable) -> None:
        """Set callback for sending notifications to the user."""
        self._notification_callback = callback
    
    async def execute(
        self,
        workflow: Workflow,
        context: UserContext,
        initial_inputs: Optional[Dict[str, Any]] = None
    ) -> WorkflowResult:
        """
        Execute a workflow.
        
        Args:
            workflow: The workflow to execute
            context: Current user context
            initial_inputs: Initial inputs to make available to steps
            
        Returns:
            WorkflowResult with execution details
        """
        workflow_id = workflow.id
        self._running_workflows[workflow_id] = workflow
        
        # Initialize result
        result = WorkflowResult(
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(),
        )
        
        # Build execution context from initial inputs and context
        exec_context = {
            "user_context": context,
            "inputs": initial_inputs or {},
            "step_results": {},
        }
        
        workflow.status = WorkflowStatus.RUNNING
        logger.info(f"Starting workflow: {workflow.name} ({workflow_id})")
        
        try:
            # Execute each step
            for step in workflow.steps:
                step_result = await self._execute_step(step, exec_context, workflow)
                result.step_results.append(step_result)
                
                # Store step result for use by subsequent steps
                exec_context["step_results"][step.name] = step_result.output
                
                # Check if step requires user input
                if step_result.status == StepStatus.PENDING and step.requires_user_approval:
                    result.status = WorkflowStatus.WAITING_USER_INPUT
                    result.pending_step = step.name
                    result.pending_prompt = f"Approval required for step: {step.name}"
                    return result
                
                # Handle step failure
                if step_result.status == StepStatus.FAILED:
                    if not step.continue_on_failure and not workflow.continue_on_step_failure:
                        result.status = WorkflowStatus.FAILED
                        result.error = f"Step '{step.name}' failed: {step_result.error}"
                        break
            
            # All steps completed
            if result.status != WorkflowStatus.FAILED:
                result.status = WorkflowStatus.COMPLETED
                
                # Use last step's output as workflow output
                if result.step_results:
                    result.output = result.step_results[-1].output
                    
        except asyncio.CancelledError:
            result.status = WorkflowStatus.CANCELLED
            logger.info(f"Workflow cancelled: {workflow.name}")
        except Exception as e:
            result.status = WorkflowStatus.FAILED
            result.error = str(e)
            logger.error(f"Workflow error: {e}")
        finally:
            result.completed_at = datetime.now()
            workflow.status = result.status
            del self._running_workflows[workflow_id]
        
        logger.info(f"Workflow completed: {workflow.name} - {result.status.value}")
        return result
    
    async def _execute_step(
        self,
        step: Step,
        context: Dict[str, Any],
        workflow: Workflow
    ) -> StepResult:
        """
        Execute a single workflow step.
        
        Args:
            step: The step to execute
            context: Execution context with previous results
            workflow: The parent workflow
            
        Returns:
            StepResult with execution details
        """
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now()
        
        logger.debug(f"Executing step: {step.name} (action: {step.action})")
        
        try:
            # Check skip condition
            if step.skip_if and self._evaluate_condition(step.skip_if, context):
                step.status = StepStatus.SKIPPED
                step.completed_at = datetime.now()
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                    output=None,
                    duration_seconds=step.duration_seconds or 0,
                )
            
            # Check execution condition
            if step.condition and not self._evaluate_condition(step.condition, context):
                step.status = StepStatus.SKIPPED
                step.completed_at = datetime.now()
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                    output=None,
                    metadata={"reason": "Condition not met"},
                    duration_seconds=step.duration_seconds or 0,
                )
            
            # Check for user approval
            if step.requires_user_approval:
                # This would typically wait for user input
                # For now, we return pending status
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.PENDING,
                    metadata={"requires_approval": True},
                )
            
            # Resolve inputs
            resolved_inputs = step.resolve_inputs(context)
            
            # Get and execute action
            action = self.action_registry.get(step.action)
            
            if not action:
                raise ValueError(f"Unknown action: {step.action}")
            
            # Execute with timeout and retries
            output = await self._execute_with_retry(
                action,
                resolved_inputs,
                step.timeout_seconds,
                step.max_retries
            )
            
            step.status = StepStatus.COMPLETED
            step.result = output
            step.completed_at = datetime.now()
            
            return StepResult(
                step_name=step.name,
                status=StepStatus.COMPLETED,
                output=output,
                duration_seconds=step.duration_seconds or 0,
            )
            
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.completed_at = datetime.now()
            
            logger.error(f"Step '{step.name}' failed: {e}")
            
            return StepResult(
                step_name=step.name,
                status=StepStatus.FAILED,
                error=str(e),
                duration_seconds=step.duration_seconds or 0,
            )
    
    async def _execute_with_retry(
        self,
        action: Callable,
        inputs: Dict[str, Any],
        timeout: int,
        max_retries: int
    ) -> Any:
        """Execute an action with timeout and retries."""
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(action):
                    result = await asyncio.wait_for(
                        action(**inputs),
                        timeout=timeout
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(action, **inputs),
                        timeout=timeout
                    )
                return result
                
            except asyncio.TimeoutError:
                last_error = f"Step timed out after {timeout}s"
                logger.warning(f"Step timeout (attempt {attempt + 1}/{max_retries + 1})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Step error (attempt {attempt + 1}/{max_retries + 1}): {e}")
            
            if attempt < max_retries:
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
        
        raise RuntimeError(last_error)
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition expression.
        
        Simple expression evaluation supporting basic comparisons.
        """
        try:
            # Very basic condition evaluation
            # In production, use a proper expression parser
            
            # Handle simple existence checks
            if condition in context.get("step_results", {}):
                return bool(context["step_results"][condition])
            
            # Handle boolean context values
            parts = condition.split(".")
            current = context
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                elif hasattr(current, part):
                    current = getattr(current, part)
                else:
                    return False
            
            return bool(current)
            
        except Exception as e:
            logger.warning(f"Error evaluating condition '{condition}': {e}")
            return False
    
    async def cancel(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        if workflow_id in self._running_workflows:
            workflow = self._running_workflows[workflow_id]
            workflow.status = WorkflowStatus.CANCELLED
            return True
        return False
    
    def get_running_workflows(self) -> List[str]:
        """Get list of running workflow IDs."""
        return list(self._running_workflows.keys())
    
    async def send_notification(
        self,
        title: str,
        body: str,
        urgency: str = "normal"
    ) -> bool:
        """Send a notification to the user."""
        if self._notification_callback:
            try:
                await self._notification_callback(title=title, body=body, urgency=urgency)
                return True
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
        return False


# Register built-in actions
def register_builtin_actions(registry: ActionRegistry) -> None:
    """Register built-in actions for workflows."""
    
    async def log_message(message: str) -> str:
        """Log a message."""
        logger.info(f"[Workflow] {message}")
        return message
    
    async def send_notification(title: str, body: str, urgency: str = "normal") -> dict:
        """Send a notification (placeholder)."""
        logger.info(f"[Notification] {title}: {body}")
        return {"sent": True, "title": title, "body": body}
    
    async def wait_seconds(seconds: int) -> bool:
        """Wait for specified seconds."""
        await asyncio.sleep(seconds)
        return True
    
    async def calculate_optimal_departure(
        travel_time: int,
        meeting_time: str,
        buffer_minutes: int = 10
    ) -> dict:
        """Calculate optimal departure time."""
        from datetime import datetime, timedelta
        
        # Parse meeting time
        if isinstance(meeting_time, datetime):
            meeting_dt = meeting_time
        else:
            meeting_dt = datetime.fromisoformat(meeting_time.replace("Z", "+00:00"))
        
        # Calculate departure time
        departure_dt = meeting_dt - timedelta(minutes=travel_time + buffer_minutes)
        
        return {
            "departure_time": departure_dt.isoformat(),
            "meeting_time": meeting_dt.isoformat(),
            "total_lead_time_minutes": travel_time + buffer_minutes,
        }
    
    # Register actions
    registry.register("log", log_message)
    registry.register("notification.send", send_notification)
    registry.register("wait", wait_seconds)
    registry.register("calculate_optimal_departure", calculate_optimal_departure)
