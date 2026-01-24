from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

class AgentPhase(str, Enum):
    """
    Standardized lifecycle phases for the Agent Runtime.
    Explicitly tracks the agent's current mode of operation.
    """
    INIT = "init"
    PLANNING = "planning"
    EXECUTING = "executing"  # Executing tools
    OBSERVING = "observing"  # Processing tool outputs
    HANDOFF = "handoff"
    TERMINATED = "terminated"
    FAILED = "failed"


@dataclass
class AgentState:
    """
    Explicit, serializable state of the Agent Runtime.
    
    This state object is the single source of truth for the agent's execution.
    It can be serialized to disk (checkpointing) and reloaded to resume execution.
    """
    run_id: str
    phase: AgentPhase
    turn_index: int
    current_agent_name: str
    
    # Context: The short-term memory (conversation history)
    # Stored as a list of dictionaries compatible with OpenAI message format
    messages: list[dict[str, Any]] = field(default_factory=list)
    
    # Memory: Long-term or specific memory (KV store)
    memory: dict[str, Any] = field(default_factory=dict)
    
    # Execution Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_checkpoint_id: Optional[str] = None
    
    # Runtime Environment
    work_dir: Optional[str] = None
    last_output: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize state to a dictionary."""
        return {
            "run_id": self.run_id,
            "phase": self.phase.value,
            "turn_index": self.turn_index,
            "current_agent_name": self.current_agent_name,
            "messages": self.messages,
            "memory": self.memory,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_checkpoint_id": self.last_checkpoint_id,
            "work_dir": self.work_dir,
            "last_output": self.last_output,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentState:
        """Deserialize state from a dictionary."""
        # Handle enum conversion
        if "phase" in data and isinstance(data["phase"], str):
            data["phase"] = AgentPhase(data["phase"])
            
        return cls(**data)
        
    def to_json(self) -> str:
        """Serialize state to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> AgentState:
        """Deserialize state from JSON string."""
        return cls.from_dict(json.loads(json_str))
