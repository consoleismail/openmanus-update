"""Image embedding generation using CLIP."""

from pathlib import Path
from typing import List, Optional, Union
import numpy as np

from pydantic import BaseModel, Field

from app.logger import logger


class ImageEmbedderConfig(BaseModel):
    """Configuration for image embedder."""
    
    model_name: str = "openai/clip-vit-base-patch32"
    cache_folder: Optional[str] = None
    device: str = "cpu"  # cpu, cuda, mps
    max_image_size: int = 2048


class ImageEmbedder:
    """
    Generate image embeddings using CLIP.
    
    CLIP (Contrastive Language-Image Pre-training) embeddings allow:
    - Image-to-image similarity search
    - Text-to-image search (same embedding space)
    - Cross-modal retrieval
    """
    
    def __init__(self, config: Optional[ImageEmbedderConfig] = None):
        """
        Initialize the image embedder.
        
        Args:
            config: Embedder configuration
        """
        self.config = config or ImageEmbedderConfig()
        self._model = None
        self._processor = None
        self._model_loaded = False
    
    def _load_model(self) -> None:
        """Lazy load the CLIP model."""
        if self._model_loaded:
            return
        
        try:
            from transformers import CLIPModel, CLIPProcessor
            import torch
            
            logger.info(f"Loading CLIP model: {self.config.model_name}")
            
            self._model = CLIPModel.from_pretrained(
                self.config.model_name,
                cache_dir=self.config.cache_folder
            )
            self._processor = CLIPProcessor.from_pretrained(
                self.config.model_name,
                cache_dir=self.config.cache_folder
            )
            
            # Move to device
            if self.config.device != "cpu":
                self._model = self._model.to(self.config.device)
            
            self._model.eval()
            self._model_loaded = True
            
            logger.info("CLIP model loaded successfully")
            
        except ImportError:
            logger.error("transformers not installed. Run: pip install transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            raise
    
    def _load_image(self, image_source: Union[str, Path, "Image.Image"]) -> "Image.Image":
        """Load an image from various sources."""
        from PIL import Image
        
        if isinstance(image_source, (str, Path)):
            path = Path(image_source)
            if path.exists():
                image = Image.open(path)
            elif str(image_source).startswith(("http://", "https://")):
                import requests
                from io import BytesIO
                response = requests.get(str(image_source))
                image = Image.open(BytesIO(response.content))
            else:
                raise ValueError(f"Invalid image path: {image_source}")
        else:
            image = image_source
        
        # Convert to RGB if necessary
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Resize if too large
        if max(image.size) > self.config.max_image_size:
            ratio = self.config.max_image_size / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size)
        
        return image
    
    def embed_image(self, image: Union[str, Path, "Image.Image"]) -> np.ndarray:
        """
        Generate embedding for an image.
        
        Args:
            image: Image path, URL, or PIL Image object
            
        Returns:
            Numpy array of the image embedding
        """
        self._load_model()
        import torch
        
        img = self._load_image(image)
        
        inputs = self._processor(images=img, return_tensors="pt")
        
        if self.config.device != "cpu":
            inputs = {k: v.to(self.config.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            features = self._model.get_image_features(**inputs)
        
        # Normalize
        features = features / features.norm(dim=-1, keepdim=True)
        
        return features.cpu().numpy().flatten()
    
    def embed_images(self, images: List[Union[str, Path, "Image.Image"]]) -> np.ndarray:
        """
        Generate embeddings for multiple images.
        
        Args:
            images: List of image paths, URLs, or PIL Image objects
            
        Returns:
            Numpy array of image embeddings
        """
        self._load_model()
        import torch
        
        imgs = [self._load_image(img) for img in images]
        
        inputs = self._processor(images=imgs, return_tensors="pt", padding=True)
        
        if self.config.device != "cpu":
            inputs = {k: v.to(self.config.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            features = self._model.get_image_features(**inputs)
        
        # Normalize
        features = features / features.norm(dim=-1, keepdim=True)
        
        return features.cpu().numpy()
    
    def embed_text(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Generate CLIP text embedding (in the same space as images).
        
        This allows text-to-image search where you can find images
        matching a text description.
        
        Args:
            text: Text string or list of strings
            
        Returns:
            Numpy array of text embedding(s)
        """
        self._load_model()
        import torch
        
        single_input = isinstance(text, str)
        texts = [text] if single_input else text
        
        inputs = self._processor(text=texts, return_tensors="pt", padding=True)
        
        if self.config.device != "cpu":
            inputs = {k: v.to(self.config.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            features = self._model.get_text_features(**inputs)
        
        # Normalize
        features = features / features.norm(dim=-1, keepdim=True)
        
        embeddings = features.cpu().numpy()
        
        if single_input:
            return embeddings.flatten()
        return embeddings
    
    def image_text_similarity(
        self, 
        image: Union[str, Path, "Image.Image"],
        texts: List[str]
    ) -> np.ndarray:
        """
        Calculate similarity between an image and texts.
        
        Args:
            image: Image to compare
            texts: List of text descriptions
            
        Returns:
            Array of similarity scores
        """
        image_emb = self.embed_image(image)
        text_embs = self.embed_text(texts)
        
        return np.dot(text_embs, image_emb)
    
    def image_similarity(
        self,
        image1: Union[str, Path, "Image.Image"],
        image2: Union[str, Path, "Image.Image"]
    ) -> float:
        """
        Calculate similarity between two images.
        
        Args:
            image1: First image
            image2: Second image
            
        Returns:
            Cosine similarity score
        """
        emb1 = self.embed_image(image1)
        emb2 = self.embed_image(image2)
        
        return float(np.dot(emb1, emb2))
    
    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        self._load_model()
        return self._model.config.projection_dim
    
    def unload(self) -> None:
        """Unload the model to free memory."""
        if self._model is not None:
            del self._model
            del self._processor
            self._model = None
            self._processor = None
            self._model_loaded = False
            logger.info("CLIP model unloaded")
