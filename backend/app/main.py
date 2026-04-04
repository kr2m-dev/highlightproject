"""
Video Highlight Extractor - Application principale
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import app
from .core.config import settings

__all__ = ["app"]
