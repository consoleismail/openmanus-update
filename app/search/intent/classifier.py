"""Intent classifier for determining user query intent and output format."""

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.logger import logger


class IntentType(str, Enum):
    """Types of user intents."""
    
    COMPARISON = "comparison"
    LIST = "list"
    FACT = "fact"
    HOW_TO = "how_to"
    DEFINITION = "definition"
    DATA_EXTRACTION = "data_extraction"
    ANALYSIS = "analysis"
    SUMMARY = "summary"
    GENERAL = "general"


class OutputFormat(str, Enum):
    """Output format types."""
    
    TABLE = "table"
    LIST = "list"
    NUMBERED_LIST = "numbered_list"
    JSON = "json"
    TEXT = "text"
    STRUCTURED = "structured"


class Intent(BaseModel):
    """Classified intent of a user query."""
    
    intent_type: IntentType
    output_format: OutputFormat
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Extracted entities
    entities: List[str] = Field(default_factory=list)
    attributes: List[str] = Field(default_factory=list)
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IntentPattern(BaseModel):
    """Pattern for intent recognition."""
    
    intent_type: IntentType
    output_format: OutputFormat
    patterns: List[str]
    priority: int = 0


# Pre-defined intent patterns
INTENT_PATTERNS = [
    IntentPattern(
        intent_type=IntentType.COMPARISON,
        output_format=OutputFormat.TABLE,
        patterns=[
            r"compare\s+(.+?)\s+(?:and|vs|versus|with)\s+(.+)",
            r"difference(?:s)?\s+between\s+(.+?)\s+and\s+(.+)",
            r"(.+?)\s+vs\.?\s+(.+)",
            r"which\s+is\s+better[,:]?\s+(.+?)\s+or\s+(.+)",
            r"pros\s+and\s+cons\s+of\s+(.+)",
            r"compare\s+the\s+(.+)",
        ],
        priority=10
    ),
    IntentPattern(
        intent_type=IntentType.LIST,
        output_format=OutputFormat.LIST,
        patterns=[
            r"list\s+(?:of\s+)?(?:the\s+)?(?:top\s+)?(\d+)?\s*(.+)",
            r"(?:top|best|worst)\s+(\d+)\s+(.+)",
            r"(?:give|show|tell)\s+me\s+(?:some|a\s+few)\s+(.+)",
            r"examples?\s+of\s+(.+)",
            r"what\s+are\s+(?:some|the)\s+(.+)",
            r"types?\s+of\s+(.+)",
        ],
        priority=8
    ),
    IntentPattern(
        intent_type=IntentType.HOW_TO,
        output_format=OutputFormat.NUMBERED_LIST,
        patterns=[
            r"how\s+(?:do\s+I|to|can\s+I)\s+(.+)",
            r"steps?\s+(?:to|for)\s+(.+)",
            r"guide\s+(?:to|for|on)\s+(.+)",
            r"tutorial\s+(?:on|for)\s+(.+)",
            r"instructions?\s+(?:for|to)\s+(.+)",
            r"process\s+(?:of|for)\s+(.+)",
        ],
        priority=9
    ),
    IntentPattern(
        intent_type=IntentType.DEFINITION,
        output_format=OutputFormat.TEXT,
        patterns=[
            r"what\s+is\s+(?:a\s+|an\s+|the\s+)?(.+)",
            r"define\s+(.+)",
            r"meaning\s+of\s+(.+)",
            r"explain\s+(?:what\s+)?(.+?)\s+(?:is|means)",
        ],
        priority=6
    ),
    IntentPattern(
        intent_type=IntentType.FACT,
        output_format=OutputFormat.TEXT,
        patterns=[
            r"who\s+(?:is|was|are)\s+(.+)",
            r"when\s+(?:did|was|is)\s+(.+)",
            r"where\s+(?:is|was|are)\s+(.+)",
            r"how\s+(?:many|much)\s+(.+)",
        ],
        priority=7
    ),
    IntentPattern(
        intent_type=IntentType.DATA_EXTRACTION,
        output_format=OutputFormat.JSON,
        patterns=[
            r"extract\s+(?:the\s+)?(.+?)\s+from\s+(.+)",
            r"get\s+(?:all\s+)?(?:the\s+)?(.+?)\s+from\s+(.+)",
            r"find\s+(?:all\s+)?(?:the\s+)?(.+?)\s+in\s+(.+)",
            r"parse\s+(?:the\s+)?(.+)",
            r"export\s+(.+)",
        ],
        priority=9
    ),
    IntentPattern(
        intent_type=IntentType.ANALYSIS,
        output_format=OutputFormat.STRUCTURED,
        patterns=[
            r"analyze\s+(.+)",
            r"analysis\s+of\s+(.+)",
            r"break\s*down\s+(.+)",
            r"evaluate\s+(.+)",
        ],
        priority=7
    ),
    IntentPattern(
        intent_type=IntentType.SUMMARY,
        output_format=OutputFormat.TEXT,
        patterns=[
            r"summarize\s+(.+)",
            r"summary\s+of\s+(.+)",
            r"brief(?:ly)?\s+(?:describe|explain)\s+(.+)",
            r"overview\s+of\s+(.+)",
            r"tldr\s+(.+)",
        ],
        priority=7
    ),
]


