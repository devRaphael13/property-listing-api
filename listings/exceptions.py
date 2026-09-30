"""Uniform JSON error envelope for every API error.

Successful list responses look like
``{"count": .., "next": .., "previous": .., "results": [..]}``.

Errors always look like::

    {
      "error": {
        "status": 400,
        "code": "validation_error",
        "message": "Validation failed.",
        "details": {"price": ["A valid number is required."]}
      }
    }
"""

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler

DEFAULT_MESSAGES = {
    400: "Request could not be understood.",
    401: "Authentication credentials were not provided.",
    403: "You do not have permission to perform this action.",
    404: "Not found.",
    405: "Method not allowed.",
    406: "Not acceptable.",
    415: "Unsupported media type.",
    429: "Request was throttled.",
}


def error_payload(code, message, details=None, status_code=status.HTTP_400_BAD_REQUEST):
    payload = {"status": status_code, "code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return {"error": payload}


def _flatten(detail):
    """Turn DRF's nested ErrorDetail structures into plain JSON-ready values."""
    if isinstance(detail, dict):
        return {key: _flatten(value) for key, value in detail.items()}
    if isinstance(detail, list):
        return [_flatten(item) for item in detail]
    return str(detail)


def _message_for(exc, status_code):
    if isinstance(exc, ValidationError):
        detail = exc.detail
        if isinstance(detail, dict):
            return "Validation failed."
        if isinstance(detail, list):
            return str(detail[0]) if detail else "Validation failed."
        return str(detail)
    if isinstance(exc, Http404):
        return "Not found."
    if exc.default_detail:
        return str(exc.default_detail)
    return DEFAULT_MESSAGES.get(status_code, "Request failed.")


def api_exception_handler(exc, context):
    """DRF EXCEPTION_HANDLER that wraps every error in the envelope above."""
    # Anything DRF does not recognise (a genuine bug, a DB error) is re-raised so
    # Django's 500 handler runs instead of leaking a traceback in the payload.
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    status_code = response.status_code
    if isinstance(exc, ValidationError):
        code = "validation_error"
    elif isinstance(exc, Http404):
        code = "not_found"
    else:
        code = getattr(exc, "default_code", "error")

    details = _flatten(exc.detail) if isinstance(exc, APIException) else None
    response.data = error_payload(
        code=code,
        message=_message_for(exc, status_code),
        details=details,
        status_code=status_code,
    )
    return response
