import json
import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from src.agent.orchestrator import ConvFinQAManager
from src.agent.context_builder import ContextBuilder
from src.models.schemas import ConversationState, StudyCondition

app = typer.Typer(name="main", help="ConvFinQA Agentic Interface")
console = Console()
ROOT_DIR = Path(__file__).parent.parent
DATA_PATH = ROOT_DIR / "data" / "convfinqa_dataset.json"

def get_record_by_id(record_id: str):
    with open(DATA_PATH, "r") as f:
        dataset = json.load(f)["train"]
        for record in dataset:
            if record["id"] == record_id:
                return record
    return None

@app.command()
def chat(
    record_id: str = typer.Argument(..., help="ID of the record to chat about"),
    condition: int = typer.Option(7, help="Condition ID to use (1-7)")
) -> None:
    """Chat with the Synthetic Analyst using a specific Study Condition."""
    
    record = get_record_by_id(record_id)
    if not record:
        console.print(f"[red]Record ID '{record_id}' not found.[/red]")
        return

    # Use the selected Study Condition
    study_cond = StudyCondition(condition)
    manager = ConvFinQAManager(condition=study_cond)
    builder = ContextBuilder()
    
    context = builder.build(record)
    state = ConversationState(context=context, condition=study_cond)

    console.print(Panel(f"{context.markdown_table}", title=f"Analyzing {record_id} [Cond: {study_cond.name}]"))

    while True:
        message = input(">>> ")
        if message.strip().lower() in {"exit", "quit"}:
            break
            
        with console.status("[bold blue]Agent is reasoning..."):
            turn = manager.process_turn(state, message)

        # Output UI
        console.print(f"\n[bold blue]Question:[/bold blue] {message}")
        
        # Display Plan if available
        if turn.plan:
            console.print(f"[dim cyan]Plan:[/dim cyan] {turn.plan.analysis}")
        
        # Show Math and result
        console.print(Panel(
            f"[bold magenta]Expression:[/bold magenta] `{turn.final_expression}`\n"
            f"[bold green]Result:[/bold green] [bold white]{turn.conversational_response}[/bold white]",
            border_style="blue"
        ))

if __name__ == "__main__":
    app()