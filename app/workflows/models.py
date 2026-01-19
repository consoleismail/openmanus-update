"""Workflow models for autonomous task execution."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    """Status of a workflow step."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(str, Enum):
    """Status of an entire workflow."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_USER_INPUT = "waiting_user_input"


class Step(BaseModel):
    """A single step in a workflow."""
    
    name: str
    action: str  # The action to execute (tool name or function)
    description: str = ""
    
    # Input configuration
    inputs: Dict[str, Any] = Field(default_factory=dict)
    
    # Execution control
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3
    continue_on_failure: bool = False
    requires_user_approval: bool = False
    
    # Conditional execution
    condition: Optional[str] = None  # Expression to evaluate
    skip_if: Optional[str] = None  # Skip step if condition is true
    
    # Status tracking
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def resolve_inputs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve input references using the context.
        
        Supports template syntax like {step_name.field} to reference
        results from previous steps.
        """
        import re
        
        resolved = {}
        
        for key, value in self.inputs.items():
            if isinstance(value, str):
                # Replace template references
                for match in re.finditer(r'\{([^}]+)\}', value):
                    ref = match.group(1)
                    ref_value = self._get_nested_value(context, ref)
                    if ref_value is not None:
                        if value == match.group(0):
                            # Entire value is a reference
                            value = ref_value
                        else:
                            # Partial replacement
                            value = value.replace(match.group(0), str(ref_value))
                resolved[key] = value
            else:
                resolved[key] = value
        
        return resolved
    
    def _get_nested_value(self, obj: Dict, path: str) -> Any:
        """Get a nested value using dot notation."""
        parts = path.split(".")
        current = obj
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        
        return current
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate step duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class Workflow(BaseModel):
    """A complete workflow definition."""
    
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    
    # Steps to execute
    steps: List[Step] = Field(default_factory=list)
    
    # Workflow-level configuration
    timeout_seconds: int = 3600  # 1 hour default
    max_parallel_steps: int = 1  # Sequential by default
    continue_on_step_failure: bool = False
    
    # Trigger configuration (what causes this workflow to run)
    trigger_rule_id: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # Execution tracking
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step_index: int = 0
    
    def get_current_step(self) -> Optional[Step]:
        """Get the current step."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def advance_step(self) -> Optional[Step]:
        """Move to the next step and return it."""
        self.current_step_index += 1
        return self.get_current_step()
    
    def reset(self) -> None:
        """Reset the workflow for re-execution."""
        self.status = WorkflowStatus.PENDING
        self.current_step_index = 0
        for step in self.steps:
            step.status = StepStatus.PENDING
            step.result = None
            step.error = None
            step.started_at = None
            step.completed_at = None
    
    @property
    def completed_steps(self) -> List[Step]:
        """Get list of completed steps."""
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]
    
    @property
    def progress_percentage(self) -> float:
        """Calculate workflow progress as percentage."""
        if not self.steps:
            return 100.0
        return (len(self.completed_steps) / len(self.steps)) * 100


class StepResult(BaseModel):
    """Result of executing a single step."""
    
    step_name: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    """Result of executing an entire workflow."""
    
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    
    # Step results
    step_results: List[StepResult] = Field(default_factory=list)
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Output (final workflow output)
    output: Any = None
    error: Optional[str] = None
    
    # If waiting for user input
    pending_step: Optional[str] = None
    pending_prompt: Optional[str] = None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate total workflow duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def success(self) -> bool:
        """Check if workflow completed successfully."""
        return self.status == WorkflowStatus.COMPLETED
    
    def to_summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"Workflow: {self.workflow_name}",
            f"Status: {self.status.value}",
            f"Steps: {len([r for r in self.step_results if r.status == StepStatus.COMPLETED])}/{len(self.step_results)} completed",
        ]
        
        if self.duration_seconds:
            lines.append(f"Duration: {self.duration_seconds:.2f}s")
        
        if self.error:
            lines.append(f"Error: {self.error}")
        
        return "\n".join(lines)
