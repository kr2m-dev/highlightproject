# YouTube Highlight Extractor - Spécifications Complètes

## 🎯 Objectif du Projet

Créer une application web complète pour extraire automatiquement les moments forts de vidéos YouTube en utilisant l'IA multi-signal (vision, transcription, commentaires).

---

## 📋 Stack Technique

### Backend
- **Python 3.11+** (pas 3.13 - problèmes de compatibilité)
- **FastAPI** - Framework web asynchrone
- **Pydantic v2** - Validation des données
- **yt-dlp** - Téléchargement vidéo YouTube
- **ffmpeg** - Extraction des frames vidéo
- **httpx** - Client HTTP asynchrone pour les APIs
- **Pillow** - Traitement d'images
- **Redis** - Cache et gestion des jobs (optionnel)

### Frontend
- **HTML5/CSS3/JavaScript vanilla** - Pas de framework
- **Design moderne** - Interface responsive avec gradients

### APIs Externes
1. **Groq API** - Pour Whisper (transcription) ET Vision (Llama 3.2 11B Vision)
2. **YouTube Data API v3** - Pour les commentaires

---

## 🔑 Configuration Requise

Fichier `.env` à la racine :
```env
GROQ_API_KEY=gsk_xxxxx
YOUTUBE_API_KEY=AIzaxxxxx
```

---

## 🏗️ Architecture du Projet

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py              # Point d'entrée FastAPI
│   │   ├── core/
│   │   │   └── config.py        # Configuration avec Pydantic Settings
│   │   ├── api/
│   │   │   └── routes.py        # Routes API
│   │   ├── models/
│   │   │   └── schemas.py       # Modèles Pydantic
│   │   ├── services/
│   │   │   ├── video_downloader.py      # Téléchargement vidéo
│   │   │   ├── vision_analyzer.py       # Analyse visuelle
│   │   │   ├── transcript_analyzer.py   # Transcription Whisper
│   │   │   ├── comment_analyzer.py      # Analyse commentaires
│   │   │   ├── fusion_engine.py         # Fusion des scores
│   │   │   └── orchestrator.py          # Orchestration pipeline
│   │   └── utils/
│   │       └── helpers.py       # Fonctions utilitaires
│   └── requirements.txt
├── frontend/
│   └── static/
│       ├── index.html           # Interface web
│       ├── css/
│       │   └── style.css        # Styles
│       └── js/
│           └── app.js           # Logique frontend
└── .env
```

---

## 📦 Dépendances (requirements.txt)

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.9.0
pydantic-settings==2.5.0
python-multipart==0.0.12
python-dotenv==1.0.0
httpx==0.27.0
yt-dlp==2024.10.22
Pillow==11.0.0
ffmpeg-python==0.2.0
google-api-python-client==2.130.0
redis==5.1.0
aiofiles==24.1.0
```

---

## 🔧 Configuration (backend/app/core/config.py)

**ATTENTION : Utiliser uniquement des ESPACES (4 espaces), JAMAIS de tabs**

```python
"""
Configuration avec Pydantic Settings v2
"""
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "YouTube Highlight Extractor"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Serveur
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    # API Keys
    GROQ_API_KEY: Optional[str] = None
    YOUTUBE_API_KEY: Optional[str] = None
    
    # Configuration Groq
    GROQ_MODEL_VISION: str = "llama-3.2-11b-vision-preview"
    GROQ_MODEL_WHISPER: str = "whisper-large-v3"
    GROQ_MAX_TOKENS: int = 800
    GROQ_TEMPERATURE: float = 0.2
    GROQ_TIMEOUT: int = 30
    
    # Stockage
    UPLOAD_DIR: Path = Path("./tmp/uploads")
    OUTPUT_DIR: Path = Path("./tmp/output")
    CACHE_DIR: Path = Path("./tmp/cache")
    COOKIES_DIR: Path = Path("./tmp/cookies")
    
    # Analyse par défaut
    DEFAULT_VISION_INTERVAL: int = 60  # secondes
    DEFAULT_MAX_CLIPS: int = 20
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for dir_path in [self.UPLOAD_DIR, self.OUTPUT_DIR, self.CACHE_DIR, self.COOKIES_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

---

## 🎥 Service 1: Video Downloader (video_downloader.py)

### Responsabilités
- Télécharger les métadonnées vidéo (titre, durée, description)
- Télécharger la vidéo en qualité 720p max
- Supporter les cookies pour vidéos restreintes
- Extraire les frames à intervalles réguliers

### Fonctions Principales

```python
class VideoDownloader:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
    
    async def get_video_info(self, url: str, use_cookies: bool = False, cookies_path: Optional[str] = None) -> dict:
        """
        Récupère les métadonnées de la vidéo SANS la télécharger
        Retourne: {title, duration, description, thumbnail, video_id}
        """
        
    async def download_video(self, url: str, quality: str = "720p", use_cookies: bool = False, cookies_path: Optional[str] = None) -> Path:
        """
        Télécharge la vidéo complète
        Retourne le chemin du fichier téléchargé
        """
        
    async def extract_frames(self, video_path: Path, interval_seconds: int = 60, max_frames: int = 50) -> List[Tuple[Path, float]]:
        """
        Extrait des frames à intervalles réguliers
        Retourne: [(frame_path, timestamp), ...]
        """
        
    def _save_cookies_temp(self, cookies_content: str) -> str:
        """
        Sauvegarde les cookies en format Netscape
        Supporte: JSON (export navigateur) ou texte brut
        """
