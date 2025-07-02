"""Custom exceptions for the Monzo API library."""

from typing import Any, Dict, Optional


class MonzoAPIError(Exception):
    """Base exception for all Monzo API related errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the exception.

        Args:
            message: Error message
            status_code: HTTP status code (if applicable)
            response_data: Response data from the API (if applicable)
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}


class MonzoAuthenticationError(MonzoAPIError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        response_data: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the authentication error.

        Args:
            message: Error message
            response_data: Response data from the API (if applicable)
        """
        super().__init__(message, status_code=401, response_data=response_data)


class MonzoRateLimitError(MonzoAPIError):
    """Raised when rate limits are exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        response_data: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the rate limit error.

        Args:
            message: Error message
            response_data: Response data from the API (if applicable)
        """
        super().__init__(message, status_code=429, response_data=response_data)


class MonzoValidationError(MonzoAPIError):
    """Raised when request validation fails."""

    def __init__(
        self,
        message: str = "Validation error",
        response_data: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the validation error.

        Args:
            message: Error message
            response_data: Response data from the API (if applicable)
        """
        super().__init__(message, status_code=400, response_data=response_data)
