from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .state import AgentPhase

class EventType(str, Enum):
    """
    Types of events that can occur during an Agent Runtime execution.
    Designed for full auditability and replayability.
    """
    # Lifecycle
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    RUN_FAILED = "run_failed"
    PHASE_CHANGED = "phase_changed"
    
    # Interaction
    LLM_CALLED = "llm_called"
    LLM_RESPONDED = "llm_responded"
    USER_MESSAGE = "user_message"
    
    # Tool Use
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    
    # Runtime
    CHECKPOINT_SAVED = "checkpoint_saved"
    HANDOFF = "handoff"
    LOG_MESSAGE = "log_message"  # Generic infrastructure logs


@dataclass
class Event:
    """
    A single immutable event in the agent execution stream.
    """
    event_id: str
    run_id: str
    timestamp: str
    event_type: EventType
    
    # Context snapshots
    phase: AgentPhase
    agent_name: str
    
    # The actual data of the event
    payload: dict[str, Any] = field(default_factory=dict)
    
    # Tracing correlation
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        run_id: str,
        event_type: EventType,
        phase: AgentPhase,
        agent_name: str,
        payload: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> Event:
        """Factory method to create a new event with defaults."""
        return cls(
            event_id=str(uuid.uuid4()),
            run_id=run_id,
            timestamp=(timestamp or datetime.utcnow()).isoformat(),
            event_type=event_type,
            phase=phase,
            agent_name=agent_name,
            payload=payload or {},
            trace_id=trace_id,
            span_id=span_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "phase": self.phase.value,
            "agent_name": self.agent_name,
            "payload": self.payload,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Deserialize event from dictionary."""
        if "event_type" in data and isinstance(data["event_type"], str):
            data["event_type"] = EventType(data["event_type"])
        if "phase" in data and isinstance(data["phase"], str):
            data["phase"] = AgentPhase(data["phase"])
            
        return cls(**data)

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
        
    @classmethod
    def from_json(cls, json_str: str) -> Event:
        """Deserialize event from JSON string."""
        return cls.from_dict(json.loads(json_str))
