"""JSON formatter for data extraction queries."""

import json
from typing import Any, Dict, List

from app.formatters.base import OutputFormatter, FormattedOutput
from app.search.intent.classifier import Intent
from app.search.semantic.engine import SearchResult


class JSONFormatter(OutputFormatter):
    """
    Formats results as structured JSON for data extraction queries.
    
    Extracts structured data from search results and formats
    as valid JSON for API consumption or further processing.
    """
    
    async def format(
        self,
        results: List[SearchResult],
        query: str,
        intent: Intent
    ) -> FormattedOutput:
        """Format results as JSON."""
        if not results:
            return FormattedOutput(
                format_type="json",
                content="[]",
                raw_data=[]
            )
        
        # Extract structured data from results
        extracted_data = self._extract_structured_data(results, query, intent)
        
        # Format as pretty JSON
        json_content = json.dumps(extracted_data, indent=2, ensure_ascii=False)
        
        return FormattedOutput(
            format_type="json",
            content=f"```json\n{json_content}\n```",
            raw_data=extracted_data,
            metadata={"item_count": len(extracted_data)}
        )
    
    def _extract_structured_data(
        self,
        results: List[SearchResult],
        query: str,
        intent: Intent
    ) -> List[Dict[str, Any]]:
        """Extract structured data from results."""
        data = []
        
        for result in results:
            item = {
                "id": result.id,
                "content": self._clean_text(result.content),
                "score": round(result.score, 4),
            }
            
            # Add metadata
            if result.metadata:
                for key, value in result.metadata.items():
                    if key not in item:
                        item[key] = value
            
            # Try to extract specific fields from content
            extracted_fields = self._extract_fields(result.content, intent.entities)
            item.update(extracted_fields)
            
            data.append(item)
        
        return data
    
    def _extract_fields(
        self,
        content: str,
        target_fields: List[str]
    ) -> Dict[str, Any]:
        """Extract specific fields from content."""
        import re
        
        fields = {}
        
        for field in target_fields:
            # Try to find field:value patterns
            patterns = [
                rf"{re.escape(field)}[:\s]+([^,.\n]+)",
                rf"'{re.escape(field)}'[:\s]+([^,.\n]+)",
                rf'"{re.escape(field)}"[:\s]+([^,.\n]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Try to parse as number if applicable
                    value = self._parse_value(value)
                    fields[field.lower().replace(' ', '_')] = value
                    break
        
        return fields
    
    def _parse_value(self, value: str) -> Any:
        """Parse a string value to appropriate type."""
        value = value.strip().strip('"\'')
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try boolean
        if value.lower() in ('true', 'yes'):
            return True
        if value.lower() in ('false', 'no'):
            return False
        
        # Return as string
        return value
