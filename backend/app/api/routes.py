"""
Routes API pour Video Highlight Extractor
"""
import uuid
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import settings
from ..models.schemas import AnalysisStatus, JobStatus, AnalysisResult, HighlightMoment
from ..utils.helpers import FrameExtractor
from ..services.vision_analyzer import VisionAnalyzer
from ..services.transcript_analyzer import TranscriptAnalyzer
from ..services.fusion_engine import FusionEngine

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

frontend_path = Path(__file__).parent.parent.parent.parent / "frontend" / "static"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs_store: dict = {}
results_store: dict = {}


@app.on_event("startup")
async def startup():
    for dir_path in [settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.CACHE_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


@app.get("/")
async def root():
    frontend_path = Path(__file__).parent.parent.parent.parent / "frontend" / "static" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return {"message": "Video Highlight Extractor API", "docs": "/docs"}


@app.get("/api/v1/health")
async def health():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/v1/debug/groq-models")
async def debug_groq_models():
    """Debug endpoint to check available Groq models"""
    import httpx
    
    if not settings.GROQ_API_KEY:
        return {"error": "No GROQ_API_KEY configured"}
    
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                models = [m["id"] for m in data.get("data", [])]
                vision_models = [m for m in models if "vision" in m.lower()]
                return {
                    "all_models": models,
                    "vision_models": vision_models,
                    "configured_model": settings.GROQ_MODEL_VISION
                }
            else:
                return {
                    "error": f"API returned {response.status_code}",
                    "detail": response.text
                }
        except Exception as e:
            return {"error": str(e)}


@app.get("/api/v1/debug/test-vision")
async def debug_test_vision():
    """Test vision API with a simple request"""
    from PIL import Image
    import io
    import base64
    
    if not settings.GROQ_API_KEY:
        return {"error": "No GROQ_API_KEY configured"}
    
    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": settings.GROQ_MODEL_VISION,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What color is this image?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 100
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers
            )
            
            return {
                "status_code": response.status_code,
                "model_used": settings.GROQ_MODEL_VISION,
                "response": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"error": str(e)}


@app.post("/api/v1/upload")
async def upload_video(
    video: Optional[UploadFile] = File(None),
    video_path: Optional[str] = Form(default=None),
    vision_interval: int = Form(default=60),
    max_clips: int = Form(default=20),
    enable_vision: bool = Form(default=False),  # Désactivé par défaut (modèle non disponible)
    enable_transcript: bool = Form(default=True)
):
    """
    Analyse une vidéo - deux modes possits:
    1. Upload direct: envoyer le fichier via form-data 'video'
    2. Chemin serveur: fournir 'video_path' (chemin absolu sur le serveur)
    
    Utile pour AWS où les fichiers sont déjà sur le serveur.
    """
    allowed_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    job_id = str(uuid.uuid4())
    
    if video and video.filename:
        ext = Path(video.filename).suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Format non supporté. Formats acceptés: {allowed_extensions}"
            )
        
        final_video_path = settings.UPLOAD_DIR / f"{job_id}{ext}"
        
        try:
            content = await video.read()
            with open(final_video_path, "wb") as f:
                f.write(content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur sauvegarde vidéo: {str(e)}")
        
        source = "upload"
        
    elif video_path:
        video_path = video_path.strip()
        
        # Linux absolute path: starts with /
        # Windows absolute path: C:\ or C:/
        BACKSLASH = chr(92)  # '\\'
        is_absolute = (
            video_path.startswith('/') or  # Linux
            (len(video_path) >= 3 and video_path[1] == ':' and video_path[2] in (BACKSLASH, '/'))  # Windows
        )

        if not is_absolute:
            raise HTTPException(
                status_code=400,
                detail=f"Le chemin doit être absolu: {video_path}"
            )
        
        final_video_path = Path(video_path)
        
        if not final_video_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Fichier non trouvé: {video_path}"
            )
        
        ext = final_video_path.suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Format non supporté. Formats acceptés: {allowed_extensions}"
            )
        
        source = "server_path"
        
    else:
        raise HTTPException(
            status_code=400,
            detail="Fournir soit 'video' (fichier) soit 'video_path' (chemin serveur)"
        )
    
    jobs_store[job_id] = JobStatus(
        job_id=job_id,
        status=AnalysisStatus.UPLOADING,
        progress=5,
        message=f"Vidéo prête ({source})",
        created_at=datetime.now()
    )
    
    asyncio.create_task(process_video(
        job_id, 
        final_video_path, 
        vision_interval, 
        max_clips,
        enable_vision,
        enable_transcript
    ))
    
    return {
        "job_id": job_id,
        "message": "Analyse démarrée",
        "video_path": str(final_video_path),
        "source": source
    }


def update_progress(job_id: str, progress: float, message: str):
    """Met à jour la progression d'un job"""
    if job_id in jobs_store:
        jobs_store[job_id] = JobStatus(
            job_id=job_id,
            status=jobs_store[job_id].status,
            progress=progress,
            message=message,
            created_at=jobs_store[job_id].created_at
        )


