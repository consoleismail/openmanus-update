"""Unified multimodal input processor."""

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.logger import logger


class MultimodalInput(BaseModel):
    """Container for multimodal input data."""
    
    text: Optional[str] = None
    image_path: Optional[str] = None
    image_base64: Optional[str] = None
    audio_path: Optional[str] = None
    audio_base64: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProcessedInput(BaseModel):
    """Result of processing multimodal input."""
    
    text: str = ""
    image: Optional[Any] = None  # PIL Image
    image_base64: Optional[str] = None
    audio_transcription: Optional[str] = None
    combined_text: str = ""  # Text + any transcriptions
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


class MultimodalProcessor:
    """
    Unified processor for multimodal inputs.
    
    Handles:
    - Text processing and cleaning
    - Image loading and preprocessing
    - Audio transcription (using Whisper)
    - Combining all modalities into a unified format
    """
    
    def __init__(
        self,
        whisper_model: str = "base",
        max_image_size: int = 2048,
        enable_audio: bool = True
    ):
        """
        Initialize the multimodal processor.
        
        Args:
            whisper_model: Whisper model size for transcription
            max_image_size: Maximum image dimension
            enable_audio: Whether to enable audio processing
        """
        self.whisper_model = whisper_model
        self.max_image_size = max_image_size
        self.enable_audio = enable_audio
        
        self._whisper = None
        self._whisper_loaded = False
    
    async def process(self, input_data: MultimodalInput) -> ProcessedInput:
        """
        Process multimodal input.
        
        Args:
            input_data: Input containing text, image, and/or audio
            
        Returns:
            Processed input with all modalities
        """
        result = ProcessedInput()
        
        # Process text
        if input_data.text:
            result.text = self._clean_text(input_data.text)
        
        # Process image
        if input_data.image_path or input_data.image_base64:
            try:
                image, base64_str = self._process_image(
                    path=input_data.image_path,
                    base64_data=input_data.image_base64
                )
                result.image = image
                result.image_base64 = base64_str
            except Exception as e:
                logger.warning(f"Failed to process image: {e}")
        
        # Process audio
        if self.enable_audio and (input_data.audio_path or input_data.audio_base64):
            try:
                transcription = await self._transcribe_audio(
                    path=input_data.audio_path,
                    base64_data=input_data.audio_base64
                )
                result.audio_transcription = transcription
            except Exception as e:
                logger.warning(f"Failed to transcribe audio: {e}")
        
        # Combine text
        parts = []
        if result.text:
            parts.append(result.text)
        if result.audio_transcription:
            parts.append(result.audio_transcription)
        
        result.combined_text = " ".join(parts).strip()
        
        # Copy metadata
        result.metadata = input_data.metadata.copy()
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        import re
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _process_image(
        self,
        path: Optional[str] = None,
        base64_data: Optional[str] = None
    ) -> tuple:
        """
        Process an image from path or base64.
        
        Returns:
            Tuple of (PIL Image, base64 string)
        """
        from PIL import Image
        from io import BytesIO
        
        if path:
            image = Image.open(path)
        elif base64_data:
            # Handle data URL format
            if "," in base64_data:
                base64_data = base64_data.split(",")[1]
            
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(BytesIO(image_bytes))
        else:
            raise ValueError("No image source provided")
        
        # Convert to RGB
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Resize if too large
        if max(image.size) > self.max_image_size:
            ratio = self.max_image_size / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size)
        
        # Convert to base64
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        return image, base64_str
    
    async def _transcribe_audio(
        self,
        path: Optional[str] = None,
        base64_data: Optional[str] = None
    ) -> str:
        """
        Transcribe audio using Whisper.
        
        Returns:
            Transcribed text
        """
        import tempfile
        
        # Load Whisper if not loaded
        if not self._whisper_loaded:
            await self._load_whisper()
        
        # Get audio file path
        audio_path = path
        temp_file = None
        
        if base64_data:
            # Save base64 to temp file
            if "," in base64_data:
                base64_data = base64_data.split(",")[1]
            
            audio_bytes = base64.b64decode(base64_data)
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_file.write(audio_bytes)
            temp_file.close()
            audio_path = temp_file.name
        
        try:
            # Transcribe
            result = self._whisper.transcribe(audio_path)
            return result["text"].strip()
        finally:
            # Clean up temp file
            if temp_file:
                Path(temp_file.name).unlink(missing_ok=True)
    
    async def _load_whisper(self) -> None:
        """Load the Whisper model."""
        try:
            import whisper
            
            logger.info(f"Loading Whisper model: {self.whisper_model}")
            self._whisper = whisper.load_model(self.whisper_model)
            self._whisper_loaded = True
            logger.info("Whisper model loaded")
            
        except ImportError:
            logger.error("openai-whisper not installed. Run: pip install openai-whisper")
            raise
    
    def describe_image(self, image_path: str) -> str:
        """
        Generate a text description of an image.
        
        This is a placeholder - real implementation would use
        a vision model like BLIP or GPT-4V.
        """
        # Placeholder - would call vision model
        return f"Image from: {image_path}"
