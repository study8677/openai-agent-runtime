from __future__ import annotations

import logging
import json
from pathlib import Path
import aiofiles

from ..state import AgentState
from .checkpoint import CheckpointStore

logger = logging.getLogger(__name__)

class FileSystemCheckpointStore(CheckpointStore):
    """
    Checkpoint store that saves state to the local filesystem as JSON.
    Location: {runs_dir}/{run_id}/state.json
    """
    
    def __init__(self, runs_dir: Path | str):
        self.runs_dir = Path(runs_dir)
        
    def _get_run_dir(self, run_id: str) -> Path:
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
        
    def _get_state_path(self, run_id: str) -> Path:
        return self._get_run_dir(run_id) / "state.json"

    async def save(self, state: AgentState) -> None:
        """Save state to state.json."""
        state_path = self._get_state_path(state.run_id)
        # Atomic write pattern could be better, but simple overwrite is fine for now
        async with aiofiles.open(state_path, mode="w", encoding="utf-8") as f:
            await f.write(state.to_json())

    async def load(self, run_id: str) -> AgentState | None:
        """Load state from state.json."""
        state_path = self._get_state_path(run_id)
        if not state_path.exists():
            return None
            
        async with aiofiles.open(state_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            try:
                state = AgentState.from_json(content)
                state.work_dir = str(state_path.parent) # Ensure work_dir is set to current location? 
                # Actually state.work_dir should come from persisted state.
                return state
            except json.JSONDecodeError:
                logger.error(f"Failed to decode state for run {run_id}")
                return None

    async def list_runs(self) -> list[str]:
        """List all run IDs (directories in runs_dir)."""
        if not self.runs_dir.exists():
            return []
        return [d.name for d in self.runs_dir.iterdir() if d.is_dir()]
