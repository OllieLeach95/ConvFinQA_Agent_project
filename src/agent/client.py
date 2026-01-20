import os
from typing import Type, TypeVar
from pydantic import BaseModel
from openai import OpenAI

T = TypeVar("T", bound=BaseModel)

class ReasoningClient:
    """
    Client for GPT-5.2 family models using the Responses API.
    Identifies and extracts structured outputs from the 'output_parsed' attribute.
    """
    
    def __init__(self, model: str = "gpt-5-mini-2025-08-07"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
            
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def get_structured_response(
        self, 
        instructions: str, 
        input_text: str, 
        response_model: Type[T],
        model: str | None = None,
        effort: str = "medium"
    ) -> T:
        """
        Executes a request and returns the validated Pydantic model.
        """
        
        target_model = model or self.model
        
        kwargs = {
            "model": target_model,
            "instructions": instructions,
            "input": input_text,
            "text_format": response_model,
        }

        # gpt-5-mini doesn't support the reasoning effort parameter
        if "mini" not in target_model.lower():
            kwargs["reasoning"] = {"effort": effort}

        response = self.client.responses.parse(**kwargs)
        parsed = response.output_parsed


        # # --- Comment in for prompt engineering/debugging ---
        # if parsed:
        #     print(f"\n[RAW DEBUG - {target_model}]")
        #     # AnalysisPlan uses 'intent', AnalyticStep uses 'thought'
        #     reasoning = getattr(parsed, 'thought', getattr(parsed, 'intent', 'N/A'))
        #     print(f"Reasoning: {reasoning}")
            
        #     if hasattr(parsed, 'python_expression'):
        #         print(f"Expression: {parsed.python_expression}")
            
        #     if hasattr(parsed, 'execution_steps'):
        #         print(f"Steps: {parsed.execution_steps}")
        # # --------------------------------------
        
        return parsed