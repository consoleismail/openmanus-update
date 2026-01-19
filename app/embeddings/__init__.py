# Embeddings Module
# Provides text and image embedding generation using sentence-transformers and CLIP

from app.embeddings.text import TextEmbedder
from app.embeddings.image import ImageEmbedder
from app.embeddings.store import VectorStore, MultimodalVectorStore

__all__ = [
    "TextEmbedder",
    "ImageEmbedder",
    "VectorStore",
    "MultimodalVectorStore",
]
