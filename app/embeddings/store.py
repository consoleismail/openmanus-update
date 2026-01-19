"""Vector store abstraction for embedding storage and retrieval."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np

from pydantic import BaseModel, Field

from app.embeddings.text import TextEmbedder, TextEmbedderConfig
from app.embeddings.image import ImageEmbedder, ImageEmbedderConfig
from app.logger import logger


class VectorStoreConfig(BaseModel):
    """Configuration for vector store."""
    
    persist_directory: str = "./data/vector_store"
    collection_name: str = "documents"
    distance_metric: str = "cosine"  # cosine, l2, ip


class RetrievedItem(BaseModel):
    """A retrieved item from the vector store."""
    
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    item_type: str = "text"  # text, image
    source_path: Optional[str] = None


class VectorStore:
    """
    Vector store for text embeddings using ChromaDB.
    
    Provides:
    - Document indexing with embeddings
    - Semantic similarity search
    - Metadata filtering
    - Persistence
    """
    
    def __init__(
        self, 
        config: Optional[VectorStoreConfig] = None,
        embedder: Optional[TextEmbedder] = None
    ):
        """
        Initialize the vector store.
        
        Args:
            config: Store configuration
            embedder: Text embedder to use
        """
        self.config = config or VectorStoreConfig()
        self.embedder = embedder or TextEmbedder()
        self._client = None
        self._collection = None
        self._initialized = False
    
    def _initialize(self) -> None:
        """Initialize the ChromaDB client and collection."""
        if self._initialized:
            return
        
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Create persist directory
            persist_path = Path(self.config.persist_directory)
            persist_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize client
            self._client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(persist_path),
                anonymized_telemetry=False
            ))
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.config.collection_name,
                metadata={"hnsw:space": self.config.distance_metric}
            )
            
            self._initialized = True
            logger.info(f"Vector store initialized: {self.config.collection_name}")
            
        except ImportError:
            logger.error("ChromaDB not installed. Run: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    def add_documents(
        self,
        documents: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Add documents to the store.
        
        Args:
            documents: List of document texts
            ids: Optional list of document IDs
            metadatas: Optional list of metadata dicts
            
        Returns:
            List of document IDs
        """
        self._initialize()
        
        # Generate IDs if not provided
        if ids is None:
            ids = [f"doc_{i}_{datetime.now().timestamp()}" for i in range(len(documents))]
        
        # Generate embeddings
        embeddings = self.embedder.embed_batch(documents)
        
        # Add to collection
        self._collection.add(
            documents=documents,
            embeddings=embeddings.tolist(),
            ids=ids,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(documents)} documents to vector store")
        return ids
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedItem]:
        """
        Search for similar documents.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of retrieved items
        """
        self._initialize()
        
        # Generate query embedding
        query_embedding = self.embedder.embed(query)
        
        # Search
        results = self._collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=filter_metadata
        )
        
        # Format results
        items = []
        for i in range(len(results["ids"][0])):
            item = RetrievedItem(
                id=results["ids"][0][i],
                content=results["documents"][0][i] if results["documents"] else "",
                metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                score=1 - results["distances"][0][i] if results["distances"] else 0,
                item_type="text"
            )
            items.append(item)
        
        return items
    
    def delete(self, ids: List[str]) -> None:
        """Delete documents by ID."""
        self._initialize()
        self._collection.delete(ids=ids)
        logger.info(f"Deleted {len(ids)} documents from vector store")
    
    def get(self, ids: List[str]) -> List[RetrievedItem]:
        """Get documents by ID."""
        self._initialize()
        
        results = self._collection.get(ids=ids)
        
        items = []
        for i in range(len(results["ids"])):
            item = RetrievedItem(
                id=results["ids"][i],
                content=results["documents"][i] if results["documents"] else "",
                metadata=results["metadatas"][i] if results["metadatas"] else {},
                item_type="text"
            )
            items.append(item)
        
        return items
    
    @property
    def count(self) -> int:
        """Get the number of documents in the store."""
        self._initialize()
        return self._collection.count()
    
    def persist(self) -> None:
        """Persist the store to disk."""
        if self._client:
            self._client.persist()
            logger.info("Vector store persisted")


