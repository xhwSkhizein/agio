import logging

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agio.utils.logging import get_logger

logger = get_logger(__name__)

# Common retryable exceptions for LLM APIs
# We will catch generic Exception for now or specific ones if we import them from openai
# Ideally we should catch openai.RateLimitError, openai.APIError, openai.Timeout
RETRYABLE_EXCEPTIONS = (Exception,)


def retry_async(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    exceptions: tuple = RETRYABLE_EXCEPTIONS,
):
    """
    Decorator for async functions to add retry logic with exponential backoff.
    """
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
