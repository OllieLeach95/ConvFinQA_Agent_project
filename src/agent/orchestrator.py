import logging
from pathlib import Path
from typing import Any

from src.agent.client import ReasoningClient
from src.agent.context_builder import ContextBuilder
from src.agent.tools import MathTool
from src.models.schemas import (
    ConversationState, TurnResult, AnalyticStep, 
    AnalysisPlan, ReviewResult, StudyCondition
)

logger = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).parent / "prompts"

class ConvFinQAManager:
    def __init__(self, condition: StudyCondition):
        self.condition = condition
        self.client = ReasoningClient()
        self.builder = ContextBuilder()
        self.math_tool = MathTool()
        self.prompts = self._load_all_prompts()
        
        self._config_matrix = {
            StudyCondition.JSON_BASELINE_MINI: ("gpt-5-mini", "none"),
            StudyCondition.MD_BASELINE_MINI:   ("gpt-5-mini", "none"),
            StudyCondition.JSON_BASELINE_MED:  ("gpt-5.2", "medium"),
            StudyCondition.MD_BASELINE_MED:    ("gpt-5.2", "medium"),
            StudyCondition.MD_BASELINE_HIGH:   ("gpt-5.2", "high"),
            StudyCondition.MODULAR_MINI:       ("gpt-5-mini", "none"),
            StudyCondition.MODULAR_MED:        ("gpt-5.2", "medium"),
            StudyCondition.MODULAR_HIGH:        ("gpt-5.2", "high"),
            StudyCondition.REFLECT_MINI:       ("gpt-5-mini", "none"),
            StudyCondition.REFLECT_MED:        ("gpt-5.2", "medium"),
            StudyCondition.REFLECT_HIGH:       ("gpt-5.2", "high"),
        }

    def _load_all_prompts(self) -> dict[str, str]:
        files = {
            "baseline": "baseline_analyst_system_prompt.xml",
            "planner": "planner_system_prompt.xml",
            "agentic_analyst": "agentic_analyst_system_prompt.xml",
            "reviewer": "reviewer_system_prompt.xml"
        }
        loaded = {}
        for key, filename in files.items():
            path = PROMPT_DIR / filename
            if not path.exists():
                raise FileNotFoundError(f"Missing prompt: {path}")
            loaded[key] = path.read_text(encoding="utf-8")
        return loaded

    def process_record(self, record: dict[str, Any]) -> ConversationState:
        context = self.builder.build(record)
        state = ConversationState(context=context, condition=self.condition)
        questions = record.get("dialogue", {}).get("conv_questions", [])
        
        for i, question in enumerate(questions):
            logger.info(f"Turn {i} | Record {context.record_id} | Cond {self.condition.value}")
            turn_data = self._execute_pipeline(state, question)
            turn_result = self._create_turn_result(state, question, i, turn_data)
            state.history.append(turn_result)
            
        return state

    def _create_turn_result(self, state: ConversationState, question: str, 
                            index: int, turn_data: dict[str, Any]) -> TurnResult:
        try:
            raw_result = self.math_tool.calculate(
                turn_data["final_expression"], 
                state.get_ans_map()
            )
            response = self.math_tool.format_final_response(
                raw_result, 
                turn_data["is_percentage"]
            )
        except Exception as e:
            logger.error(f"Math error on turn {index}: {e}")
            raw_result, response = 0.0, f"Execution Error: {str(e)}"

        return TurnResult(
            turn_index=index,
            question=question,
            plan=turn_data.get("plan"),
            analyst_output=turn_data["analyst_output"],
            review=turn_data.get("review"),
            final_expression=turn_data["final_expression"],
            raw_math_output=raw_result,
            conversational_response=response
        )

    def _execute_pipeline(self, state: ConversationState, question: str) -> dict[str, Any]:
        model, effort = self._config_matrix[self.condition]
        payload = self._build_payload(state, question)

        baselines = [
            StudyCondition.JSON_BASELINE_MINI, StudyCondition.MD_BASELINE_MINI,
            StudyCondition.JSON_BASELINE_MED, StudyCondition.MD_BASELINE_MED,
            StudyCondition.MD_BASELINE_HIGH
        ]

        if self.condition in baselines:
            return self._run_baseline_flow(payload, model, effort)
        return self._run_agentic_flow(payload, model, effort)

    def _run_baseline_flow(self, payload: str, model: str, effort: str) -> dict[str, Any]:
        output = self.client.get_structured_response(
            self.prompts["baseline"], payload, AnalyticStep, model=model, effort=effort
        )
        
        # Fallback for API/Parsing failures
        if not output:
            output = AnalyticStep(python_expression="0", is_percentage=False, thought="API Failure")

        return {
            "analyst_output": output,
            "final_expression": output.python_expression,
            "is_percentage": output.is_percentage
        }

    def _run_agentic_flow(self, payload: str, model: str, effort: str) -> dict[str, Any]:
        # 1. Planning State
        plan = self.client.get_structured_response(
            self.prompts["planner"], payload, AnalysisPlan, model=model, effort=effort
        )
        if not plan:
            plan = AnalysisPlan(intent="Error", data_points=[], execution_steps=[], is_percentage_required=False)

        # 2. Analyst State (Reasoning & Code Generation)
        analyst_payload = f"{payload}\n<plan>{plan.model_dump_json()}</plan>"
        output = self.client.get_structured_response(
            self.prompts["agentic_analyst"], analyst_payload, AnalyticStep, model=model, effort=effort
        )
        if not output:
            output = AnalyticStep(python_expression="0", is_percentage=False, thought="API Failure")
        
        final_expr = output.python_expression
        review = None

        # 3. Auditor State (Reflection/Review)
        if self.condition >= StudyCondition.REFLECT_MINI:
            review_payload = f"{payload}\n<proposed_code>{output.python_expression}</proposed_code>"
            review = self.client.get_structured_response(
                self.prompts["reviewer"], review_payload, ReviewResult, model=model, effort=effort
            )
            
            # 4. Self-Correction Loop (if Auditor flags an error)
            if review and not review.is_valid:
                logger.info(f"Self-correction triggered via {model}")
                retry_payload = f"{analyst_payload}\n<feedback>{review.audit_commentary}</feedback>"
                retry_output = self.client.get_structured_response(
                    self.prompts["agentic_analyst"], retry_payload, AnalyticStep, model=model, effort=effort
                )
                if retry_output:
                    output = retry_output
                    final_expr = output.python_expression

        return {
            "plan": plan,
            "analyst_output": output,
            "review": review,
            "final_expression": final_expr,
            "is_percentage": output.is_percentage
        }

    def _build_payload(self, state: ConversationState, question: str) -> str:
        json_modes = [StudyCondition.JSON_BASELINE_MINI, StudyCondition.JSON_BASELINE_MED]
        table = state.context.raw_table if self.condition in json_modes else state.context.markdown_table
        
        return (
            f"<context>\n"
            f"<metadata>ID: {state.context.record_id}</metadata>\n"
            f"<pre_text>{state.context.pre_text}</pre_text>\n"
            f"<table_data>\n{table}\n</table_data>\n"
            f"<post_text>{state.context.post_text}</post_text>\n"
            f"<history>{state.get_prompt_history()}</history>\n"
            f"</context>\n"
            f"<current_question>{question}</current_question>"
        )