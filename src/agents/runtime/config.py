from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

@dataclass
class RuntimeConfig:
    """
    Configuration for the Agent Runtime.
    """
    
    # Persistence
    persistence_dir: Path | str = field(default_factory=lambda: Path(".runtime"))
    enable_persistence: bool = True
    
    # Logging
    log_format: Literal["jsonl", "markdown", "both"] = "both"
    verbose: bool = False
    
    # MCP
    enable_mcp: bool = True
    mcp_servers: dict[str, list[str]] = field(default_factory=dict)
    
    # Execution
    max_turns: int = 10
    timeout_seconds: float = 300.0
    
    # Context
    load_project_context: bool = True  # Load CLAUDE.md if exists
    
    def __post_init__(self):
        # Ensure persistence_dir is a Path object
        if isinstance(self.persistence_dir, str):
            self.persistence_dir = Path(self.persistence_dir)
            
    @property
    def runs_dir(self) -> Path:
        """Directory for storing run data."""
        return self.persistence_dir / "runs"
        
    def get_run_dir(self, run_id: str) -> Path:
        """Get the specific directory for a run."""
        return self.runs_dir / run_id
