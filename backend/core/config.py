"""Application configuration"""
import os
from typing import Optional, List


class Settings:
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    max_file_size_mb: int = 10
    allowed_mime_types: List[str] = ["image/jpeg", "image/png", "application/pdf"]
    gemini_model: str = "gemini-1.5-flash"


settings = Settings()
