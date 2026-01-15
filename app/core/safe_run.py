# app/core/safe_run.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from app.core.errors import report_exception

T = TypeVar("T")

@dataclass
class RunResult:
    ok: bool
    value: Any = None
    error: Optional[BaseException] = None

def safe_call(fn: Callable[[], T], *, context: Optional[dict[str, Any]] = None) -> RunResult:
    try:
        return RunResult(ok=True, value=fn())
    except BaseException as e:
        report_exception(e, context=context or {})
        return RunResult(ok=False, error=e)