class MultimodalVectorStore:
    """
    Unified vector store for text and image embeddings.
    
    Supports:
    - Text document indexing
    - Image indexing with CLIP
    - Cross-modal search (text query for images)
    - Combined retrieval
    """
    
    def __init__(
        self,
        config: Optional[VectorStoreConfig] = None,
        text_embedder: Optional[TextEmbedder] = None,
        image_embedder: Optional[ImageEmbedder] = None
    ):
        """
        Initialize the multimodal vector store.
        
        Args:
            config: Store configuration
            text_embedder: Text embedder to use
            image_embedder: Image embedder (CLIP) to use
        """
        self.config = config or VectorStoreConfig()
        self.text_embedder = text_embedder or TextEmbedder()
        self.image_embedder = image_embedder or ImageEmbedder()
        self._client = None
        self._text_collection = None
        self._image_collection = None
        self._initialized = False
    
    def _initialize(self) -> None:
        """Initialize the ChromaDB client and collections."""
        if self._initialized:
            return
        
        try:
            import chromadb
            from chromadb.config import Settings
            
            persist_path = Path(self.config.persist_directory)
            persist_path.mkdir(parents=True, exist_ok=True)
            
            self._client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(persist_path),
                anonymized_telemetry=False
            ))
            
            # Separate collections for text and images
            self._text_collection = self._client.get_or_create_collection(
                name=f"{self.config.collection_name}_text",
                metadata={"hnsw:space": self.config.distance_metric}
            )
            
            self._image_collection = self._client.get_or_create_collection(
                name=f"{self.config.collection_name}_images",
                metadata={"hnsw:space": self.config.distance_metric}
            )
            
            self._initialized = True
            logger.info("Multimodal vector store initialized")
            
        except ImportError:
            logger.error("ChromaDB not installed. Run: pip install chromadb")
            raise
    
    def add_texts(
        self,
        texts: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """Add text documents to the store."""
        self._initialize()
        
        if ids is None:
            ids = [f"text_{i}_{datetime.now().timestamp()}" for i in range(len(texts))]
        
        embeddings = self.text_embedder.embed_batch(texts)
        
        self._text_collection.add(
            documents=texts,
            embeddings=embeddings.tolist(),
            ids=ids,
            metadatas=metadatas
        )
        
        return ids
    
    def add_images(
        self,
        image_paths: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        descriptions: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add images to the store.
        
        Args:
            image_paths: List of image file paths
            ids: Optional IDs
            metadatas: Optional metadata
            descriptions: Optional text descriptions for each image
        """
        self._initialize()
        
        if ids is None:
            ids = [f"img_{i}_{datetime.now().timestamp()}" for i in range(len(image_paths))]
        
        # Generate CLIP embeddings
        embeddings = self.image_embedder.embed_images(image_paths)
        
        # Prepare metadata with image paths
        if metadatas is None:
            metadatas = [{} for _ in image_paths]
        
        for i, path in enumerate(image_paths):
            metadatas[i]["image_path"] = str(path)
            if descriptions and i < len(descriptions):
                metadatas[i]["description"] = descriptions[i]
        
        # Store descriptions as documents
        docs = descriptions if descriptions else [""] * len(image_paths)
        
        self._image_collection.add(
            documents=docs,
            embeddings=embeddings.tolist(),
            ids=ids,
            metadatas=metadatas
        )
        
        return ids
    
    async def search(
        self,
        query_text: Optional[str] = None,
        query_image: Optional[str] = None,
        top_k: int = 5,
        search_types: Optional[List[str]] = None
    ) -> List[RetrievedItem]:
        """
        Search for relevant text and images.
        
        Args:
            query_text: Text query
            query_image: Image path for visual query
            top_k: Number of results per modality
            search_types: List of types to search ("text", "image")
            
        Returns:
            Combined list of retrieved items ranked by relevance
        """
        self._initialize()
        
        search_types = search_types or ["text", "image"]
        all_results = []
        
        # Search text collection
        if "text" in search_types and query_text:
            text_emb = self.text_embedder.embed(query_text)
            text_results = self._text_collection.query(
                query_embeddings=[text_emb.tolist()],
                n_results=top_k
            )
            
            for i in range(len(text_results["ids"][0])):
                item = RetrievedItem(
                    id=text_results["ids"][0][i],
                    content=text_results["documents"][0][i] if text_results["documents"] else "",
                    metadata=text_results["metadatas"][0][i] if text_results["metadatas"] else {},
                    score=1 - text_results["distances"][0][i] if text_results["distances"] else 0,
                    item_type="text"
                )
                all_results.append(item)
        
        # Search image collection with text query (using CLIP)
        if "image" in search_types and query_text:
            clip_text_emb = self.image_embedder.embed_text(query_text)
            image_results = self._image_collection.query(
                query_embeddings=[clip_text_emb.tolist()],
                n_results=top_k
            )
            
            for i in range(len(image_results["ids"][0])):
                meta = image_results["metadatas"][0][i] if image_results["metadatas"] else {}
                item = RetrievedItem(
                    id=image_results["ids"][0][i],
                    content=meta.get("description", ""),
                    metadata=meta,
                    score=1 - image_results["distances"][0][i] if image_results["distances"] else 0,
                    item_type="image",
                    source_path=meta.get("image_path")
                )
                all_results.append(item)
        
        # Search image collection with image query
        if "image" in search_types and query_image:
            img_emb = self.image_embedder.embed_image(query_image)
            image_results = self._image_collection.query(
                query_embeddings=[img_emb.tolist()],
                n_results=top_k
            )
            
            for i in range(len(image_results["ids"][0])):
                meta = image_results["metadatas"][0][i] if image_results["metadatas"] else {}
                item = RetrievedItem(
                    id=image_results["ids"][0][i],
                    content=meta.get("description", ""),
                    metadata=meta,
                    score=1 - image_results["distances"][0][i] if image_results["distances"] else 0,
                    item_type="image",
                    source_path=meta.get("image_path")
                )
                # Avoid duplicates
                if not any(r.id == item.id for r in all_results):
                    all_results.append(item)
        
        # Sort by score and return
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:top_k * 2]  # Return more results for combined search
    
    def persist(self) -> None:
        """Persist the store to disk."""
        if self._client:
            self._client.persist()
            logger.info("Multimodal vector store persisted")
