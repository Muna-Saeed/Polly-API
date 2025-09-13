"""Polly API client helper functions.

This module contains convenience wrappers around the Polly API endpoints so that
Python applications or scripts can interact with the backend easily.

Currently implemented:
    - cast_vote: vote for a specific option in an existing poll.
    - get_poll_results: retrieve aggregated results of a poll.

Example:
    from client import cast_vote

    token = "<JWT_ACCESS_TOKEN>"
    response = cast_vote(poll_id=1, option_id=3, token=token)
    print(response)
"""

from typing import Any, Dict

import requests
import logging

__all__ = [
    "ApiClientError",
    "cast_vote",
    "get_poll_results",
]

logger = logging.getLogger(__name__)  # Module-level logger


class ApiClientError(Exception):
    """Raised when the client receives an unexpected response from the API."""


def _handle_response(response: requests.Response) -> Dict[str, Any]:
    """Validate HTTP response and return JSON body.

    Args:
        response: The Response object returned by ``requests``.

    Returns:
        Parsed JSON content of the response.

    Raises:
        ApiClientError: If the response status code is not in the 200 range or
            if the body cannot be parsed as JSON.
    """

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        # Attempt to extract error message from server, default to HTTPError str
        msg = None
        try:
            msg = response.json().get("detail")  # FastAPI error structure
        except Exception:  # noqa: BLE001
            pass
        raise ApiClientError(msg or str(exc)) from exc

    try:
        return response.json()
    except ValueError as exc:  # responses without JSON body
        raise ApiClientError("Response did not contain valid JSON data") from exc


def cast_vote(*, poll_id: int, option_id: int, token: str, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Cast a vote on a poll.

    Parameters
    ----------
    poll_id : int
        The target poll ID.
    option_id : int
        The selected option's ID.
    token : str
        JWT access token obtained after login.
    base_url : str, optional
        Polly API base URL; default is ``http://localhost:8000``.

    Returns
    -------
    dict
        JSON data representing the recorded vote.

    Raises
    ------
    ValueError
        If any required parameter is missing / falsy.
    ApiClientError
        For HTTP errors with descriptive messages.
    """

    # Client-side validation -------------------------------------------------
    if not poll_id:
        raise ValueError("Parameter 'poll_id' is required and must be a positive integer")
    if not option_id:
        raise ValueError("Parameter 'option_id' is required and must be a positive integer")
    if not token:
        raise ValueError("Parameter 'token' (JWT) is required")

    url = f"{base_url.rstrip('/')}/polls/{poll_id}/vote"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"option_id": option_id}

    response = requests.post(url, json=payload, headers=headers, timeout=10)

    # Specific error-handling -------------------------------------------------
    if response.status_code == 401:
        raise ApiClientError("Unauthorized: invalid or expired token")
    if response.status_code == 404:
        raise ApiClientError("Poll or option not found")

    return _handle_response(response)


def get_poll_results(*, poll_id: int, token: str, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Fetch aggregated vote counts for a poll.

    Parameters
    ----------
    poll_id : int
        Target poll ID.
    token : str
        JWT access token for authorization (required).
    base_url : str, optional
        Polly API base URL; default is ``http://localhost:8000``.

    Returns
    -------
    dict
        Poll results in the shape defined by the ``PollResults`` schema.

    Raises
    ------
    ValueError
        If required parameters are missing / falsy.
    ApiClientError
        For known HTTP errors. Other HTTP errors are propagated via
        :func:`_handle_response`.
    """

    # Client-side validation
    if not poll_id:
        raise ValueError("Parameter 'poll_id' is required and must be a positive integer")
    if not token:
        raise ValueError("Parameter 'token' (JWT) is required")

    url = f"{base_url.rstrip('/')}/polls/{poll_id}/results"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers, timeout=10)

    # Error-aware logging ----------------------------------------------------
    if response.status_code == 401:
        logger.error("Unauthorized while fetching poll results for poll_id=%s", poll_id)
        raise ApiClientError("Unauthorized: invalid or expired token")
    if response.status_code == 404:
        logger.error("Poll not found when fetching results for poll_id=%s", poll_id)
        raise ApiClientError("Poll not found")

    return _handle_response(response)
