# OpenAI Agent Runtime (运行时引擎)

[English](README.md) | [中文](README_zh.md)

**Agent Runtime** 是一个构建在 `openai-agents-python` SDK 之上的高级执行引擎。它旨在弥补原生 SDK 在构建长期运行、有状态、可恢复的智能体应用时的空白，提供类似 Claude Desktop 或生产级 Agent 系统的能力。

## 🌟 我们做了什么？ (What we built)

原生 SDK (`Runner`) 提供了基础的运行循环，但在实际工程化落地中，往往缺少以下关键特性，而 **Agent Runtime** 将其补全：

### 1. 🛡️ 稳健的生命周期管理 (Lifecycle Management)
我们引入了明确的 **Phase (阶段)** 概念，将 Agent 的执行过程结构化：
- `INIT`: 初始化运行时配置。
- `PLANNING`: Agent 思考与调用 LLM 阶段。
- `EXECUTING`: 外部工具（Tools）执行阶段。
- `OBSERVING`: 接收工具结果与环境反馈阶段。
- `TERMINATED` / `FAILED`: 明确的结束状态。

### 2. 💾 双层持久化系统 (Dual-Layer Persistence)
为了同时满足机器回放和人类调试的需求，我们实现了一套双写日志系统：
- **机器层 (`events.jsonl`)**: 记录每一次状态变更的结构化事件流。可以用于精确重放 (Replay) 或分析。
- **人类层 (`trace.md`)**: 实时渲染精美的 Markdown 追踪日志，像阅读文章一样查看 Agent 的思考过程、工具调用参数和最终结果。

### 3. ⏯️ 检查点与断点续传 (Undo & Resume)
这是 Runtime 最核心的能力。引擎会在每次关键操作（如工具执行后）自动保存 **Checkpoint (`state.json`)**。
- **无状态焦虑**: 哪怕进程崩溃或被强制中断，Agent 的记忆（Conversation History）、当前状态（Turn Index）都会被完整保留。
- **热加载**: 使用 `resume_from="run_id"` 即可瞬间恢复到上一次的会话状态，继续执行。

### 4. 🔌 MCP & 本地模型支持
- **MCP Host**: 原生集成了 Model Context Protocol，可以直接挂载标准 MCP Server（如 Filesystem, Google Drive 等）。
- **Ollama/Local LLM**: 通过兼容层支持 Ollama、vLLM 等本地模型，只需配置 `OPENAI_BASE_URL` 即可无缝切换。

---

## 🚀 快速上手 (Quick Start)

### 安装

配置 Python 3.10+ 环境并安装依赖：

```bash
# 克隆仓库
git clone https://github.com/study8677/openai-agent-runtime.git
cd openai-agent-runtime

# 安装依赖
pip install -e .
pip install rich  # 推荐：用于美化终端演示
```

### 运行交互式 Demo (REPL)

我们提供了一个全功能的 REPL 环境，展示了上述所有特性。

**连接 OpenAI:**
```bash
export OPENAI_API_KEY=sk-proj-xxxx
python examples/runtime/repl_demo.py
```

**连接 Ollama (本地):**
```bash
# 启动 Ollama 并确保已有模型（如 qwen3:0.6b）
export OPENAI_BASE_URL=http://localhost:11434/v1
export MODEL=qwen3:0.6b
# 脚本会自动检测并使用虚拟 Key 连接
python examples/runtime/repl_demo.py
```

---

## 🏗️ 架构概览 (Architecture)

### 核心组件

1. **`AgentRuntime`**: 引擎入口。负责组装 SDK Runner、挂载 Hooks、管理 EventStore 和 CheckpointStore。
2. **`AgentState`**: 单一事实来源 (Single Source of Truth)。所有的运行时状态都存储在这个可序列化的数据类中。
3. **`RuntimeHooks`**: 桥接层。拦截 SDK 的 `on_llm_start`, `on_tool_end` 等回调，将其转化为 Runtime 的标准 Events。
4. **`FileSystemEventStore`**: 负责将内存中的事件流实时落盘。

### 目录结构与可视化日志

所有运行时数据默认存储在 `.runtime_repl_data/` (或配置的目录) 下：

```text
.runtime_repl_data/
└── runs/
    └── run_1737731234/          # 每次运行一个独立目录
        ├── events.jsonl         # 机器日志 (JSONL)
        ├── trace.md             # 人类日志 (Markdown)
        └── state.json           # 最终状态快照 (Checkpoint)
```

### 运行交互式 Demo (REPL)

如果你想将 Runtime 集成到自己的应用中：

```python
import asyncio
from agents import Agent, function_tool
from agents.runtime import AgentRuntime, RuntimeConfig

# 1. 定义工具
@function_tool
def get_weather(city: str) -> str:
    return f"{city} is sunny."

# 2. 初始化 Runtime
config = RuntimeConfig(
    persistence_dir="./my_agent_data",
    log_format="both",  # 同时生成 jsonl 和 markdown
    enable_mcp=False
)
runtime = AgentRuntime(config)

agent = Agent(name="bot", tools=[get_weather])

# 3. 运行 Agent
async def main():
    # 第一次运行
    state = await runtime.run(agent, "What's the weather in Tokyo?")
    print(f"Result: {state.last_output}")
    
    # 4. 模拟中断后恢复 (Resume)
    # 使用上一次的 run_id
    new_state = await runtime.run(
        agent, 
        "And how about Osaka?", 
        resume_from=state.run_id
    )
    print(f"Resumed Result: {new_state.last_output}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 📝 未来计划与贡献 (Roadmap & Contribution)

我们正致力于构建最强大的 Agent 运行时，接下来的重点是：

- **🔌 更多 MCP 支持**: 官方适配 Filesystem, Git, PostgreSQL, Slack 等常用 MCP Server。
- **🧩 Skills 机制**: 推出的可复用“技能包”标准，支持一键加载复杂能力（如“数据分析技能”、“网页爬虫技能”）。
- **🛡️ 安全沙箱**: 更细粒度的工具执行权限控制。

**🤝 欢迎贡献!**
我们非常欢迎社区参与！如果你开发了新的 MCP Server 连接器或有趣的 Agent Skill，请提交 PR 贡献给我们。让我们一起重新定义 AI Agent 的开发体验。

---
*Built with ❤️ by the Advanced Agentic Coding Team.*
