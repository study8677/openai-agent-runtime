from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiofiles

from ..events import Event, EventType
from .interface import EventStore

logger = logging.getLogger(__name__)

class FileSystemEventStore(EventStore):
    """
    Event store that persists events to the local filesystem.
    Supports dual persistency:
    1. events.jsonl: Machine readable, complete event stream
    2. trace.md: Human readable, summarized execution trace
    """
    
    def __init__(self, runs_dir: Path | str, generate_markdown: bool = True):
        self.runs_dir = Path(runs_dir)
        self.generate_markdown = generate_markdown
        
    def _get_run_dir(self, run_id: str) -> Path:
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
        
    def _get_jsonl_path(self, run_id: str) -> Path:
        return self._get_run_dir(run_id) / "events.jsonl"
        
    def _get_markdown_path(self, run_id: str) -> Path:
        return self._get_run_dir(run_id) / "trace.md"

    async def append(self, event: Event) -> None:
        """Append event to both jsonl and markdown files."""
        run_dir = self._get_run_dir(event.run_id)
        
        # 1. Append to JSONL
        jsonl_path = self._get_jsonl_path(event.run_id)
        async with aiofiles.open(jsonl_path, mode="a", encoding="utf-8") as f:
            await f.write(event.to_json() + "\n")
            
        # 2. Append to Markdown (if enabled)
        if self.generate_markdown:
            md_path = self._get_markdown_path(event.run_id)
            md_content = self._format_event_markdown(event)
            if md_content:
                async with aiofiles.open(md_path, mode="a", encoding="utf-8") as f:
                    await f.write(md_content + "\n")

    async def get_events(self, run_id: str) -> list[Event]:
        """Read all events from JSONL."""
        jsonl_path = self._get_jsonl_path(run_id)
        if not jsonl_path.exists():
            return []
            
        events = []
        async with aiofiles.open(jsonl_path, mode="r", encoding="utf-8") as f:
            async for line in f:
                if line.strip():
                    try:
                        events.append(Event.from_json(line))
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode event line: {line[:50]}...")
        return events

    def _format_event_markdown(self, event: Event) -> str | None:
        """Format a single event into Markdown for human readability."""
        timestamp = event.timestamp
        agent = event.agent_name
        
        if event.event_type == EventType.RUN_STARTED:
            return f"# Agent Run Trace\n\n**Run ID:** `{event.run_id}`\n**Started:** {timestamp}\n\n---\n"
            
        elif event.event_type == EventType.PHASE_CHANGED:
            new_phase = event.payload.get("new_phase")
            return f"\n## Phase: {new_phase}\n"
            
        elif event.event_type == EventType.USER_MESSAGE:
            content = event.payload.get("content", "")
            return f"\n### 👤 User\n\n{content}\n"
            
        elif event.event_type == EventType.LLM_CALLED:
            # Maybe too verbose to log every call input in markdown? 
            # Let's log a summary
            model = event.payload.get("model", "unknown")
            return f"\n> 🤖 **Calling LLM** ({model})...\n"
            
        elif event.event_type == EventType.LLM_RESPONDED:
            content = event.payload.get("content", "")
            return f"\n### 🤖 {agent}\n\n{content}\n"
            
        elif event.event_type == EventType.TOOL_CALLED:
            tool_name = event.payload.get("tool", "unknown")
            tool_input = json.dumps(event.payload.get("input", {}), indent=2)
            return f"\n#### 🛠️ Tool Call: `{tool_name}`\n\n```json\n{tool_input}\n```\n"
            
        elif event.event_type == EventType.TOOL_RESULT:
            tool_name = event.payload.get("tool", "unknown")
            result = event.payload.get("output", "")
            # Truncate long results
            if isinstance(result, str) and len(result) > 500:
                result = result[:500] + "... (truncated)"
            return f"\n#### 🏁 Tool Result: `{tool_name}`\n\n```\n{result}\n```\n"
            
        elif event.event_type == EventType.TOOL_ERROR:
            tool_name = event.payload.get("tool", "unknown")
            error = event.payload.get("error", "Unknown error")
            return f"\n#### ❌ Tool Error: `{tool_name}`\n\n```\n{error}\n```\n"
            
        elif event.event_type == EventType.RUN_FINISHED:
            return f"\n---\n\n**Run Finished** at {timestamp}\n"
            
        elif event.event_type == EventType.RUN_FAILED:
            error = event.payload.get("error", "Unknown error")
            return f"\n---\n\n**❌ RUN FAILED**\n\nError: {error}\n"
            
        return None
