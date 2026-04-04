from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class HighlightMoment(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)
    duration: float = Field(..., ge=0)
    score: float = Field(..., ge=0, le=10)
    title: str
    sources: Dict[str, float]
    thumbnail: Optional[str] = None


class AnalysisResult(BaseModel):
    job_id: str
    filename: str
    duration: float
    highlights: List[HighlightMoment]
    metadata: Dict[str, object]
    created_at: datetime


class JobStatus(BaseModel):
    job_id: str
    status: AnalysisStatus
    progress: float = Field(..., ge=0, le=100)
    message: str
    created_at: datetime
    error: Optional[str] = None
