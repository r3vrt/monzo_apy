"""Authentication storage abstractions for Monzo."""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel


class MonzoCredentials(BaseModel):
    """Encapsulates Monzo OAuth2 credentials."""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert credentials to a dictionary."""
        return self.model_dump()


class AuthStorage(ABC):
    """Abstract base class for Monzo authentication storage."""

    @abstractmethod
    def load(self) -> MonzoCredentials:
        """Load credentials from storage."""
        pass

    @abstractmethod
    def save(self, credentials: MonzoCredentials) -> None:
        """Save credentials to storage."""
        pass


class FileAuthStorage(AuthStorage):
    """Default implementation of AuthStorage that saves to a JSON file."""

    def __init__(self, filename: str = "config/auth.json"):
        self.filename = filename

    def load(self) -> MonzoCredentials:
        """Load credentials from a JSON file."""
        if not os.path.exists(self.filename):
            return MonzoCredentials()
        
        try:
            with open(self.filename, "r") as f:
                data = json.load(f)
            return MonzoCredentials.model_validate(data)
        except (json.JSONDecodeError, IOError):
            return MonzoCredentials()

    def save(self, credentials: MonzoCredentials) -> None:
        """Save credentials to a JSON file."""
        config_dir = os.path.dirname(self.filename)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
            
        with open(self.filename, "w") as f:
            json.dump(credentials.to_dict(), f, indent=2, sort_keys=True)


class MemoryAuthStorage(AuthStorage):
    """In-memory implementation of AuthStorage for testing or short-lived scripts."""

    def __init__(self, credentials: Optional[MonzoCredentials] = None):
        self._credentials = credentials or MonzoCredentials()

    def load(self) -> MonzoCredentials:
        return self._credentials

    def save(self, credentials: MonzoCredentials) -> None:
        self._credentials = credentials
