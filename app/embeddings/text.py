"""Text embedding generation using sentence-transformers."""

from typing import List, Optional, Union
import numpy as np

from pydantic import BaseModel, Field

from app.logger import logger


class TextEmbedderConfig(BaseModel):
    """Configuration for text embedder."""
    
    model_name: str = "all-MiniLM-L6-v2"
    cache_folder: Optional[str] = None
    device: str = "cpu"  # cpu, cuda, mps
    max_seq_length: int = 256
    normalize_embeddings: bool = True


class TextEmbedder:
    """
    Generate text embeddings using sentence-transformers.
    
    Provides semantic embeddings for text that capture meaning,
    enabling similarity-based search and retrieval.
    """
    
    def __init__(self, config: Optional[TextEmbedderConfig] = None):
        """
        Initialize the text embedder.
        
        Args:
            config: Embedder configuration
        """
        self.config = config or TextEmbedderConfig()
        self._model = None
        self._model_loaded = False
        
    def _load_model(self) -> None:
        """Lazy load the sentence-transformer model."""
        if self._model_loaded:
            return
            
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Loading text embedding model: {self.config.model_name}")
            
            self._model = SentenceTransformer(
                self.config.model_name,
                cache_folder=self.config.cache_folder,
                device=self.config.device
            )
            
            if self.config.max_seq_length:
                self._model.max_seq_length = self.config.max_seq_length
            
            self._model_loaded = True
            logger.info("Text embedding model loaded successfully")
            
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load text embedding model: {e}")
            raise
    
    def embed(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Generate embeddings for text.
        
        Args:
            text: Single text string or list of strings
            
        Returns:
            Numpy array of embeddings (2D for list, 1D for single string)
        """
        self._load_model()
        
        single_input = isinstance(text, str)
        texts = [text] if single_input else text
        
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=False
        )
        
        if single_input:
            return embeddings[0]
        return embeddings
    
    def embed_batch(
        self, 
        texts: List[str], 
        batch_size: int = 32,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: List of text strings
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar
            
        Returns:
            Numpy array of embeddings
        """
        self._load_model()
        
        return self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=show_progress
        )
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Cosine similarity score (0 to 1 for normalized embeddings)
        """
        emb1 = self.embed(text1)
        emb2 = self.embed(text2)
        
        return float(np.dot(emb1, emb2))
    
    def find_most_similar(
        self, 
        query: str, 
        candidates: List[str],
        top_k: int = 5
    ) -> List[tuple]:
        """
        Find the most similar texts from candidates.
        
        Args:
            query: Query text
            candidates: List of candidate texts
            top_k: Number of top results to return
            
        Returns:
            List of (index, text, score) tuples sorted by similarity
        """
        query_emb = self.embed(query)
        candidate_embs = self.embed(candidates)
        
        # Calculate similarities
        similarities = np.dot(candidate_embs, query_emb)
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        return [
            (int(idx), candidates[idx], float(similarities[idx]))
            for idx in top_indices
        ]
    
    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        self._load_model()
        return self._model.get_sentence_embedding_dimension()
    
    def unload(self) -> None:
        """Unload the model to free memory."""
        if self._model is not None:
            del self._model
            self._model = None
            self._model_loaded = False
            logger.info("Text embedding model unloaded")
