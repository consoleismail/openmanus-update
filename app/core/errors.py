# app/core/errors.py
from __future__ import annotations

import os
import sys
import time
import json
import traceback
from dataclasses import dataclass, asdict
from typing import Any, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
except Exception:  # rich not installed
    Console = None  # type: ignore

@dataclass
class ErrorEvent:
    ts: float
    kind: str
    message: str
    exc_type: str
    stack: str
    context: dict[str, Any]

def _format_stack(e: BaseException) -> str:
    return "".join(traceback.format_exception(type(e), e, e.__traceback__))

def _rich_print(event: ErrorEvent) -> None:
    console = Console(stderr=True)
    title = Text(f"{event.kind}: {event.exc_type}", style="bold red")
    body = Text()
    body.append(f"Message: {event.message}\n", style="bold")
    if event.context:
        body.append("\nContext:\n", style="bold")
        body.append(json.dumps(event.context, indent=2, ensure_ascii=False))
        body.append("\n")
    body.append("\nStack:\n", style="bold")
    body.append(event.stack)

    console.print(Panel(body, title=title, border_style="red"))

def _plain_print(event: ErrorEvent) -> None:
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {event.kind} {event.exc_type}: {event.message}\n"
        f"Context: {json.dumps(event.context, ensure_ascii=False)}\n"
        f"Stack:\n{event.stack}",
        file=sys.stderr,
    )

def report_exception(
    e: BaseException,
    *,
    kind: str = "ERROR",
    context: Optional[dict[str, Any]] = None,
) -> ErrorEvent:
    event = ErrorEvent(
        ts=time.time(),
        kind=kind,
        message=str(e),
        exc_type=type(e).__name__,
        stack=_format_stack(e),
        context=context or {},
    )

    # Pretty output for humans
    if Console is not None and os.getenv("NO_RICH") != "1":
        _rich_print(event)
    else:
        _plain_print(event)

    return event
