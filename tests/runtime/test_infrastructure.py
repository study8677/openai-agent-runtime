import json
import shutil
import tempfile
from pathlib import Path

import pytest
from agents.runtime import AgentPhase, AgentState, Event, EventType, RuntimeConfig
from agents.runtime.stores import FileSystemEventStore

class TestAgentState:
    def test_serialization(self):
        state = AgentState(
            run_id="run_123",
            phase=AgentPhase.PLANNING,
            turn_index=1,
            current_agent_name="test_agent",
            messages=[{"role": "user", "content": "hello"}],
            memory={"key": "value"},
        )
        
        json_str = state.to_json()
        restored = AgentState.from_json(json_str)
        
        assert restored.run_id == "run_123"
        assert restored.phase == AgentPhase.PLANNING
        assert restored.messages == [{"role": "user", "content": "hello"}]
        assert restored.memory == {"key": "value"}

class TestEvent:
    def test_creation_and_serialization(self):
        event = Event.create(
            run_id="run_123",
            event_type=EventType.TOOL_CALLED,
            phase=AgentPhase.EXECUTING,
            agent_name="test_agent",
            payload={"tool": "weather", "input": {"city": "Tokyo"}},
        )
        
        json_str = event.to_json()
        restored = Event.from_dict(json.loads(json_str))
        
        assert restored.run_id == "run_123"
        assert restored.event_type == EventType.TOOL_CALLED
        assert restored.phase == AgentPhase.EXECUTING
        assert restored.payload["tool"] == "weather"

@pytest.fixture
def temp_run_dir():
    # Create temp dir
    dir_path = Path(tempfile.mkdtemp())
    yield dir_path
    # Cleanup
    shutil.rmtree(dir_path)

@pytest.mark.asyncio
class TestFileSystemEventStore:
    async def test_dual_persistence(self, temp_run_dir):
        store = FileSystemEventStore(runs_dir=temp_run_dir)
        run_id = "test_run"
        
        # 1. Start Event
        e1 = Event.create(
            run_id=run_id,
            event_type=EventType.RUN_STARTED,
            phase=AgentPhase.INIT,
            agent_name="system",
        )
        await store.append(e1)
        
        # 2. User Message
        e2 = Event.create(
            run_id=run_id,
            event_type=EventType.USER_MESSAGE,
            phase=AgentPhase.PLANNING,
            agent_name="user",
            payload={"content": "Check weather in Tokyo"},
        )
        await store.append(e2)
        
        # 3. Tool Call
        e3 = Event.create(
            run_id=run_id,
            event_type=EventType.TOOL_CALLED,
            phase=AgentPhase.EXECUTING,
            agent_name="assistant",
            payload={"tool": "get_weather", "input": {"city": "Tokyo"}},
        )
        await store.append(e3)

        # Verify JSONL
        jsonl_path = temp_run_dir / run_id / "events.jsonl"
        assert jsonl_path.exists()
        
        events = await store.get_events(run_id)
        assert len(events) == 3
        assert events[0].event_type == EventType.RUN_STARTED
        assert events[2].payload["tool"] == "get_weather"
        
        # Verify Markdown
        md_path = temp_run_dir / run_id / "trace.md"
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        
        assert "# Agent Run Trace" in content
        assert "User" in content
        assert "Check weather in Tokyo" in content
        assert "Tool Call" in content
        assert "`get_weather`" in content
