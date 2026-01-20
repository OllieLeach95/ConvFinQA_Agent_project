from typing import Dict, Any, List

def _format_financial_value(val: Any) -> str:
    """Handles comma separators and decimal precision for financial metrics."""
    if not isinstance(val, (int, float)):
        return str(val)
    
    if isinstance(val, float):
        # Format to 2 decimals, but strip trailing zeros if they are unnecessary
        formatted = f"{val:,.2f}".rstrip('0').rstrip('.')
        return formatted
    
    return f"{val:,}"

def table_to_markdown(table_dict: Dict[str, Dict[str, Any]]) -> str:
    """
    Transforms ConvFinQA-style nested dictionaries into a Markdown table.
    Preserves row and column order based on dictionary insertion order.
    """
    if not table_dict or not isinstance(table_dict, dict):
        return ""

    columns = list(table_dict.keys())
    
    # Collect unique row labels across all columns while preserving insertion order
    row_labels: List[str] = []
    seen = set()
    for col_data in table_dict.values():
        for label in col_data:
            if label not in seen:
                seen.add(label)
                row_labels.append(label)

    if not row_labels:
        return ""

    # Build components
    header = f"| Item | {' | '.join(columns)} |"
    separator = f"| :--- | {' | '.join([':---:'] * len(columns))} |"

    rows = []
    for label in row_labels:
        # Bold the metric name for visual hierarchy
        row_cells = [f"**{label}**"]
        
        for col in columns:
            value = table_dict[col].get(label, "n/a")
            row_cells.append(_format_financial_value(value))
        
        rows.append(f"| {' | '.join(row_cells)} |")

    return "\n".join([header, separator] + rows)