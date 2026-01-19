"""Multimodal Search Tool - Search using text and images."""

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import Field

from app.tool.base import BaseTool, ToolResult
from app.embeddings.store import MultimodalVectorStore, RetrievedItem
from app.embeddings.text import TextEmbedder
from app.embeddings.image import ImageEmbedder
from app.logger import logger


class MultimodalSearchTool(BaseTool):
    """
    Search tool that handles text and image queries.
    
    Supports:
    - Text-only search
    - Image-only search (find similar images)
    - Combined text+image search
    - Cross-modal search (find images matching text description)
    """
    
    name: str = "multimodal_search"
    description: str = """Search using text and/or images.
    
Use this tool to:
- Search for information using text queries
- Find images similar to a given image
- Ask questions about an image
- Find content matching both text and image criteria

The tool supports cross-modal search, meaning you can describe an image
in text and find matching images, or provide an image to find related text."""
    
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Text query describing what to search for"
            },
            "image_path": {
                "type": "string",
                "description": "Optional path to an image file to use in search"
            },
            "search_type": {
                "type": "string",
                "enum": ["text", "image", "combined"],
                "default": "combined",
                "description": "Type of search: text-only, image-only, or combined"
            },
            "top_k": {
                "type": "integer",
                "default": 5,
                "description": "Number of results to return"
            }
        },
        "required": ["query"]
    }
    
    # Vector store for multimodal search
    _vector_store: Optional[MultimodalVectorStore] = None
    _initialized: bool = False
    
    class Config:
        arbitrary_types_allowed = True
    
    def _initialize(self) -> None:
        """Initialize the vector store and embedders."""
        if self._initialized:
            return
        
        try:
            self._vector_store = MultimodalVectorStore()
            self._initialized = True
            logger.info("MultimodalSearchTool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MultimodalSearchTool: {e}")
            raise
    
    async def execute(
        self,
        query: str,
        image_path: Optional[str] = None,
        search_type: str = "combined",
        top_k: int = 5
    ) -> ToolResult:
        """
        Execute multimodal search.
        
        Args:
            query: Text query
            image_path: Optional path to image file
            search_type: Type of search (text, image, combined)
            top_k: Number of results
            
        Returns:
            ToolResult with search results
        """
        try:
            self._initialize()
            
            # Validate image path if provided
            if image_path:
                path = Path(image_path)
                if not path.exists():
                    return self.fail_response(f"Image file not found: {image_path}")
                if not self._is_valid_image(path):
                    return self.fail_response(f"Invalid image file: {image_path}")
            
            # Determine search modalities
            search_types = []
            if search_type == "text" or (search_type == "combined" and query):
                search_types.append("text")
            if search_type == "image" or (search_type == "combined" and image_path):
                search_types.append("image")
            
            # Execute search
            results = await self._vector_store.search(
                query_text=query if query else None,
                query_image=image_path,
                top_k=top_k,
                search_types=search_types
            )
            
            # Format results
            formatted_results = self._format_results(results, query, image_path)
            
            return self.success_response(formatted_results)
            
        except Exception as e:
            logger.error(f"Multimodal search error: {e}")
            return self.fail_response(f"Search failed: {str(e)}")
    
    def _is_valid_image(self, path: Path) -> bool:
        """Check if file is a valid image."""
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        return path.suffix.lower() in valid_extensions
    
    def _format_results(
        self,
        results: List[RetrievedItem],
        query: str,
        image_path: Optional[str]
    ) -> Dict[str, Any]:
        """Format search results for output."""
        formatted = {
            "query": query,
            "image_query": image_path,
            "result_count": len(results),
            "results": []
        }
        
        for result in results:
            item = {
                "id": result.id,
                "type": result.item_type,
                "score": round(result.score, 4),
                "content": result.content[:500] if result.content else "",
            }
            
            if result.source_path:
                item["image_path"] = result.source_path
            
            if result.metadata:
                item["metadata"] = result.metadata
            
            formatted["results"].append(item)
        
        return formatted
    
    async def index_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Index a text document for search.
        
        Args:
            content: Document text
            metadata: Optional metadata
            
        Returns:
            Document ID
        """
        self._initialize()
        
        ids = self._vector_store.add_texts(
            texts=[content],
            metadatas=[metadata] if metadata else None
        )
        
        return ids[0]
    
    async def index_image(
        self,
        image_path: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Index an image for search.
        
        Args:
            image_path: Path to image file
            description: Optional text description
            metadata: Optional metadata
            
        Returns:
            Image ID
        """
        self._initialize()
        
        ids = self._vector_store.add_images(
            image_paths=[image_path],
            descriptions=[description] if description else None,
            metadatas=[metadata] if metadata else None
        )
        
        return ids[0]


class ImageAnalysisTool(BaseTool):
    """
    Analyze images and answer questions about them.
    
    Uses vision-capable LLMs to understand image content
    and answer natural language questions.
    """
    
    name: str = "analyze_image"
    description: str = """Analyze an image and answer questions about it.
    
Use this tool to:
- Describe what's in an image
- Answer questions about image content
- Identify objects, text, or people in images
- Extract information from charts, diagrams, or documents"""
    
    parameters: dict = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image file to analyze"
            },
            "question": {
                "type": "string",
                "description": "Question to answer about the image"
            }
        },
        "required": ["image_path"]
    }
    
    async def execute(
        self,
        image_path: str,
        question: Optional[str] = None
    ) -> ToolResult:
        """
        Analyze an image.
        
        Args:
            image_path: Path to image file
            question: Optional question about the image
            
        Returns:
            ToolResult with analysis
        """
        try:
            path = Path(image_path)
            
            if not path.exists():
                return self.fail_response(f"Image file not found: {image_path}")
            
            # Read and encode image
            with open(path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            
            # Determine MIME type
            mime_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
            }
            mime_type = mime_types.get(path.suffix.lower(), 'image/jpeg')
            
            # Build prompt
            if question:
                prompt = f"Please analyze this image and answer the following question: {question}"
            else:
                prompt = "Please describe this image in detail, including any text, objects, people, or notable features you can see."
            
            # Use LLM with vision capability
            from app.llm import LLM
            from app.schema import Message
            
            llm = LLM()
            
            # Create message with image
            messages = [
                Message.user_message(
                    content=prompt,
                    base64_image=f"data:{mime_type};base64,{image_data}"
                )
            ]
            
            response = await llm.ask(messages=messages)
            
            return self.success_response({
                "image_path": str(path),
                "question": question,
                "analysis": response
            })
            
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return self.fail_response(f"Analysis failed: {str(e)}")