```

### Configuration yt-dlp
```python
ydl_opts = {
    "quiet": True,
    "no_warnings": True,
    "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "outtmpl": str(self.output_dir / "%(id)s.%(ext)s"),
    "cookies": cookies_path if use_cookies else None,
    "merge_output_format": "mp4",
}
```

---

## 👁️ Service 2: Vision Analyzer (vision_analyzer.py)

### API Groq Vision - Llama 3.2 11B Vision

**URL de base**: `https://api.groq.com/openai/v1`

### Structure de la Classe

```python
class VisionAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = "llama-3.2-11b-vision-preview"
    
    async def analyze_frame(self, image_path: Path, timestamp: float) -> dict:
        """
        Analyse une frame avec Groq Vision
        Retourne: {
            "timestamp": float,
            "is_highlight": bool,
            "score": float (0-10),
            "reasons": List[str],
            "emotions": List[str],
            "visual_elements": List[str],
            "suggested_title": str
        }
        """
```

### Format de la Requête API

```python
payload = {
    "model": "llama-3.2-11b-vision-preview",
    "messages": [
        {
            "role": "system",
            "content": "Tu es un expert en analyse de contenu vidéo..."
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyse cette image"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                        "detail": "high"
                    }
                }
            ]
        }
    ],
    "max_tokens": 800,
    "temperature": 0.2
}
```

### Prompt Système

```
Tu es un expert en analyse de contenu vidéo YouTube.

Analyse cette image et identifie si elle contient un moment fort potentiel.

Un moment fort se caractérise par:
- Une action intense ou spectaculaire
- Une réaction émotionnelle forte
- Un changement de rythme visuel
- Un contenu particulièrement engageant
- Une révélation ou surprise

Réponds en JSON avec ce format:
{
    "is_highlight": true/false,
    "score": 0-10,
    "reasons": ["raison1", "raison2"],
    "emotions": ["emotion1"],
    "visual_elements": ["element1"],
    "suggested_title": "Titre"
}
```

### Encodage Image

```python
def _encode_image(self, image_path: Path) -> str:
    """
    Encode l'image en base64 JPEG
    - Resize max 1024px
    - Convertit en RGB
    - Qualité 85%
    """
```

---

## 🎤 Service 3: Transcript Analyzer (transcript_analyzer.py)

### API Groq Whisper

**IMPORTANT**: Ce service est OBLIGATOIRE, pas optionnel

### Structure

```python
class TranscriptAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = "whisper-large-v3"
    
    async def transcribe(self, audio_path: Path) -> dict:
        """
        Transcrit l'audio avec Groq Whisper
        Retourne: {
            "text": str,
            "segments": [{"start": float, "end": float, "text": str}],
            "language": str
        }
        """
```

### Requête API

```python
# Multipart/form-data
files = {
    "file": ("audio.mp3", audio_data, "audio/mpeg"),
    "model": (None, "whisper-large-v3"),
    "response_format": (None, "verbose_json")
}

headers = {
    "Authorization": f"Bearer {self.api_key}"
}

response = await httpx.AsyncClient().post(
    f"{self.base_url}/audio/transcriptions",
    files=files,
    headers=headers,
    timeout=300.0
)
```

### Analyse des Segments

```python
def analyze_transcript(self, transcript: dict) -> List[dict]:
    """
    Analyse le transcript pour détecter les moments forts
    Critères:
    - Mots-clés: "incroyable", "wow", "regardez", "c'est fou"
    - Exclamations, rires
    - Questions rhétoriques
    - Changements de ton
    """
```

---

## 💬 Service 4: Comment Analyzer (comment_analyzer.py)

### YouTube Data API v3

### Structure

```python
class CommentAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
    
    async def get_comments(self, video_id: str, max_comments: int = 500) -> List[dict]:
        """
        Récupère les commentaires
        Retourne: [{text, likes, timestamp, author}]
        """
```