class IntentClassifier:
    """
    Classifies user query intent for structured output generation.
    
    Uses pattern matching for high-confidence classification,
    with optional LLM fallback for ambiguous cases.
    """
    
    def __init__(self, use_llm_fallback: bool = False, llm: Any = None):
        """
        Initialize the intent classifier.
        
        Args:
            use_llm_fallback: Whether to use LLM for ambiguous cases
            llm: LLM instance for fallback classification
        """
        self.patterns = sorted(INTENT_PATTERNS, key=lambda p: -p.priority)
        self.use_llm_fallback = use_llm_fallback
        self.llm = llm
        
        # Compile regex patterns
        self._compiled_patterns = [
            (p, [re.compile(pattern, re.IGNORECASE) for pattern in p.patterns])
            for p in self.patterns
        ]
    
    async def classify(self, query: str) -> Intent:
        """
        Classify the intent of a user query.
        
        Args:
            query: User query text
            
        Returns:
            Classified Intent object
        """
        # Try pattern matching first
        intent = self._pattern_match(query)
        
        if intent and intent.confidence >= 0.8:
            return intent
        
        # Try LLM fallback if enabled
        if self.use_llm_fallback and self.llm:
            try:
                llm_intent = await self._llm_classify(query)
                if llm_intent.confidence > (intent.confidence if intent else 0):
                    return llm_intent
            except Exception as e:
                logger.warning(f"LLM intent classification failed: {e}")
        
        # Return pattern match result or default
        return intent or Intent(
            intent_type=IntentType.GENERAL,
            output_format=OutputFormat.TEXT,
            confidence=0.5
        )
    
    def _pattern_match(self, query: str) -> Optional[Intent]:
        """Match query against intent patterns."""
        query = query.strip()
        
        for pattern_config, compiled_patterns in self._compiled_patterns:
            for regex in compiled_patterns:
                match = regex.search(query)
                if match:
                    # Extract entities from match groups
                    entities = [g for g in match.groups() if g]
                    
                    return Intent(
                        intent_type=pattern_config.intent_type,
                        output_format=pattern_config.output_format,
                        confidence=0.9,
                        entities=entities,
                        metadata={"pattern_matched": regex.pattern}
                    )
        
        return None
    
    async def _llm_classify(self, query: str) -> Intent:
        """
        Use LLM to classify ambiguous queries.
        
        Args:
            query: User query
            
        Returns:
            Classified intent
        """
        prompt = f"""Classify the following user query into one of these intent types:
- comparison: User wants to compare things (output as table)
- list: User wants a list of items (output as bullet list)
- how_to: User wants step-by-step instructions (output as numbered list)
- definition: User wants a definition or explanation (output as text)
- fact: User wants a specific fact (output as text)
- data_extraction: User wants data extracted in structured form (output as JSON)
- analysis: User wants analysis of something (output as structured text)
- summary: User wants a summary (output as text)
- general: General query (output as text)

Query: "{query}"

Respond with JSON: {{"intent_type": "...", "output_format": "...", "entities": [...], "confidence": 0.0-1.0}}"""

        from app.schema import Message
        
        response = await self.llm.ask(
            messages=[Message.user_message(prompt)],
            temperature=0.1
        )
        
        try:
            import json
            result = json.loads(response)
            
            return Intent(
                intent_type=IntentType(result.get("intent_type", "general")),
                output_format=OutputFormat(result.get("output_format", "text")),
                confidence=float(result.get("confidence", 0.7)),
                entities=result.get("entities", [])
            )
        except Exception as e:
            logger.warning(f"Failed to parse LLM intent response: {e}")
            return Intent(
                intent_type=IntentType.GENERAL,
                output_format=OutputFormat.TEXT,
                confidence=0.5
            )
    
    def extract_comparison_entities(self, query: str) -> List[str]:
        """Extract entities being compared from a comparison query."""
        patterns = [
            r"compare\s+(.+?)\s+(?:and|vs|versus|with)\s+(.+?)(?:\s|$|\.)",
            r"(.+?)\s+vs\.?\s+(.+?)(?:\s|$|\.)",
            r"difference(?:s)?\s+between\s+(.+?)\s+and\s+(.+?)(?:\s|$|\.)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                entities = [g.strip() for g in match.groups() if g]
                return entities
        
        return []
    
    def extract_list_attributes(self, query: str) -> tuple:
        """Extract list count and subject from a list query."""
        patterns = [
            r"(?:top|best|worst)\s+(\d+)\s+(.+)",
            r"list\s+(?:of\s+)?(?:the\s+)?(?:top\s+)?(\d+)?\s*(.+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                count = int(match.group(1)) if match.group(1) else 5
                subject = match.group(2).strip() if len(match.groups()) > 1 else ""
                return count, subject
        
        return 5, ""
