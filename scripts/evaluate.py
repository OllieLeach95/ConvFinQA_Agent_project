# scripts/evaluate.py

import json
import random
import logging
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.progress import track

from src.agent.orchestrator import ConvFinQAManager
from src.models.schemas import StudyCondition, TurnResult
from src.utils.eval_utils import is_nearly_equal, detect_symbolic_hallucination, calculate_scale_error

# --- Constants ---
CONSOLE = Console()
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_PATH = DATA_DIR / "convfinqa_dataset.json"
RANDOM_SEED = 42
SAMPLE_SIZE = 15

STUDY_MATRIX = [
    {"id": StudyCondition.JSON_BASELINE_MINI, "name": "1. JSON Baseline (Mini)"},
    {"id": StudyCondition.MD_BASELINE_MINI, "name": "2. MD Baseline (Mini)"},
    {"id": StudyCondition.JSON_BASELINE_MED, "name": "3. JSON Baseline (Med)"},
    {"id": StudyCondition.MD_BASELINE_MED, "name": "4. MD Baseline (Med)"},
    {"id": StudyCondition.MD_BASELINE_HIGH, "name": "5. MD Baseline (High)"},
    {"id": StudyCondition.MODULAR_MINI, "name": "6. Modular (Mini)"},
    {"id": StudyCondition.MODULAR_MED, "name": "7. Modular (Med)"},
    {"id": StudyCondition.MODULAR_HIGH, "name": "8. Modular (High)"},
    {"id": StudyCondition.REFLECT_MINI, "name": "9. Reflect (Mini)"},
    {"id": StudyCondition.REFLECT_MED, "name": "10. Reflect (Med)"},
    {"id": StudyCondition.REFLECT_HIGH, "name": "11. Reflect (High)"},
]

# For initial round of prompt engineering before running the full evaluation
# STUDY_MATRIX = [
#     {"id": StudyCondition.MD_BASELINE_MINI, "name": "2. MD Baseline (Mini)"},
#     {"id": StudyCondition.REFLECT_HIGH, "name": "10. Reflect (High)"},
# ]

logging.basicConfig(
    level=logging.INFO, 
    filename=DATA_DIR / "evaluation.log",
    filemode='w'
)

logger = logging.getLogger(__name__)

@dataclass
class TurnStats:
    correct: int = 0
    total: int = 0

    @property
    def accuracy(self) -> float:
        return (self.correct / self.total * 100) if self.total > 0 else 0

@dataclass
class ConditionMetrics:
    total_turns: int = 0
    correct: int = 0
    hallucinations: int = 0
    scale_errors: int = 0
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    per_turn_breakdown: Dict[int, TurnStats] = field(default_factory=dict)

    def update(self, turn_idx: int, is_correct: bool, is_hallucinated: bool, 
               is_scale: bool, internal_review_failed: bool):
        self.total_turns += 1
        if is_correct: self.correct += 1
        if is_hallucinated: self.hallucinations += 1
        if is_scale: self.scale_errors += 1
        
        # FIXED LOGIC: Attempt is counted if the agent flagged itself.
        if internal_review_failed:
            self.recovery_attempts += 1
            if is_correct:
                self.successful_recoveries += 1
        
        if turn_idx not in self.per_turn_breakdown:
            self.per_turn_breakdown[turn_idx] = TurnStats()
        self.per_turn_breakdown[turn_idx].total += 1
        if is_correct: self.per_turn_breakdown[turn_idx].correct += 1

    @property
    def final_accuracy(self) -> float:
        return (self.correct / self.total_turns * 100) if self.total_turns > 0 else 0
    
    @property
    def recovery_rate(self) -> float:
        return (self.successful_recoveries / self.recovery_attempts * 100) if self.recovery_attempts > 0 else 0

