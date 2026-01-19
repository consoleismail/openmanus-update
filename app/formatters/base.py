"""Base formatter and common utilities."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.search.intent.classifier import Intent
from app.search.semantic.engine import SearchResult


class FormattedOutput(BaseModel):
    """Formatted output result."""
    
    format_type: str
    content: str  # Formatted string (markdown, etc.)
    raw_data: Any = None  # Raw data for further processing
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OutputFormatter(ABC):
    """Base class for output formatters."""
    
    @abstractmethod
    async def format(
        self,
        results: List[SearchResult],
        query: str,
        intent: Intent
    ) -> FormattedOutput:
        """
        Format search results according to the intent.
        
        Args:
            results: Search results to format
            query: Original user query
            intent: Classified intent
            
        Returns:
            Formatted output
        """
        pass
    
    def _truncate_text(self, text: str, max_length: int = 200) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    def _clean_text(self, text: str) -> str:
        """Clean text for display."""
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class TextFormatter(OutputFormatter):
    """Simple text formatter."""
    
    async def format(
        self,
        results: List[SearchResult],
        query: str,
        intent: Intent
    ) -> FormattedOutput:
        """Format results as plain text."""
        if not results:
            return FormattedOutput(
                format_type="text",
                content="No results found.",
                raw_data=[]
            )
        
        # Combine content from results
        parts = []
        for i, result in enumerate(results[:5], 1):
            content = self._clean_text(result.content)
            content = self._truncate_text(content, 500)
            parts.append(content)
        
        return FormattedOutput(
            format_type="text",
            content="\n\n".join(parts),
            raw_data=[r.content for r in results],
            metadata={"result_count": len(results)}
        )
