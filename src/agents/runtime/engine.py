from __future__ import annotations

import logging
import asyncio
import os
from typing import Any, Optional, cast
from pathlib import Path

from agents import Agent, Runner, RunConfig
from agents.lifecycle import RunHooks
from agents.run_context import RunContextWrapper
from agents.items import ModelResponse, TResponseInputItem
from agents.tool import Tool

# MCP Imports
from agents.mcp import MCPServerManager, MCPServerStdio, MCPServerStdioParams

from .config import RuntimeConfig
from .events import Event, EventType
from .state import AgentPhase, AgentState
from .stores import EventStore, FileSystemEventStore, CheckpointStore, FileSystemCheckpointStore

logger = logging.getLogger(__name__)

class RuntimeHooks(RunHooks):
    """
    Hooks to bridge OpenAI SDK lifecycle events to Agent Runtime events/state.
    """
    def __init__(self, runtime: "AgentRuntime"):
        self.runtime = runtime

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: Optional[str],
        input_items: list[TResponseInputItem],
    ) -> None:
        await self.runtime._emit(EventType.LLM_CALLED, AgentPhase.PLANNING, {
            "model": self.runtime._current_model(),
            "input_count": len(input_items)
        })

    async def on_llm_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        response: ModelResponse,
    ) -> None:
        # Check if content exists
        content = getattr(response, "content", "") or ""
        await self.runtime._emit_and_save(EventType.LLM_RESPONDED, AgentPhase.PLANNING, {
            "content": content
        })

    async def on_tool_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Tool,
    ) -> None:
        self.runtime.state.phase = AgentPhase.EXECUTING
        await self.runtime._emit(EventType.TOOL_CALLED, AgentPhase.EXECUTING, {
            "tool": tool.name,
        })

    async def on_tool_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Tool,
        result: str,
    ) -> None:
        self.runtime.state.phase = AgentPhase.OBSERVING
        await self.runtime._emit_and_save(EventType.TOOL_RESULT, AgentPhase.OBSERVING, {
            "tool": tool.name,
            "output": result
        })

    async def on_agent_start(self, context: Any, agent: Agent[Any]) -> None:
        self.runtime.state.current_agent_name = agent.name
        self.runtime.state.turn_index += 1
        await self.runtime._emit_and_save(EventType.PHASE_CHANGED, self.runtime.state.phase, {
            "new_agent": agent.name,
            "turn": self.runtime.state.turn_index
        })


