import asyncio
import logging
from pathlib import Path
import os

from agents import Agent, function_tool
from agents.runtime import AgentRuntime, RuntimeConfig, AgentPhase

# Setup logging
logging.basicConfig(level=logging.INFO)

# Define a tool
@function_tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city} is Sunny, 25C"

async def main():
    # 1. Config
    config = RuntimeConfig(
        persistence_dir=".runtime_test",
        log_format="both",
        enable_mcp=False,
        load_project_context=True,
        max_turns=3
    )
    
    # 2. Runtime
    runtime = AgentRuntime(config)
    
    # 3. Agent
    agent = Agent(
        name="weather_bot",
        instructions="You are a helpful assistant.",
        tools=[get_weather]
    )
    
    # Set OpenAI Key via environment if available, else mock?
    # Actually basic local tools agent doesn't need OpenAI if not calling LLM?
    # Wait, Runner always calls model. 
    # For testing without Key, we need to mock or set Key.
    # Assuming user has env logic or similar. If not, this script fails.
    # But previous error was "The api_key client option must be set".
    # I will set a dummy key because I'm not actually hitting API if I mock model?
    # Or I should expect failure but check if "Started" event logged.
    
    # Let's set a dummy key to bypass client init check, 
    # but actual calls will fail if network is attempted. 
    # For infrastructure test, we just want to see events generated until error.
    os.environ["OPENAI_API_KEY"] = "sk-dummy"

    # 4. First Run
    print(">>> Starting Run 1...")
    try:
        state1 = await runtime.run(agent, "What is the weather in Tokyo?")
    except Exception as e:
        print(f"Run 1 ended with expected error (no real API): {e}")
        # Even if failed, state should have run_id
        state1 = runtime.state

    print(f"\n>>> Run 1 ID: {state1.run_id}")
    run1_id = state1.run_id
    
    # Verify outputs
    run_dir = config.get_run_dir(run1_id)
    state_json = run_dir / "state.json"
    
    if state_json.exists():
        print(f"  ✅ state.json found at {state_json}")
        print(f"  Content: {state_json.read_text()[:100]}...")
    else:
        print("  ❌ state.json MISSING")
        return

    # 5. Resume Run
    print(f"\n>>> Starting Run 2 (Resume from {run1_id})...")
    # Using same runtime instance, but `run()` re-initializes `self.state` if resume_from passed.
    try:
        # We pass a NEW input, as if user continued conversation.
        state2 = await runtime.run(agent, "And how about Osaka?", resume_from=run1_id)
    except Exception as e:
        print(f"Run 2 ended with expected error: {e}")
        state2 = runtime.state

    print(f"\n>>> Run 2 ID: {state2.run_id}")
    
    if state2.run_id == run1_id:
        print("  ✅ Run ID preserved (Resume successful)")
    else:
        print(f"  ❌ Run ID changed! Expected {run1_id}, got {state2.run_id}")

    # Check turn index increased? 
    # Since Run 1 failed at start, turn_index might be small.
    # But if state was loaded, we continue from there.

if __name__ == "__main__":
    asyncio.run(main())
