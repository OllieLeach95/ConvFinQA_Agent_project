import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MathTool:
    """Deterministic math engine for evaluating and formatting financial expressions."""

    @staticmethod
    def calculate(expression: str, reference_values: Dict[str, float]) -> float:
        """Evaluates a Python math expression within a restricted namespace."""
        safe_namespace = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            **reference_values
        }

        try:
            result = eval(expression, {"__builtins__": None}, safe_namespace)
            return float(result)
        except (SyntaxError, NameError) as e:
            logger.error(f"Agent generated invalid Python: {expression} | Error: {e}")
            raise ValueError(f"Invalid expression syntax: {e}")
        except ZeroDivisionError:
            logger.warning(f"Division by zero in expression: {expression}")
            return 0.0
        except Exception as e:
            logger.error(f"Math evaluation error: {expression} | Error: {e}")
            raise ValueError(f"Calculation failed: {e}")

    @staticmethod
    def format_final_response(value: float, is_percentage: bool) -> str:
        """Formats raw floats into accounting-standard string representations."""
        if is_percentage:
            return f"{value * 100:.1f}%"
        
        if value.is_integer():
            return f"{int(value):,}"
        
        return f"{value:,.2f}".rstrip('0').rstrip('.')