class AgentRuntime:
    """
    The main execution engine for the Agent Runtime.
    Wraps OpenAI Agents SDK Runner with explicitly managed state and persistence.
    """
    
    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.store = FileSystemEventStore(
            runs_dir=self.config.runs_dir,
            generate_markdown=self.config.log_format in ["markdown", "both"]
        )
        self.checkpoint_store = FileSystemCheckpointStore(
            runs_dir=self.config.runs_dir
        )
        self.state: AgentState = None  # type: ignore
        self._hooks = RuntimeHooks(self)
        
        # Initialize MCP Manager (but don't connect yet)
        self.mcp_manager = self._init_mcp_manager()

    def _init_mcp_manager(self) -> MCPServerManager | None:
        """Initialize MCP servers from config."""
        if not self.config.enable_mcp or not self.config.mcp_servers:
            return None
        
        servers = []
        for name, cmd_args in self.config.mcp_servers.items():
            if not cmd_args:
                continue
            # Assume Stdio for now as it's the standard for local tools
            server = MCPServerStdio(
                command=cmd_args[0],
                args=cmd_args[1:],
                params=MCPServerStdioParams(name=name)
            )
            servers.append(server)
            
        return MCPServerManager(servers=servers) if servers else None

    async def run(
        self,
        agent: Agent[Any],
        input_text: str,
        resume_from: Optional[str] = None
    ) -> AgentState:
        """
        Execute the agent with the given input.
        """
        # 1. Initialize or Load State
        if resume_from:
            logger.info(f"Resuming from run_id: {resume_from}")
            loaded_state = await self.checkpoint_store.load(resume_from)
            if loaded_state:
                self.state = loaded_state
                # Emit resumed event
                await self._emit(EventType.PHASE_CHANGED, self.state.phase, {
                    "action": "resume", 
                    "from_run_id": resume_from
                })
            else:
                logger.warning(f"Failed to load checkpoint for {resume_from}, starting new run.")
                resume_from = None
        
        if not resume_from:
            run_id = f"run_{asyncio.get_event_loop().time()}"
            self.state = AgentState(
                run_id=run_id,
                phase=AgentPhase.INIT,
                turn_index=0,
                current_agent_name=agent.name,
                work_dir=str(Path.cwd())
            )
            
            # 2. Emit Start Event
            config_dict = self.config.__dict__.copy() if hasattr(self.config, "__dict__") else {}
            # Serialize Paths
            for k, v in config_dict.items():
                if isinstance(v, Path):
                    config_dict[k] = str(v)
    
            await self._emit_and_save(EventType.RUN_STARTED, AgentPhase.INIT, {
                "config": config_dict
            })

        # 3. Load Context (CLAUDE.md) if enabled
        context_msg = ""
        if self.config.load_project_context:
            context_msg = self._load_context()
            if context_msg:
                original_instructions = agent.instructions or ""
                if isinstance(original_instructions, str):
                    agent = agent.clone(instructions=f"{original_instructions}\n\n{context_msg}")
        
        # 4. Run Loop (Delegating to SDK Runner)
        await self._emit(EventType.USER_MESSAGE, AgentPhase.PLANNING, {"content": input_text})
        self.state.phase = AgentPhase.PLANNING
        
        # Note: When resuming, we still treat the new input as "next turn" input.
        # But if we truly wanted to "resume middle of execution", we would need lower level control of Runner.
        # Current "resume" is basically "load memory/state and start NEW turn".
        # This fits "Chat" model.

        try:
            if self.mcp_manager:
                async with self.mcp_manager as active_servers:
                    agent_with_mcp = agent.clone(mcp_servers=active_servers)
                    
                    result = await Runner.run(
                        starting_agent=agent_with_mcp,
                        input=input_text,
                        max_turns=self.config.max_turns,
                        hooks=self._hooks
                    )
            else:
                result = await Runner.run(
                    starting_agent=agent,
                    input=input_text,
                    max_turns=self.config.max_turns,
                    hooks=self._hooks
                )
            
            # 5. Finish
            self.state.phase = AgentPhase.TERMINATED
            self.state.last_output = str(result.final_output)
            await self._emit_and_save(EventType.RUN_FINISHED, AgentPhase.TERMINATED, {
                "final_output": str(result.final_output)
            })
            
        except Exception as e:
            self.state.phase = AgentPhase.FAILED
            await self._emit_and_save(EventType.RUN_FAILED, AgentPhase.FAILED, {"error": str(e)})
            raise e
            
        return self.state

    async def _emit(
        self, 
        event_type: EventType, 
        phase: AgentPhase, 
        payload: dict[str, Any] | None = None
    ) -> None:
        """Internal helper to emit events without saving checkpoint."""
        event = Event.create(
            run_id=self.state.run_id,
            event_type=event_type,
            phase=phase,
            agent_name=self.state.current_agent_name,
            payload=payload
        )
        await self.store.append(event)
        
    async def _emit_and_save(
        self, 
        event_type: EventType, 
        phase: AgentPhase, 
        payload: dict[str, Any] | None = None
    ) -> None:
        """Emit event AND save checkpoint."""
        await self._emit(event_type, phase, payload)
        await self.checkpoint_store.save(self.state)

    def _current_model(self) -> str:
        return "default-model"

    def _load_context(self) -> str:
        """Load project context from CLAUDE.md if it exists."""
        claude_md = Path("CLAUDE.md")
        if claude_md.exists():
            try:
                content = claude_md.read_text(encoding="utf-8")
                return f"Project Context (from CLAUDE.md):\n{content}"
            except Exception as e:
                logger.warning(f"Failed to read CLAUDE.md: {e}")
        return ""
