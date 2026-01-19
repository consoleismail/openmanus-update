"""Pre-defined workflow templates for common proactive scenarios."""

from app.workflows.models import Workflow, Step
from app.triggers.models import Priority


# Travel Advisory Workflow
# Triggered when the user has an upcoming meeting that requires travel

TRAVEL_ADVISORY_WORKFLOW = Workflow(
    id="travel_advisory",
    name="Travel Advisory",
    description="Proactively notify user about travel requirements for upcoming meetings",
    version="1.0.0",
    trigger_rule_id="travel_advisory",
    tags=["travel", "meetings", "notifications"],
    steps=[
        Step(
            name="get_traffic_info",
            action="maps.get_traffic",
            description="Get current traffic conditions to the destination",
            inputs={
                "destination": "{inputs.event_location}",
            },
            timeout_seconds=30,
        ),
        Step(
            name="calculate_departure",
            action="calculate_optimal_departure",
            description="Calculate the optimal departure time",
            inputs={
                "travel_time": "{get_traffic_info.estimated_minutes}",
                "meeting_time": "{inputs.event_time}",
                "buffer_minutes": 10,
            },
        ),
        Step(
            name="send_notification",
            action="notification.send",
            description="Send travel advisory notification to the user",
            inputs={
                "title": "Time to leave for {inputs.event_title}",
                "body": "Leave by {calculate_departure.departure_time} to arrive on time. Expected travel: {get_traffic_info.estimated_minutes} minutes via {get_traffic_info.route}.",
                "urgency": "high",
            },
        ),
    ],
)


# Meeting Preparation Workflow
# Triggered before important meetings to help the user prepare

MEETING_PREP_WORKFLOW = Workflow(
    id="meeting_prep",
    name="Meeting Preparation",
    description="Help user prepare for upcoming important meetings",
    version="1.0.0",
    trigger_rule_id="meeting_prep",
    tags=["meetings", "preparation"],
    steps=[
        Step(
            name="get_meeting_details",
            action="calendar.get_event_details",
            description="Get full meeting details including attendees and agenda",
            inputs={
                "event_id": "{inputs.event_id}",
            },
        ),
        Step(
            name="get_attendee_info",
            action="contacts.get_info",
            description="Get information about meeting attendees",
            inputs={
                "attendees": "{get_meeting_details.attendees}",
            },
            continue_on_failure=True,
        ),
        Step(
            name="search_related_docs",
            action="search.documents",
            description="Find documents related to the meeting topic",
            inputs={
                "query": "{get_meeting_details.title} {get_meeting_details.description}",
                "limit": 5,
            },
            continue_on_failure=True,
        ),
        Step(
            name="prepare_summary",
            action="llm.summarize",
            description="Prepare a meeting prep summary",
            inputs={
                "meeting": "{get_meeting_details}",
                "attendees": "{get_attendee_info}",
                "documents": "{search_related_docs}",
            },
        ),
        Step(
            name="send_notification",
            action="notification.send",
            description="Send meeting preparation summary",
            inputs={
                "title": "Prep for: {inputs.event_title}",
                "body": "{prepare_summary.summary}",
                "urgency": "normal",
            },
        ),
    ],
)


# Deadline Reminder Workflow
# Triggered when there are high-priority tasks with approaching deadlines

DEADLINE_REMINDER_WORKFLOW = Workflow(
    id="deadline_reminder",
    name="Deadline Reminder",
    description="Remind user about approaching task deadlines",
    version="1.0.0",
    trigger_rule_id="deadline_reminder",
    tags=["tasks", "deadlines", "reminders"],
    steps=[
        Step(
            name="get_urgent_tasks",
            action="tasks.get_urgent",
            description="Get tasks with approaching deadlines",
            inputs={
                "hours_ahead": 24,
                "min_priority": 7,
            },
        ),
        Step(
            name="prioritize_tasks",
            action="llm.prioritize",
            description="Analyze and prioritize the urgent tasks",
            inputs={
                "tasks": "{get_urgent_tasks.tasks}",
            },
        ),
        Step(
            name="send_notification",
            action="notification.send",
            description="Send deadline reminder",
            inputs={
                "title": "Deadline Alert: {prioritize_tasks.top_task.title}",
                "body": "You have {get_urgent_tasks.count} tasks due in the next 24 hours. Focus on: {prioritize_tasks.recommendation}",
                "urgency": "high",
            },
        ),
    ],
)


