from contextvars import ContextVar
from typing import Optional

# Define the global ContextVar to hold the Request ID
# default=None is safer than empty string for logic checks
_request_id_ctx_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """
    Retrieve the current Request ID from the context.

    Usage:
        headers = {"X-Request-ID": get_request_id()}
        requests.get(url, headers=headers)
    """
    return _request_id_ctx_var.get()


def set_request_id(request_id: str):
    """
    Internal use: Set the request ID for the current context.
    Returns a Token that can be used to reset the context.
    """
    return _request_id_ctx_var.set(request_id)


def reset_request_id(token):
    """
    Internal use: Reset the context to its previous state.
    """
    _request_id_ctx_var.reset(token)
