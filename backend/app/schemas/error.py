"""Structured error response schemas for consistent API error handling."""

from typing import Optional
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Individual error detail within a structured error response."""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response returned by all API endpoints.

    Example JSON::

        {
            "detail": "Product not found",
            "status_code": 404,
            "errors": []
        }
    """
    detail: str
    status_code: int
    errors: list[ErrorDetail] = []