# Daily Briefing Workflow
# Triggered each morning to provide a daily overview

DAILY_BRIEFING_WORKFLOW = Workflow(
    id="daily_briefing",
    name="Daily Briefing",
    description="Provide a daily overview of schedule and priorities",
    version="1.0.0",
    tags=["daily", "briefing", "overview"],
    steps=[
        Step(
            name="get_calendar",
            action="calendar.get_today",
            description="Get today's calendar events",
        ),
        Step(
            name="get_tasks",
            action="tasks.get_today",
            description="Get today's tasks and priorities",
        ),
        Step(
            name="check_weather",
            action="weather.get_forecast",
            description="Get today's weather forecast",
            continue_on_failure=True,
        ),
        Step(
            name="generate_briefing",
            action="llm.generate_briefing",
            description="Generate the daily briefing",
            inputs={
                "calendar": "{get_calendar}",
                "tasks": "{get_tasks}",
                "weather": "{check_weather}",
            },
        ),
        Step(
            name="send_notification",
            action="notification.send",
            description="Send daily briefing",
            inputs={
                "title": "Good morning! Here's your day",
                "body": "{generate_briefing.content}",
                "urgency": "normal",
            },
        ),
    ],
)


# Focus Time Workflow
# Suggest focus time when calendar has gaps and user has deep work tasks

FOCUS_TIME_WORKFLOW = Workflow(
    id="focus_time",
    name="Focus Time Suggestion",
    description="Suggest focus time blocks when calendar allows",
    version="1.0.0",
    tags=["focus", "productivity"],
    steps=[
        Step(
            name="find_gaps",
            action="calendar.find_free_slots",
            description="Find available time slots in the calendar",
            inputs={
                "min_duration_minutes": 60,
                "hours_ahead": 8,
            },
        ),
        Step(
            name="get_deep_work",
            action="tasks.get_deep_work",
            description="Get tasks that require focused attention",
        ),
        Step(
            name="match_tasks_to_slots",
            action="llm.match_tasks",
            description="Match tasks to available time slots",
            inputs={
                "slots": "{find_gaps.slots}",
                "tasks": "{get_deep_work.tasks}",
            },
        ),
        Step(
            name="send_suggestion",
            action="notification.send",
            description="Send focus time suggestion",
            inputs={
                "title": "Focus Time Available",
                "body": "You have a {match_tasks_to_slots.slot_duration}min focus block at {match_tasks_to_slots.slot_time}. Suggested task: {match_tasks_to_slots.suggested_task}",
                "urgency": "low",
            },
            condition="match_tasks_to_slots.has_match",
        ),
    ],
)


# All available workflow templates
WORKFLOW_TEMPLATES = {
    "travel_advisory": TRAVEL_ADVISORY_WORKFLOW,
    "meeting_prep": MEETING_PREP_WORKFLOW,
    "deadline_reminder": DEADLINE_REMINDER_WORKFLOW,
    "daily_briefing": DAILY_BRIEFING_WORKFLOW,
    "focus_time": FOCUS_TIME_WORKFLOW,
}


def get_workflow_template(template_id: str) -> Workflow:
    """Get a workflow template by ID."""
    if template_id not in WORKFLOW_TEMPLATES:
        raise ValueError(f"Unknown workflow template: {template_id}")
    
    # Return a copy to avoid modifying the template
    template = WORKFLOW_TEMPLATES[template_id]
    return Workflow(**template.dict())


def list_workflow_templates() -> list:
    """List all available workflow templates."""
    return [
        {
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "tags": w.tags,
        }
        for w in WORKFLOW_TEMPLATES.values()
    ]
