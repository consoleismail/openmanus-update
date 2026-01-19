# Workflow templates init
from app.workflows.templates.proactive import (
    TRAVEL_ADVISORY_WORKFLOW,
    MEETING_PREP_WORKFLOW,
    DEADLINE_REMINDER_WORKFLOW,
    DAILY_BRIEFING_WORKFLOW,
    FOCUS_TIME_WORKFLOW,
    WORKFLOW_TEMPLATES,
    get_workflow_template,
    list_workflow_templates,
)

__all__ = [
    "TRAVEL_ADVISORY_WORKFLOW",
    "MEETING_PREP_WORKFLOW",
    "DEADLINE_REMINDER_WORKFLOW",
    "DAILY_BRIEFING_WORKFLOW",
    "FOCUS_TIME_WORKFLOW",
    "WORKFLOW_TEMPLATES",
    "get_workflow_template",
    "list_workflow_templates",
]
