"""List formatter for enumeration queries."""

from typing import Any, Dict, List

from app.formatters.base import OutputFormatter, FormattedOutput
from app.search.intent.classifier import Intent
from app.search.semantic.engine import SearchResult


class ListFormatter(OutputFormatter):
    """
    Formats results as bullet or numbered lists.
    
    Supports:
    - Bullet lists (unordered)
    - Numbered lists (ordered, for how-to queries)
    - Nested lists
    """
    
    def __init__(self, numbered: bool = False):
        """
        Initialize list formatter.
        
        Args:
            numbered: Whether to use numbered list
        """
        self.numbered = numbered
    
    async def format(
        self,
        results: List[SearchResult],
        query: str,
        intent: Intent
    ) -> FormattedOutput:
        """Format results as a list."""
        if not results:
            return FormattedOutput(
                format_type="list",
                content="No items found.",
                raw_data=[]
            )
        
        # Determine if numbered based on intent
        numbered = self.numbered or intent.metadata.get("numbered", False)
        
        # Extract list items from results
        items = self._extract_list_items(results, query)
        
        # Format as markdown list
        if numbered:
            markdown = self._format_numbered_list(items)
        else:
            markdown = self._format_bullet_list(items)
        
        return FormattedOutput(
            format_type="numbered_list" if numbered else "list",
            content=markdown,
            raw_data=items,
            metadata={"item_count": len(items)}
        )
    
    def _extract_list_items(
        self,
        results: List[SearchResult],
        query: str
    ) -> List[str]:
        """Extract individual list items from results."""
        items = []
        
        for result in results:
            content = self._clean_text(result.content)
            
            # Try to split into items if content looks like a list
            if self._looks_like_list(content):
                extracted = self._parse_list_content(content)
                items.extend(extracted)
            else:
                # Use entire content as one item
                items.append(self._truncate_text(content, 200))
        
        # Deduplicate and limit
        seen = set()
        unique_items = []
        for item in items:
            if item.lower() not in seen:
                seen.add(item.lower())
                unique_items.append(item)
        
        return unique_items[:20]  # Limit to 20 items
    
    def _looks_like_list(self, content: str) -> bool:
        """Check if content appears to be a list."""
        # Check for list markers
        import re
        
        list_patterns = [
            r'^\s*[-•*]\s',  # Bullet points
            r'^\s*\d+[\.\)]\s',  # Numbered items
            r'\n\s*[-•*]\s',  # Bullets in content
            r'\n\s*\d+[\.\)]\s',  # Numbers in content
        ]
        
        for pattern in list_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True
        
        return False
    
    def _parse_list_content(self, content: str) -> List[str]:
        """Parse list items from content."""
        import re
        
        items = []
        
        # Split by common list markers
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Remove list markers
            clean_line = re.sub(r'^[-•*\d.)\s]+', '', line)
            clean_line = clean_line.strip()
            
            if clean_line and len(clean_line) > 3:  # Skip too short items
                items.append(clean_line)
        
        return items
    
    def _format_bullet_list(self, items: List[str]) -> str:
        """Format items as bullet list."""
        return "\n".join(f"- {item}" for item in items)
    
    def _format_numbered_list(self, items: List[str]) -> str:
        """Format items as numbered list."""
        return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))


class NumberedListFormatter(ListFormatter):
    """Numbered list formatter (convenience class)."""
    
    def __init__(self):
        super().__init__(numbered=True)
