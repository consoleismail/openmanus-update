"""Base integration class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel


class IntegrationBase(ABC, BaseModel):
    """Base class for external service integrations."""
    
    name: str
    enabled: bool = True
    
    class Config:
        arbitrary_types_allowed = True
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the service."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the service."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the integration is healthy."""
        pass
