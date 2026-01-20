import json
import random
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.progress import track

from src.utils.parser import table_to_markdown
from src.models.schemas import TableEquivalence 
from src.agent.client import ReasoningClient

# --- Configuration ---
CONSOLE = Console()
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
PROMPT_DIR = ROOT_DIR / "src" / "agent" / "prompts"

PATHS = {
    "data": DATA_DIR / "convfinqa_dataset.json",
    "log": DATA_DIR / "parser_failures.json",
    "system_prompt": PROMPT_DIR / "validator_system_prompt.xml"
}

RANDOM_SEED = 42

class TableAuditor:
    def __init__(self):
        self.client = ReasoningClient()
        if not PATHS["system_prompt"].exists():
            raise FileNotFoundError(f"Missing validator prompt: {PATHS['system_prompt']}")
        self.instructions = PATHS["system_prompt"].read_text(encoding="utf-8")

    def audit(self, json_table: Dict, md_table: str) -> TableEquivalence:
        payload = (
            f"JSON SOURCE:\n{json.dumps(json_table, indent=2)}\n\n"
            f"MARKDOWN OUTPUT:\n{md_table}"
        )
        return self.client.get_structured_response(
            instructions=self.instructions,
            input_text=payload,
            response_model=TableEquivalence,
            effort="medium"
        )

class HeuristicValidator:
    @staticmethod
    def get_errors(json_table: Dict, md_table: str) -> List[str]:
        errors = []
        lines = [line for line in md_table.split("\n") if "|" in line]
        
        if not lines:
            return ["Table is empty or missing markdown pipes."]
        
        # Structure Check: Pipe consistency
        pipe_counts = [line.count("|") for line in lines]
        if len(set(pipe_counts)) > 1:
            errors.append("Structural mismatch: Inconsistent pipe counts across rows.")

        # Data Integrity: Check for numeric persistence
        clean_md = md_table.replace(",", "")
        for col in json_table.values():
            for val in col.values():
                if isinstance(val, (int, float)):
                    # Check for string representation to avoid int/float truncation issues
                    if str(val) not in clean_md:
                        errors.append(f"Missing numeric value: {val}")
                        return errors # Exit early on first missing value to save time
        return errors

def run_validation_suite(sample_size: int = 1000, success_audit_limit: int = 15):
    random.seed(RANDOM_SEED)
    
    if not PATHS["data"].exists():
        CONSOLE.print(f"[bold red]Source data not found: {PATHS['data']}[/bold red]")
        return

    with open(PATHS["data"], "r") as f:
        all_data = json.load(f).get("train", [])
        records = random.sample(all_data, min(sample_size, len(all_data)))

    auditor = TableAuditor()
    validator = HeuristicValidator()
    
    heuristic_successes = []
    heuristic_failures = []
    final_failures = []
    audit_rescues = 0

    CONSOLE.print(f"\n[bold blue]Running validation suite on {len(records)} records...[/bold blue]")

    # Phase 1: Heuristic Screening
    for record in track(records, description="Heuristic Screening"):
        md = table_to_markdown(record["doc"]["table"])
        errors = validator.get_errors(record["doc"]["table"], md)
        
        item = {"record": record, "md": md, "errors": errors}
        if not errors:
            heuristic_successes.append(item)
        else:
            heuristic_failures.append(item)

    # Phase 2: LLM Audit of Failures
    for item in track(heuristic_failures, description="Auditing Failures"):
        result = auditor.audit(item["record"]["doc"]["table"], item["md"])
        if not result.is_equivalent:
            final_failures.append({
                "record_id": item["record"]["id"],
                "failure_type": "HEURISTIC_CONFIRMED",
                "heuristic_errors": item["errors"],
                "audit_reasoning": result.reasoning,
                "md_output": item["md"]
            })
        else:
            audit_rescues += 1

    # Phase 3: Spot-check Successes (Silent Failure Detection)
    success_sample = random.sample(heuristic_successes, min(success_audit_limit, len(heuristic_successes)))
    silent_failures = 0
    for item in track(success_sample, description="Spot-checking Successes"):
        result = auditor.audit(item["record"]["doc"]["table"], item["md"])
        if not result.is_equivalent:
            silent_failures += 1
            final_failures.append({
                "record_id": item["record"]["id"],
                "failure_type": "SILENT_FAILURE",
                "audit_reasoning": result.reasoning,
                "md_output": item["md"]
            })

    # Output Results
    if final_failures:
        with open(PATHS["log"], "w") as f:
            json.dump(final_failures, f, indent=4)
        CONSOLE.print(f"\n[bold red]Logged {len(final_failures)} critical failures to {PATHS['log']}[/bold red]")

    # Summary Statistics
    total_records = len(records)
    pass_rate = (len(heuristic_successes) - silent_failures) / total_records
    
    CONSOLE.print("\n[bold green]Validation Summary[/bold green]")
    CONSOLE.print(f"Total Processed:    {total_records}")
    CONSOLE.print(f"True Pass Rate:     {pass_rate:.1%}")
    CONSOLE.print(f"Heuristic Rescues:  {audit_rescues} (False positives flagged by code, cleared by LLM)")
    CONSOLE.print(f"Silent Failures:    {silent_failures} (False negatives cleared by code, caught by LLM)")
    CONSOLE.print("\n")

if __name__ == "__main__":
    run_validation_suite()