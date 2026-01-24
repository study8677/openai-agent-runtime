from __future__ import annotations

from typing import Protocol, runtime_checkable
from ..state import AgentState

@runtime_checkable
class CheckpointStore(Protocol):
    """
    Protocol for state checkpointing backends.
    """
    
    async def save(self, state: AgentState) -> None:
        """Save the current agent state."""
        ...
        
    async def load(self, run_id: str) -> AgentState | None:
        """Load the latest state for a given run."""
        ...
    
    async def list_runs(self) -> list[str]:
        """List all available run IDs."""
        ...
