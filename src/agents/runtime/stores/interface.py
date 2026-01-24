from __future__ import annotations

from typing import Protocol, runtime_checkable
from ..events import Event

@runtime_checkable
class EventStore(Protocol):
    """
    Protocol for event storage backends.
    """
    
    async def append(self, event: Event) -> None:
        """Append a single event to the store."""
        ...
        
    async def get_events(self, run_id: str) -> list[Event]:
        """Retrieve all events for a specific run."""
        ...
