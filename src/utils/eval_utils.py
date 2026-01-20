# src/utils/eval_utils.py

import math
import re

def is_nearly_equal(val1: float, val2: float, tolerance: float = 0.02) -> bool:
    """
    Performs fuzzy matching for financial values.
    1. Performs an absolute check for zeros/small numbers
    2. Performs a relative check between two numbers at a low default tolerance
    3. Performs a percentage cross check.
    """
    try:
        if abs(val1 - val2) < 0.05:
            return True
        
        if math.isclose(val1, val2, rel_tol=tolerance):
            return True
        
        if math.isclose(val1 * 100, val2, rel_tol=tolerance) or \
           math.isclose(val1, val2 * 100, rel_tol=tolerance):
            return True
    except:
        return False
    return False

def detect_symbolic_hallucination(expression: str) -> bool:
    """Identifies if the agent used illegal business terms instead of literals."""
    allowed_terms = {"ans", "abs", "round", "min", "max", "sum"}
    words = re.findall(r'[a-zA-Z]+', expression)
    for word in words:
        if word.lower() not in allowed_terms:
            return True
    return False

def calculate_scale_error(actual: float, expected: float) -> bool:
    """Identifies errors off by more than 50% (unit/scale failure)."""
    if expected == 0: return False
    ratio = abs(actual / expected)
    return ratio > 1.5 or ratio < 0.5