### Analyse des Commentaires

```python
def analyze_comments(self, comments: List[dict]) -> dict:
    """
    Analyse pour extraire:
    - Timestamps mentionnés ("à 2:30 c'est génial")
    - Sentiment global
    - Mots-clés récurrents
    - Moments demandés par la communauté
    """
```

---

## 🔀 Service 5: Fusion Engine (fusion_engine.py)

### Algorithme de Fusion

```python
class FusionEngine:
    def __init__(self):
        # Poids par source
        self.weights = {
            "vision": 0.35,
            "transcript": 0.30,
            "comments": 0.20,
            "chapters": 0.15
        }
    
    def combine_scores(self, analyses: dict) -> List[dict]:
        """
        Combine les scores de toutes les sources
        
        Analyse:
        {
            "vision": [{timestamp, score, ...}],
            "transcript": [{timestamp, score, ...}],
            "comments": [{timestamp, score, ...}]
        }
        
        Algorithme:
        1. Regrouper par fenêtre temporelle (±10s)
        2. Score pondéré = Σ(score_source × poids)
        3. Normaliser 0-10
        4. Filtrer > seuil (6.0)
        5. Éviter chevauchements
        """
```

---

## 🎼 Service 6: Orchestrator (orchestrator.py)

### Pipeline d'Analyse

```python
class AnalysisOrchestrator:
    def __init__(self, config: Settings):
        self.downloader = VideoDownloader(config.OUTPUT_DIR)
        self.vision = VisionAnalyzer(config.GROQ_API_KEY)
        self.transcript = TranscriptAnalyzer(config.GROQ_API_KEY)
        self.comments = CommentAnalyzer(config.YOUTUBE_API_KEY)
        self.fusion = FusionEngine()
        self.jobs = {}  # Stockage en mémoire des jobs
    
    async def analyze(self, video_url: str, config: dict, progress_callback: callable) -> dict:
        """
        Pipeline complet:
        
        1. Métadonnées (5%)
           └─ get_video_info()
        
        2. Téléchargement (20%)
           └─ download_video()
        
        3. Vision (30%)
           └─ extract_frames()
           └─ analyze_frame() pour chaque frame
        
        4. Transcription OBLIGATOIRE (25%)
           └─ Extraire audio avec ffmpeg
           └─ transcribe()
        
        5. Commentaires (10%)
           └─ get_comments()
        
        6. Fusion (10%)
           └─ combine_scores()
        
        Retourne: {
            "video_id": str,
            "title": str,
            "highlights": [{start, end, score, title, sources}],
            "metadata": {...}
        }
        """
```

---

## 🌐 API Routes (backend/app/api/routes.py)

### Endpoints

```python
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Montage statique
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

@app.get("/")
async def root():
    return FileResponse("frontend/static/index.html")

@app.get("/api/v1/health")
async def health():
    return {"status": "healthy", "version": "2.0.0"}

@app.post("/api/v1/analyze")
async def analyze(
    video_url: str = Form(...),
    enable_vision: bool = Form(True),
    enable_transcript: bool = Form(True),
    enable_comments: bool = Form(True),
    use_cookies: bool = Form(False),
    cookies_file: Optional[UploadFile] = File(None)
):
    """
    Lance l'analyse
    Retourne: {"job_id": "uuid"}
    """

@app.get("/api/v1/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """
    Retourne le statut du job
    {
        "job_id": str,
        "status": "pending|downloading|analyzing|completed|failed",
        "progress": 0-100,
        "message": str
    }
    """

@app.get("/api/v1/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """
    Retourne les résultats complets
    """

@app.get("/api/v1/jobs")
async def list_jobs():
    """
    Liste tous les jobs
    """

@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Supprime un job
    """
```

---

## 🎨 Frontend (frontend/static/)

### index.html

Structure principale :
- Header avec titre
- Formulaire avec:
  - Input URL YouTube
  - Checkboxes: Vision, Transcription, Commentaires
  - Upload cookies (optionnel)
  - Options avancées (intervalles, durée)
- Barre de progression
- Section résultats avec:
  - Stats (nombre de highlights, durée totale)
  - Liste des highlights avec timestamps
  - Export JSON / Script FFmpeg
- Historique des jobs

### app.js

