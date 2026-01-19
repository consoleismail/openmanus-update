"""Table formatter for comparison queries."""

from typing import Any, Dict, List, Optional

from app.formatters.base import OutputFormatter, FormattedOutput
from app.search.intent.classifier import Intent
from app.search.semantic.engine import SearchResult
from app.logger import logger


class TableFormatter(OutputFormatter):
    """
    Formats results as markdown tables for comparison queries.
    
    Automatically extracts entities and attributes from the query
    and search results to build a structured comparison table.
    """
    
    async def format(
        self,
        results: List[SearchResult],
        query: str,
        intent: Intent
    ) -> FormattedOutput:
        """Format results as a comparison table."""
        if not results:
            return FormattedOutput(
                format_type="table",
                content="No comparison data found.",
                raw_data=[]
            )
        
        # Extract entities from intent
        entities = intent.entities or self._extract_entities_from_query(query)
        
        # Determine comparison attributes
        attributes = intent.attributes or self._determine_attributes(query, results)
        
        if not entities:
            # Fall back to listing results as rows
            return self._format_as_simple_table(results)
        
        # Build comparison matrix
        table_data = self._build_comparison_matrix(entities, attributes, results)
        
        # Generate markdown table
        markdown = self._to_markdown_table(entities, attributes, table_data)
        
        return FormattedOutput(
            format_type="table",
            content=markdown,
            raw_data=table_data,
            metadata={
                "entities": entities,
                "attributes": attributes,
                "row_count": len(entities)
            }
        )
    
    def _extract_entities_from_query(self, query: str) -> List[str]:
        """Extract entities to compare from the query."""
        import re
        
        patterns = [
            r"compare\s+(.+?)\s+(?:and|vs|versus|with)\s+(.+?)(?:\s|$|\.)",
            r"(.+?)\s+vs\.?\s+(.+?)(?:\s|$|\.)",
            r"difference(?:s)?\s+between\s+(.+?)\s+and\s+(.+?)(?:\s|$|\.)",
            r"compare\s+(?:the\s+)?(.+?),\s+(.+?),?\s+and\s+(.+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                entities = [g.strip() for g in match.groups() if g]
                # Clean up entities
                entities = [e.strip().rstrip('.') for e in entities]
                return entities
        
        return []
    
    def _determine_attributes(
        self,
        query: str,
        results: List[SearchResult]
    ) -> List[str]:
        """Determine comparison attributes from query and results."""
        # Try to extract from query
        import re
        
        # Common attribute patterns
        attribute_patterns = [
            r"compare\s+(?:the\s+)?(.+?)\s+(?:and|of)",
            r"in\s+terms\s+of\s+(.+)",
            r"by\s+(.+?)(?:\s|$|,)",
        ]
        
        extracted = []
        for pattern in attribute_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                attrs = match.group(1).split(' and ')
                extracted.extend([a.strip() for a in attrs])
        
        if extracted:
            return extracted
        
        # Default common comparison attributes
        default_attrs = ["Price", "Features", "Rating", "Pros", "Cons"]
        
        # Check which attributes are mentioned in results
        relevant_attrs = []
        for attr in default_attrs:
            for result in results:
                if attr.lower() in result.content.lower():
                    relevant_attrs.append(attr)
                    break
        
        return relevant_attrs or ["Description"]
    
    def _build_comparison_matrix(
        self,
        entities: List[str],
        attributes: List[str],
        results: List[SearchResult]
    ) -> Dict[str, Dict[str, str]]:
        """Build a matrix of entity -> attribute -> value."""
        matrix = {entity: {} for entity in entities}
        
        for entity in entities:
            for attr in attributes:
                # Find value in results
                value = self._extract_value(entity, attr, results)
                matrix[entity][attr] = value
        
        return matrix
    
    def _extract_value(
        self,
        entity: str,
        attribute: str,
        results: List[SearchResult]
    ) -> str:
        """Extract the value of an attribute for an entity from results."""
        entity_lower = entity.lower()
        attr_lower = attribute.lower()
        
        for result in results:
            content = result.content.lower()
            
            # Check if this result is about the entity
            if entity_lower in content:
                # Try to find attribute value near entity mention
                import re
                
                # Pattern: entity ... attribute: value
                pattern = rf"{re.escape(entity_lower)}.{{0,100}}{re.escape(attr_lower)}[:\s]+([^.]+)"
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1).strip()[:100]
                
                # Pattern: attribute: value (in entity context)
                pattern = rf"{re.escape(attr_lower)}[:\s]+([^.]+)"
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1).strip()[:100]
        
        return "-"  # Not found
    
    def _to_markdown_table(
        self,
        entities: List[str],
        attributes: List[str],
        data: Dict[str, Dict[str, str]]
    ) -> str:
        """Convert data matrix to markdown table."""
        # Header row
        header = "| Entity | " + " | ".join(attributes) + " |"
        separator = "|" + "|".join(["---"] * (len(attributes) + 1)) + "|"
        
        # Data rows
        rows = []
        for entity in entities:
            values = [data[entity].get(attr, "-") for attr in attributes]
            row = f"| **{entity}** | " + " | ".join(values) + " |"
            rows.append(row)
        
        return "\n".join([header, separator] + rows)
    
    def _format_as_simple_table(self, results: List[SearchResult]) -> FormattedOutput:
        """Format results as a simple table when entities aren't clear."""
        header = "| # | Content | Score |"
        separator = "|---|---|---|"
        
        rows = []
        for i, result in enumerate(results[:10], 1):
            content = self._truncate_text(self._clean_text(result.content), 100)
            score = f"{result.score:.2f}"
            rows.append(f"| {i} | {content} | {score} |")
        
        markdown = "\n".join([header, separator] + rows)
        
        return FormattedOutput(
            format_type="table",
            content=markdown,
            raw_data=[{"content": r.content, "score": r.score} for r in results]
        )
