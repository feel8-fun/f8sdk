"""Deduplicated, actionable runtime error reporting."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

log = logging.getLogger(__name__)


class ErrorReporter:
    def __init__(self, *, service_id: str, report: Callable[[str, str], None]) -> None:
        self._service_id = service_id
        self._report = report
        self._seen: set[str] = set()

    def report(self, *, key: str, message: str, exc: BaseException | None = None) -> None:
        if key in self._seen:
            return
        self._seen.add(key)
        detail = message if exc is None else f"{message}: {type(exc).__name__}: {exc}"
        self._report(key, detail)
        log.error("service_bus[%s] %s", self._service_id, message, exc_info=exc)


class ErrorReportingHost(Protocol):
    error_reporter: ErrorReporter


def log_error_once(bus: ErrorReportingHost, *, key: str, message: str, exc: BaseException | None = None) -> None:
    bus.error_reporter.report(key=key, message=message, exc=exc)


__all__ = ["ErrorReporter", "ErrorReportingHost", "log_error_once"]