Fonctions principales :
```javascript
// Soumission formulaire
async function submitAnalysis() {
    const formData = new FormData();
    // Ajouter tous les champs
    const response = await fetch('/api/v1/analyze', {
        method: 'POST',
        body: formData
    });
    const {job_id} = await response.json();
    startPolling(job_id);
}

// Polling du statut
function startPolling(job_id) {
    const interval = setInterval(async () => {
        const status = await fetch(`/api/v1/jobs/${job_id}/status`);
        const data = await status.json();
        
        updateProgress(data.progress, data.message);
        
        if (data.status === 'completed') {
            clearInterval(interval);
            loadResults(job_id);
        } else if (data.status === 'failed') {
            clearInterval(interval);
            showError(data.error);
        }
    }, 2000);
}

// Affichage résultats
function displayResults(data) {
    // Créer les cartes pour chaque highlight
    // Afficher timestamp cliquable
    // Boutons export
}
```

### Styles CSS

- Design moderne avec gradients
- Cards avec ombres
- Animations de progression
- Responsive mobile
- Thème cohérent (violet/bleu)

---

## 📝 Modèles Pydantic (backend/app/models/schemas.py)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum

class AnalysisStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
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
    sources: Dict[str, float]  # Score par source
    thumbnail: Optional[str] = None

class AnalysisResult(BaseModel):
    job_id: str
    video_id: str
    title: str
    duration: float
    highlights: List[HighlightMoment]
    metadata: Dict[str, any]
    created_at: datetime

class JobStatus(BaseModel):
    job_id: str
    status: AnalysisStatus
    progress: float = Field(..., ge=0, le=100)
    message: str
    created_at: datetime
    error: Optional[str] = None
```

---

## ⚠️ Points Critiques à Respecter

### 1. Indentation Python
- **UNIQUEMENT des espaces (4 espaces)**
- **JAMAIS de tabs**
- Configurer l'éditeur pour "spaces"

### 2. Gestion des Erreurs
```python
try:
    result = await service.analyze()
except Exception as e:
    logger.error(f"Erreur: {e}")
    raise HTTPException(status_code=500, detail=str(e))
```

### 3. Cookies YouTube
- Supporter le format Netscape ET JSON
- Fichier temporaire supprimé après usage

### 4. Transcription OBLIGATOIRE
- Ne pas rendre ce service optionnel
- Utiliser Groq Whisper (pas AssemblyAI)

### 5. Modèle Vision
- Utiliser **Groq Llama 3.2 11B Vision**
- PAS NVIDIA Kimi K2.5 (texte seulement)

### 6. Tests sans Docker
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: .\venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend
# Les fichiers statiques sont servis par FastAPI
# Accès: http://localhost:8000
```

---

## 🚀 Lancement du Projet

### Développement

```bash
# 1. Créer environnement virtuel
python -m venv venv
source venv/bin/activate

# 2. Installer dépendances
pip install -r backend/requirements.txt

# 3. Configurer .env
GROQ_API_KEY=gsk_xxxxx
YOUTUBE_API_KEY=AIzaxxxxx

# 4. Lancer
cd backend
uvicorn app.main:app --reload --port 8000
```

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 📊 Format de Sortie JSON Final

```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "duration": 240,
  "highlights": [
    {
      "start": 45.2,
      "end": 120.5,
      "duration": 75.3,
      "score": 8.5,
      "title": "Moment incroyable",
      "sources": {
        "vision": 9.0,
        "transcript": 8.0,
        "comments": 8.5
      },
      "thumbnail": "base64..."
    }
  ],
  "metadata": {
    "total_highlights": 5,
    "total_duration": 320.5,
    "analysis_time": 45.2
  }
}
```

---

## 🔍 Tests à Effectuer

1. **Health Check**: `GET /api/v1/health`
2. **Analyse Simple**: Vidéo publique < 5 min
3. **Analyse avec Cookies**: Vidéo restreinte
4. **Annulation**: Arrêter un job en cours
5. **Export**: Télécharger JSON et script FFmpeg

---

## 📚 Ressources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Groq API Docs](https://console.groq.com/docs)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [YouTube Data API](https://developers.google.com/youtube/v3)

---

## ✅ Checklist de Validation

- [ ] Python 3.11 installé
- [ ] Dépendances installées sans erreur
- [ ] .env configuré avec les clés API
- [ ] Serveur démarre sur localhost:8000
- [ ] Interface accessible dans le navigateur
- [ ] Health check fonctionne
- [ ] Analyse d'une vidéo test fonctionne
- [ ] Transcription Whisper fonctionne
- [ ] Vision Llama fonctionne
- [ ] Fusion des scores fonctionne
- [ ] Export JSON fonctionne
- [ ] Pas d'erreurs d'indentation
- [ ] Code utilise uniquement des espaces

---

**Ce document contient TOUTES les spécifications nécessaires pour reconstruire le projet de zéro. Suivre scrupuleusement les instructions d'indentation et les configurations API.**
