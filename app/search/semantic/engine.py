"""Semantic search engine with hybrid search and re-ranking."""

from typing import Any, Dict, List, Optional, Union
import numpy as np

from pydantic import BaseModel, Field

from app.embeddings.text import TextEmbedder, TextEmbedderConfig
from app.embeddings.store import VectorStore, VectorStoreConfig, RetrievedItem
from app.logger import logger


class SemanticSearchConfig(BaseModel):
    """Configuration for semantic search engine."""
    
    text_model: str = "all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    use_reranking: bool = True
    hybrid_alpha: float = 0.5  # Weight for semantic vs keyword (1.0 = all semantic)
    default_top_k: int = 10
    min_score_threshold: float = 0.0


class SearchResult(BaseModel):
    """A semantic search result."""
    
    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    highlights: List[str] = Field(default_factory=list)
    source: str = ""
    
    class Config:
        arbitrary_types_allowed = True


class SemanticSearchEngine:
    """
    Semantic search engine with hybrid search and re-ranking.
    
    Features:
    - Pure semantic search using embeddings
    - Hybrid search combining keyword and semantic
    - Cross-encoder re-ranking for improved precision
    - Configurable scoring thresholds
    """
    
    def __init__(self, config: Optional[SemanticSearchConfig] = None):
        """
        Initialize the semantic search engine.
        
        Args:
            config: Engine configuration
        """
        self.config = config or SemanticSearchConfig()
        
        # Initialize embedder
        self.embedder = TextEmbedder(TextEmbedderConfig(
            model_name=self.config.text_model
        ))
        
        # Initialize vector store
        self.vector_store = VectorStore(
            embedder=self.embedder
        )
        
        # Reranker (lazy loaded)
        self._reranker = None
        self._reranker_loaded = False
    
    def _load_reranker(self) -> None:
        """Lazy load the cross-encoder reranker."""
        if self._reranker_loaded or not self.config.use_reranking:
            return
        
        try:
            from sentence_transformers import CrossEncoder
            
            logger.info(f"Loading reranker: {self.config.reranker_model}")
            self._reranker = CrossEncoder(self.config.reranker_model)
            self._reranker_loaded = True
            logger.info("Reranker loaded successfully")
            
        except ImportError:
            logger.warning("sentence-transformers not installed, reranking disabled")
            self.config.use_reranking = False
        except Exception as e:
            logger.warning(f"Failed to load reranker: {e}")
            self.config.use_reranking = False
    
    def index_documents(
        self,
        documents: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Index documents for search.
        
        Args:
            documents: List of document texts
            ids: Optional document IDs
            metadatas: Optional metadata for each document
            
        Returns:
            List of document IDs
        """
        return self.vector_store.add_documents(
            documents=documents,
            ids=ids,
            metadatas=metadatas
        )
    
    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        use_reranking: Optional[bool] = None
    ) -> List[SearchResult]:
        """
        Search for relevant documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filter
            use_reranking: Whether to use reranking (overrides config)
            
        Returns:
            List of search results
        """
        top_k = top_k or self.config.default_top_k
        use_reranking = use_reranking if use_reranking is not None else self.config.use_reranking
        
        # Get initial results (retrieve more for reranking)
        retrieve_k = top_k * 3 if use_reranking else top_k
        
        retrieved = self.vector_store.search(
            query=query,
            top_k=retrieve_k,
            filter_metadata=filter_metadata
        )
        
        # Convert to SearchResult
        results = [
            SearchResult(
                id=item.id,
                content=item.content,
                score=item.score,
                metadata=item.metadata,
                source=item.metadata.get("source", "")
            )
            for item in retrieved
        ]
        
        # Apply reranking if enabled
        if use_reranking and results:
            results = self._rerank(query, results)
        
        # Filter by threshold
        results = [
            r for r in results 
            if r.score >= self.config.min_score_threshold
        ]
        
        # Generate highlights
        for result in results:
            result.highlights = self._generate_highlights(query, result.content)
        
        return results[:top_k]
    
    def _rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """Rerank results using cross-encoder."""
        self._load_reranker()
        
        if not self._reranker:
            return results
        
        # Prepare pairs for cross-encoder
        pairs = [[query, r.content] for r in results]
        
        # Get reranking scores
        scores = self._reranker.predict(pairs)
        
        # Update scores and sort
        for i, result in enumerate(results):
            # Combine original score with reranker score
            result.score = float(scores[i])
        
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results
    
    def _generate_highlights(self, query: str, content: str, max_highlights: int = 3) -> List[str]:
        """Generate text highlights for the query terms."""
        if not content:
            return []
        
        highlights = []
        query_terms = query.lower().split()
        sentences = content.split(". ")
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(term in sentence_lower for term in query_terms):
                # Truncate long sentences
                if len(sentence) > 200:
                    sentence = sentence[:200] + "..."
                highlights.append(sentence.strip())
                
                if len(highlights) >= max_highlights:
                    break
        
        return highlights
    
    async def hybrid_search(
        self,
        query: str,
        top_k: Optional[int] = None,
        alpha: Optional[float] = None
    ) -> List[SearchResult]:
        """
        Hybrid search combining semantic and keyword matching.
        
        Args:
            query: Search query
            top_k: Number of results
            alpha: Weight for semantic (1.0) vs keyword (0.0)
            
        Returns:
            List of search results
        """
        top_k = top_k or self.config.default_top_k
        alpha = alpha if alpha is not None else self.config.hybrid_alpha
        
        # Get semantic results
        semantic_results = await self.search(
            query=query,
            top_k=top_k * 2,
            use_reranking=False
        )
        
        # Get keyword results (simple approach)
        keyword_results = self._keyword_search(query, top_k * 2)
        
        # Merge results
        merged = self._merge_results(
            semantic_results,
            keyword_results,
            alpha=alpha
        )
        
        # Rerank merged results
        if self.config.use_reranking:
            merged = self._rerank(query, merged)
        
        return merged[:top_k]
    
    def _keyword_search(self, query: str, top_k: int) -> List[SearchResult]:
        """Simple keyword-based search."""
        # This is a placeholder - in production, use a proper
        # keyword search engine like Elasticsearch or BM25
        
        results = self.vector_store.search(query=query, top_k=top_k)
        
        keyword_results = []
        query_terms = set(query.lower().split())
        
        for item in results:
            content_terms = set(item.content.lower().split())
            overlap = len(query_terms & content_terms)
            keyword_score = overlap / len(query_terms) if query_terms else 0
            
            keyword_results.append(SearchResult(
                id=item.id,
                content=item.content,
                score=keyword_score,
                metadata=item.metadata
            ))
        
        keyword_results.sort(key=lambda x: x.score, reverse=True)
        return keyword_results
    
    def _merge_results(
        self,
        semantic: List[SearchResult],
        keyword: List[SearchResult],
        alpha: float
    ) -> List[SearchResult]:
        """Merge semantic and keyword results with weighted scoring."""
        # Normalize scores
        if semantic:
            max_sem = max(r.score for r in semantic)
            for r in semantic:
                r.score = r.score / max_sem if max_sem > 0 else 0
        
        if keyword:
            max_kw = max(r.score for r in keyword)
            for r in keyword:
                r.score = r.score / max_kw if max_kw > 0 else 0
        
        # Merge by ID
        merged_dict: Dict[str, SearchResult] = {}
        
        for r in semantic:
            merged_dict[r.id] = SearchResult(
                id=r.id,
                content=r.content,
                score=alpha * r.score,
                metadata=r.metadata
            )
        
        for r in keyword:
            if r.id in merged_dict:
                merged_dict[r.id].score += (1 - alpha) * r.score
            else:
                merged_dict[r.id] = SearchResult(
                    id=r.id,
                    content=r.content,
                    score=(1 - alpha) * r.score,
                    metadata=r.metadata
                )
        
        # Sort by combined score
        merged = list(merged_dict.values())
        merged.sort(key=lambda x: x.score, reverse=True)
        
        return merged
    
    @property
    def document_count(self) -> int:
        """Get the number of indexed documents."""
        return self.vector_store.count
