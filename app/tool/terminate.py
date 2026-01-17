from app.tool.base import BaseTool


_TERMINATE_DESCRIPTION = """Terminate the interaction when the request is met OR if the assistant cannot proceed further with the task.
When you have finished all the tasks, call this tool to end the work.
As a proactive companion, you must suggest potential next steps or improvements."""


class Terminate(BaseTool):
    name: str = "terminate"
    description: str = _TERMINATE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "The finish status of the interaction.",
                "enum": ["success", "failure"],
            },
            "proactive_suggestions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A list of proactive suggestions for next steps or improvements based on the completed task.",
            },
        },
        "required": ["status", "proactive_suggestions"],
    }

    async def execute(self, status: str, proactive_suggestions: list[str] = None) -> str:
        """Finish the current execution"""
        suggestions_str = ""
        if proactive_suggestions:
            suggestions_str = "\n\nProactive Suggestions for Next Steps:\n" + "\n".join(
                [f"- {s}" for s in proactive_suggestions]
            )
        return f"The interaction has been completed with status: {status}{suggestions_str}"
