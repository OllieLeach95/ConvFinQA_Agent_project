import re
from typing import Any
from src.utils.parser import table_to_markdown
from src.models.schemas import FinancialContext

class ContextBuilder:
    """Transforms raw dataset records into grounded financial contexts."""
    
    @staticmethod
    def normalize_text(text: str | None) -> str:
        """
        Collapses excessive whitespace while preserving the 
        specific punctuation-spacing artifacts found in the dataset.
        """
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()

    @classmethod
    def build(cls, record: dict[str, Any]) -> FinancialContext:
        """Orchestrates the conversion of a raw record into a FinancialContext schema."""
        doc = record.get("doc", {})
        raw_table = doc.get("table", {})
        
        return FinancialContext(
            record_id=record.get("id", "unknown"),
            pre_text=cls.normalize_text(doc.get("pre_text")),
            post_text=cls.normalize_text(doc.get("post_text")),
            markdown_table=table_to_markdown(raw_table),
            raw_table=raw_table
        )