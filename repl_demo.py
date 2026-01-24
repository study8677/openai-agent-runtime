import asyncio
import logging
import os
import sys
from pathlib import Path

# Try to import rich for better UI
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.status import Status
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

from agents import Agent, function_tool
from agents.runtime import AgentRuntime, RuntimeConfig, AgentPhase

# Configure logging
logging.basicConfig(
    filename="runtime_repl.log", 
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Mock tool
@function_tool
def get_current_time() -> str:
    """Get the current time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def print_user(msg):
    if RICH_AVAILABLE:
        console.print(f"\n[bold blue]User:[/bold blue] {msg}")
    else:
        print(f"\nUser: {msg}")

def print_agent(msg):
    if RICH_AVAILABLE:
        console.print(Panel(Markdown(msg), title="Agent", border_style="green"))
    else:
        print(f"\nAgent:\n{msg}\n")

def print_info(msg):
    if RICH_AVAILABLE:
        console.print(f"[dim]{msg}[/dim]")
    else:
        print(f"[Info] {msg}")

def print_error(msg):
    if RICH_AVAILABLE:
        console.print(f"[bold red]Error:[/bold red] {msg}")
    else:
        print(f"Error: {msg}")

LAST_RUN_FILE = Path(".last_run_id")

async def main():
    # Configuration via Env Vars
    # Default to local Ollama if not set, for convenience? Or stick to OpenAI default?
    # User asked for Ollama. Let's make it easy to switch.
    
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("MODEL", "gpt-4o") # Default to gpt-4o, user can change to 'llama3'

    if not api_key:
        if base_url:
             # If using custom base_url (like Ollama), we might not need a real key.
             # Set dummy key to pass SDK validation.
             os.environ["OPENAI_API_KEY"] = "sk-ollama-dummy"
             print_info("Using dummy API key for custom base_url.")
        else:
            print_error("OPENAI_API_KEY environment variable is not set!")
            print_info("For OpenAI: export OPENAI_API_KEY=sk-...")
            print_info("For Ollama: export OPENAI_BASE_URL=http://localhost:11434/v1 and run again (dummy key will be used)")
            return

    # 1. Config
    config = RuntimeConfig(
        persistence_dir=".runtime_repl_data",
        log_format="both",
        enable_mcp=False,
        verbose=True
    )
    
    runtime = AgentRuntime(config)
    
    agent = Agent(
        name="demo_bot",
        model=model_name,
        instructions="You are a helpful AI assistant. Be concise.",
        tools=[get_current_time]
    )

    # 2. Check for resume
    resume_id = None
    if LAST_RUN_FILE.exists():
        resume_id = LAST_RUN_FILE.read_text().strip()
        print_info(f"Found previous session: {resume_id}")
        # Auto-resume or ask? Let's ask but default Y for demo speed
        print_info(f"Resuming session {resume_id}...")
    
    current_run_id = resume_id

    print_info(f">>> Agent Runtime REPL started.")
    print_info(f"Model: {model_name}")
    print_info(f"Base URL: {base_url or 'Default (OpenAI)'}")
    print_info(f"Logs: {config.runs_dir}")
    print_info("Type 'exit' to quit.")

    while True:
        try:
            user_input = input("\n> ")
            if user_input.lower() in ("exit", "quit"):
                break
            if not user_input.strip():
                continue
            
            # Show spinner
            if RICH_AVAILABLE:
                status = console.status(f"[bold green]Run ID: {current_run_id or 'New'} | Processing...", spinner="dots")
                status.start()
            else:
                print("Processing...")
                
            try:
                state = await runtime.run(agent, user_input, resume_from=current_run_id)
                current_run_id = state.run_id
                
                if RICH_AVAILABLE:
                    status.stop()
                
                # Print result from state
                if state.last_output:
                    print_agent(state.last_output)
                else:
                    print_agent("(No output returned)")

                # Save run ID
                LAST_RUN_FILE.write_text(current_run_id)

            except Exception as e:
                if RICH_AVAILABLE:
                    status.stop()
                print_error(f"Runtime Exception: {e}")

        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    asyncio.run(main())