class EvaluationReporter:
    @staticmethod
    def print_comparative_table(all_results: List[Dict]):
        """Restores the side-by-side comparison from the original script."""
        table = Table(title="Ablation Study: Comparative Performance", header_style="bold magenta")
        table.add_column("Condition", style="cyan", no_wrap=True)
        table.add_column("Accuracy", justify="right", style="green")
        table.add_column("Hallucinations", justify="right", style="red")
        table.add_column("Scale Errors", justify="right", style="yellow")
        table.add_column("Recovery Rate", justify="right", style="blue")

        for res in all_results:
            m = res["metrics"]
            table.add_row(
                res["metadata"]["name"],
                f"{res['accuracy']}%",
                str(m.hallucinations),
                str(m.scale_errors),
                f"{m.recovery_rate:.1f}%"
            )
        CONSOLE.print("\n")
        CONSOLE.print(table)

    @staticmethod
    def save_results(path: Path, metadata: Dict, metrics: ConditionMetrics, results: List[Dict]):
        output = {
            "metadata": metadata,
            "accuracy": round(metrics.final_accuracy, 2),
            "metrics": {
                "total_turns": metrics.total_turns,
                "correct": metrics.correct,
                "hallucinations": metrics.hallucinations,
                "scale_errors": metrics.scale_errors,
                "recovery_attempts": metrics.recovery_attempts,
                "successful_recoveries": metrics.successful_recoveries
            },
            "detailed_results": results
        }
        with open(path, "w") as f:
            json.dump(output, f, indent=4)

class EvaluationRunner:
    def __init__(self, condition_meta: Dict):
        self.meta = condition_meta
        self.manager = ConvFinQAManager(condition=condition_meta["id"])
        self.metrics = ConditionMetrics()
        self.detailed_results = []

    def _process_turn(self, record_id: str, turn_idx: int, turn: TurnResult, expected: float):
        actual = turn.raw_math_output
        is_correct = is_nearly_equal(actual, expected)
        is_hallucinated = detect_symbolic_hallucination(turn.final_expression)
        is_scale = calculate_scale_error(actual, expected) if not is_correct else False
        
        # Recovery happened if review flagged it as invalid
        review_flagged_error = True if (turn.review and not turn.review.is_valid) else False

        self.metrics.update(turn_idx, is_correct, is_hallucinated, is_scale, review_flagged_error)
        
        self.detailed_results.append({
            "record_id": record_id,
            "turn_index": turn_idx,
            "is_correct": is_correct,
            "ground_truth": expected,
            "agent_output": actual,
            "metrics": {"was_recovered": (review_flagged_error and is_correct)}
        })

    def run(self, data: List[Dict]) -> ConditionMetrics:
        random.seed(RANDOM_SEED)
        samples = random.sample(data, min(SAMPLE_SIZE, len(data)))
        
        CONSOLE.print(f"\n[bold cyan]🧪 Executing: {self.meta['name']}[/bold cyan]")
        
        for record in track(samples, description=f"Condition {int(self.meta['id'])}"):
            try:
                state = self.manager.process_record(record)
                ground_truth = record["dialogue"]["executed_answers"]
                for i, turn in enumerate(state.history):
                    if i < len(ground_truth):
                        self._process_turn(record["id"], i, turn, ground_truth[i])
            except Exception as e:
                logger.error(f"Error in record {record.get('id')}: {e}")
        return self.metrics

def main():
    if not DATA_PATH.exists():
        CONSOLE.print(f"[bold red]Error: Dataset not found at {DATA_PATH}[/bold red]")
        return

    with open(DATA_PATH, "r") as f:
        all_data = json.load(f).get("train", [])

    final_comparison_data = []

    for config in STUDY_MATRIX:
        runner = EvaluationRunner(config)
        metrics = runner.run(all_data)
        
        # Save results to list for the final table
        final_comparison_data.append({
            "metadata": config,
            "accuracy": round(metrics.final_accuracy, 2),
            "metrics": metrics
        })
        
        # Save individual JSON file
        EvaluationReporter.save_results(
            DATA_DIR / f"eval_results_cond_{int(config['id'])}.json",
            config, metrics, runner.detailed_results
        )

    # Final report
    EvaluationReporter.print_comparative_table(final_comparison_data)
    CONSOLE.print("\n[bold green]✅ Study Complete. Data analysis files generated in /data.[/bold green]")

if __name__ == "__main__":
    main()