async def process_video(
    job_id: str,
    video_path: Path,
    vision_interval: int,
    max_clips: int,
    enable_vision: bool,
    enable_transcript: bool
):
    """Background task pour traiter la vidéo"""
    try:
        jobs_store[job_id] = JobStatus(
            job_id=job_id,
            status=AnalysisStatus.EXTRACTING,
            progress=10,
            message="Extraction des frames...",
            created_at=jobs_store[job_id].created_at
        )

        extractor = FrameExtractor(settings.OUTPUT_DIR)

        duration = await extractor.get_video_duration(video_path)

        frames = await extractor.extract_frames(
            video_path,
            interval_seconds=vision_interval,
            max_frames=max_clips
        )

        vision_results = []
        transcript_results = {"transcript": {}, "highlights": []}

        if enable_vision and frames:
            jobs_store[job_id] = JobStatus(
                job_id=job_id,
                status=AnalysisStatus.ANALYZING,
                progress=30,
                message=f"Analyse visuelle de {len(frames)} frames...",
                created_at=jobs_store[job_id].created_at
            )

            vision_analyzer = VisionAnalyzer(settings.GROQ_API_KEY)

            def vision_progress_callback(current, total, msg):
                progress = 30 + (current / total) * 25
                update_progress(job_id, progress, msg)

            vision_results = await vision_analyzer.analyze_frames(frames, vision_progress_callback)

        if enable_transcript:
            jobs_store[job_id] = JobStatus(
                job_id=job_id,
                status=AnalysisStatus.ANALYZING,
                progress=55,
                message="Extraction et transcription audio...",
                created_at=jobs_store[job_id].created_at
            )

            audio_path = await extractor.extract_audio(video_path)
            
            transcript_analyzer = TranscriptAnalyzer(settings.GROQ_API_KEY)

            def transcript_progress_callback(current, total, msg):
                progress = 55 + (current / total) * 35
                update_progress(job_id, progress, msg)

            transcript_results = await transcript_analyzer.analyze_audio(
                audio_path,
                transcript_progress_callback
            )

        jobs_store[job_id] = JobStatus(
            job_id=job_id,
            status=AnalysisStatus.PROCESSING,
            progress=95,
            message="Fusion des résultats...",
            created_at=jobs_store[job_id].created_at
        )

        fusion_engine = FusionEngine()
        
        vision_highlights = []
        for result in vision_results:
            if result.get("is_highlight", False) or result.get("score", 0) >= 3.0:
                vision_highlights.append(result)
        
        transcript_highlights = transcript_results.get("highlights", [])
        
        fused_highlights = fusion_engine.combine_scores(
            vision_highlights,
            transcript_highlights
        )

        jobs_store[job_id] = JobStatus(
            job_id=job_id,
            status=AnalysisStatus.COMPLETED,
            progress=100,
            message="Analyse terminée",
            created_at=jobs_store[job_id].created_at
        )

        highlights = []
        for h in fused_highlights:
            highlights.append(HighlightMoment(
                start=h["timestamp"],
                end=h["timestamp"] + vision_interval,
                duration=vision_interval,
                score=h["score"],
                title=h.get("title", "Moment fort"),
                sources=h.get("sources", {}),
                thumbnail=None
            ))

        results_store[job_id] = AnalysisResult(
            job_id=job_id,
            filename=video_path.name,
            duration=duration,
            highlights=highlights,
            metadata={
                "frames_extracted": len(frames),
                "vision_results": len(vision_results),
                "transcript_segments": len(transcript_results.get("transcript", {}).get("segments", [])),
                "transcript_highlights": len(transcript_results.get("highlights", [])),
                "highlights_found": len(highlights)
            },
            created_at=datetime.now()
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs_store[job_id] = JobStatus(
            job_id=job_id,
            status=AnalysisStatus.FAILED,
            progress=0,
            message="Erreur lors de l'analyse",
            created_at=jobs_store[job_id].created_at,
            error=str(e)
        )


@app.get("/api/v1/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Retourne le statut d'un job"""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job non trouvé")
    return jobs_store[job_id]


@app.get("/api/v1/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """Retourne les résultats d'une analyse"""
    if job_id not in results_store:
        raise HTTPException(status_code=404, detail="Résultat non trouvé")
    return results_store[job_id]


@app.get("/api/v1/jobs/{job_id}/export")
async def export_job_result(job_id: str):
    """Télécharge les résultats en JSON"""
    from fastapi.responses import Response
    
    if job_id not in results_store:
        raise HTTPException(status_code=404, detail="Résultat non trouvé")
    
    result = results_store[job_id].model_dump()
    result["created_at"] = result["created_at"].isoformat()
    
    json_content = json.dumps(result, indent=2, ensure_ascii=False)
    
    return Response(
        content=json_content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=highlights_{job_id}.json"
        }
    )


@app.get("/api/v1/jobs")
async def list_jobs():
    """Liste tous les jobs"""
    return list(jobs_store.values())


@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str):
    """Supprime un job et ses fichiers"""
    if job_id in jobs_store:
        del jobs_store[job_id]
    if job_id in results_store:
        del results_store[job_id]
    
    for ext in [".mp4", ".avi", ".mov", ".mkv", ".webm"]:
        video_path = settings.UPLOAD_DIR / f"{job_id}{ext}"
        if video_path.exists():
            video_path.unlink()
    
    return {"message": "Job supprimé"}
