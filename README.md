# OpenAI Agent Runtime

[English](README.md) | [中文](README_zh.md)

**Agent Runtime** is an advanced execution engine built on top of the `openai-agents-python` SDK. It is designed to fill the gap in building long-running, stateful, and recoverable agent applications, providing capabilities similar to Anthropic's Claude Desktop or production-grade agent systems.

## 🌟 What We Built

While the native SDK (`Runner`) provides a basic execution loop, **Agent Runtime** extends it with critical engineering features required for real-world applications:

### 1. 🛡️ Robust Lifecycle Management
We introduced a structured **Phase** system to track the agent's exact state:
- `INIT`: Runtime configuration and initialization.
- `PLANNING`: Agent reasoning and LLM invocation.
- `EXECUTING`: Tool execution phase.
- `OBSERVING`: Processing tool results and environment feedback.
- `TERMINATED` / `FAILED`: Explicit terminal states.

### 2. 💾 Dual-Layer Persistence
To satisfy both machine replayability and human readability, we implemented a dual-write logging system:
- **Machine Layer (`events.jsonl`)**: A structured event stream recording every state change. Used for debugging stats or precise replay.
- **Human Layer (`trace.md`)**: A real-time Markdown rendering of the execution trace. Read the agent's thought process and tool outputs like an article.

### 3. ⏯️ Checkpoint & Resume
This is the core capability of the Runtime. The engine automatically saves a **Checkpoint (`state.json`)** after every key operation (like tool execution).
- **Zero State Anxiety**: Even if the process crashes or is interrupted, the Agent's memory (Conversation History) and current state (Turn Index) are preserved.
- **Hot Resume**: Simply use `resume_from="run_id"` to instantly restore the previous session state and continue execution.

### 4. 🔌 MCP & Local Model Support
- **MCP Host**: Native integration with the Model Context Protocol, allowing direct mounting of standard MCP Servers (e.g., Filesystem, Google Drive).
- **Ollama/Local LLM**: Full support for Ollama, vLLM, and other local models via the OpenAI-compatible layer. Just configure `OPENAI_BASE_URL`.

---

## 🚀 Quick Start

### Installation

Ensure Python 3.10+ is installed:

```bash
# Clone the repository
git clone https://github.com/study8677/openai-agent-runtime.git
cd openai-agent-runtime

# Install dependencies
pip install -e .
pip install rich  # Recommended: For pretty terminal UI
```

### Interactive Demo (REPL)

We provide a full-featured REPL environment demonstrating all the features above.

**Using OpenAI:**
```bash
export OPENAI_API_KEY=sk-proj-xxxx
python examples/runtime/repl_demo.py
```

**Using Ollama (Local):**
```bash
# Start Ollama and ensure a model is pulled (e.g., qwen3:0.6b)
export OPENAI_BASE_URL=http://localhost:11434/v1
export MODEL=qwen3:0.6b
# The script automatically detects base_url and uses a dummy key
python examples/runtime/repl_demo.py
```

---

## 🏗️ Architecture Overview

### Core Components

1. **`AgentRuntime`**: The engine entry point. Orchestrates the SDK Runner, Hooks, EventStore, and CheckpointStore.
2. **`AgentState`**: Single Source of Truth. All runtime state is stored in this serializable data class.
3. **`RuntimeHooks`**: The bridge layer. Intercepts SDK callbacks like `on_llm_start` or `on_tool_end` and converts them into standardized Runtime Events.
4. **`FileSystemEventStore`**: Handles real-time writing of the event stream to disk.

### File Structure

All runtime data is stored in `.runtime_repl_data/` (or your configured path) by default:

```text
.runtime_repl_data/
└── runs/
    └── run_1737731234/          # Independent directory per run
        ├── events.jsonl         # Machine logs (JSONL)
        ├── trace.md             # Human logs (Markdown)
        └── state.json           # Final state snapshot (Checkpoint)
```



---

## �️ Python API Usage

To integrate Agent Runtime into your own application:

```python
import asyncio
from agents import Agent, function_tool
from agents.runtime import AgentRuntime, RuntimeConfig

# 1. Define Tools
@function_tool
def get_weather(city: str) -> str:
    return f"{city} is sunny."

# 2. Initialize Runtime
config = RuntimeConfig(
    persistence_dir="./my_agent_data",
    log_format="both",  # Generate both jsonl and markdown
    enable_mcp=False
)
runtime = AgentRuntime(config)

agent = Agent(name="bot", tools=[get_weather])

# 3. Run Agent
async def main():
    # First Run
    state = await runtime.run(agent, "What's the weather in Tokyo?")
    print(f"Result: {state.last_output}")
    
    # 4. Resume from Interruption
    # Use the previous run_id
    new_state = await runtime.run(
        agent, 
        "And how about Osaka?", 
        resume_from=state.run_id
    )
    print(f"Resumed Result: {new_state.last_output}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 📝 Roadmap & Contribution

We are building the most robust Agent Runtime, and our next focus areas are:

- **🔌 More MCP Support**: Official adapters for Filesystem, Git, PostgreSQL, Slack, and other popular MCP Servers.
- **🧩 Agent Skills**: A standard for reusable capability packages (e.g., "Data Analysis Skill", "Web Scraper Skill").
- **🛡️ Security Sandbox**: Fine-grained permission control for tool execution.

**🤝 We Welcome Contributions!**
If you have built a new MCP connector or an interesting Agent Skill, please submit a PR! Let's redefine the AI Agent development experience together.

---
*Built with ❤️ by the Advanced Agentic Coding Team.*
