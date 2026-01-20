from enum import IntEnum
from typing import Any
from pydantic import BaseModel, Field

class StudyCondition(IntEnum):
    """
    Experimental matrix for the ConvFinQA Ablation Study.
    Toggles between Data Format (JSON/MD), Intelligence Tier (Mini/5.2), 
    and Architectural Tier (Baseline/Modular/Reflective).
    """
    # --- Format Baselines (Mini Tier) ---
    JSON_BASELINE_MINI = 1   # Logic: Mini + JSON. Tests raw parsing of small models.
    MD_BASELINE_MINI = 2     # Logic: Mini + Markdown. Tests the "Markdown Tax" vs JSON.

    # --- Format Baselines (Medium/High Tier) ---
    JSON_BASELINE_MED = 3    # Logic: 5.2 + JSON. Safety check for the high-tier model.
    MD_BASELINE_MED = 4      # Logic: 5.2 + Markdown. Baseline for the 5.2 model.
    MD_BASELINE_HIGH = 5     # Logic: 5.2 + High Effort. The "Single-Pass Ceiling".

    # --- Architectural Ablations (Medium/High Tier) ---
    MODULAR_MINI = 6         # Logic: Mini + Plan -> Code. Can planning save a weak model?
    MODULAR_MED = 7          # Logic: 5.2 + Plan -> Code. Does modularity help smart models?
    MODULAR_HIGH = 8          # Logic: 5.2 + Plan -> Code + High effort
    
    # --- Agentic Reflection Loops ---
    REFLECT_MINI = 9         # Logic: Mini + Full Loop. Can small models self-correct?
    REFLECT_MED = 10          # Logic: 5.2 + Full Loop.
    REFLECT_HIGH = 11        # Logic: 5.2 + Full Loop + High Effort

class TableEquivalence(BaseModel):
    is_equivalent: bool = Field(description="Semantic parity between JSON and Markdown")
    data_loss_found: bool = Field(description="Detection of missing numeric facts or headers")
    reasoning: str = Field(description="Detailed explanation of discrepancies")

class FinancialContext(BaseModel):
    record_id: str
    pre_text: str
    post_text: str
    markdown_table: str
    raw_table: dict[str, Any]

class DataPoint(BaseModel):
    label: str = Field(description="Variable name, e.g., rev_2004")
    source: str = Field(description="'table' or 'history'")
    coordinate: str = Field(description="Row/Col key or ans_N index")
    value: float

class AnalysisPlan(BaseModel):
    intent: str = Field(description="Summary of the user's information need")
    data_points: list[DataPoint] = Field(description="Required numeric inputs")
    execution_steps: list[str] = Field(description="Logical sequence of operations")
    is_percentage_required: bool

class AnalyticStep(BaseModel):
    """
    In Baselines (1-3), this is the direct result of the system prompt.
    In Agentic modes (4-7), this follows the AnalysisPlan to generate the final code.
    """
    thought: str | None = Field(None, description="Internal chain-of-thought trace")
    mapping_verification: str | None = Field(None, description="Plan-to-code alignment check")
    python_expression: str = Field(description="Single-line Python math expression")
    is_percentage: bool
    unit_context: str | None = None

class ReviewResult(BaseModel):
    is_valid: bool = Field(description="Logical correctness check")
    identified_errors: list[str] = Field(default_factory=list)
    audit_commentary: str
    fixed_expression: str | None = None

class TurnResult(BaseModel):
    turn_index: int
    question: str
    
    plan: AnalysisPlan | None = None
    analyst_output: AnalyticStep
    review: ReviewResult | None = None
    
    final_expression: str
    raw_math_output: float
    conversational_response: str
    
    ground_truth: float | None = None
    is_correct: bool | None = None

class ConversationState(BaseModel):
    context: FinancialContext
    condition: StudyCondition
    history: list[TurnResult] = []

    def get_ans_map(self) -> dict[str, float]:
        """Maps turn history to ans_N variables for tool execution."""
        return {f"ans_{i}": turn.raw_math_output for i, turn in enumerate(self.history)}

    def get_prompt_history(self) -> str:
        """Serializes history for inclusion in system prompts."""
        if not self.history:
            return "No previous interaction history."
        
        output = []
        for turn in self.history:
            output.append(
                f"Question: {turn.question}\n"
                f"Answer: {turn.conversational_response} (Numeric: {turn.raw_math_output})"
            )
        return "\n---\n".join(output)