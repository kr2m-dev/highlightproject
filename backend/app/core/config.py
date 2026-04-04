"""
Configuration avec Pydantic Settings v2
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Video Highlight Extractor"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    GROQ_API_KEY: Optional[str] = None

    GROQ_MODEL_VISION: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    GROQ_MODEL_WHISPER: str = "whisper-large-v3"
    GROQ_MAX_TOKENS: int = 800
    GROQ_TEMPERATURE: float = 0.2
    GROQ_TIMEOUT: int = 30

    UPLOAD_DIR: Path = Path("./tmp/uploads")
    OUTPUT_DIR: Path = Path("./tmp/output")
    CACHE_DIR: Path = Path("./tmp/cache")

    DEFAULT_VISION_INTERVAL: int = 60
    DEFAULT_MAX_CLIPS: int = 20

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for dir_path in [self.UPLOAD_DIR, self.OUTPUT_DIR, self.CACHE_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
