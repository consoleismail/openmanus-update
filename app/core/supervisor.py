# app/core/supervisor.py
from __future__ import annotations

import time
from typing import Callable, Optional

from app.core.errors import report_exception
from app.core.safe_run import safe_call

def supervise(
    work: Callable[[], None],
    *,
    name: str = "main",
    restart_delay_sec: float = 1.0,
    max_restarts: Optional[int] = None,
) -> None:
    restarts = 0
    while True:
        res = safe_call(work, context={"supervisor": name, "restart": restarts})
        if res.ok:
            # Work finished normally; typically you exit.
            return

        restarts += 1
        if max_restarts is not None and restarts > max_restarts:
            report_exception(
                RuntimeError("Max restarts exceeded"),
                kind="FATAL",
                context={"supervisor": name, "restarts": restarts},
            )
            return

        time.sleep(restart_delay_sec)
