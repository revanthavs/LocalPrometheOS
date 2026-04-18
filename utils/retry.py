"""Shared retry decorator for external HTTP calls."""
from __future__ import annotations

import logging
from typing import Callable, TypeVar

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        response = getattr(exc, "response", None)
        if response is not None and response.status_code in _RETRYABLE_STATUS_CODES:
            return True
    return False


def _log_retry_attempt(retry_state) -> None:  # type: ignore[no-untyped-def]
    exc = retry_state.outcome.exception()
    logger.warning(
        "Retrying %s (attempt %d): %s",
        retry_state.fn.__name__,
        retry_state.attempt_number,
        exc,
    )


http_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=_log_retry_attempt,
    reraise=True,
)
