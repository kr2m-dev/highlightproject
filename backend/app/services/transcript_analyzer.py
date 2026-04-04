"""
Analyseur de transcription avec Groq Whisper API
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)


class TranscriptAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = "whisper-large-v3"

    async def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        """
        Transcrit l'audio avec Groq Whisper
        
        Args:
            audio_path: Chemin vers le fichier audio
            
        Returns:
            Dict avec: text, segments, language
        """
        if not self.api_key:
            logger.warning("Pas de clé API Groq - retourne une transcription vide")
            return {
                "text": "",
                "segments": [],
                "language": "unknown"
            }

        if not audio_path.exists():
            raise FileNotFoundError(f"Fichier audio non trouvé: {audio_path}")

        try:
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            files = {
                "file": ("audio.mp3", audio_data, "audio/mpeg"),
                "model": (None, self.model),
                "response_format": (None, "verbose_json")
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9,fr;q=0.8"
            }

            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/audio/transcriptions",
                    files=files,
                    headers=headers
                )

                if response.status_code != 200:
                    logger.error(f"Erreur API Whisper: {response.status_code} - {response.text}")
                    return {
                        "text": "",
                        "segments": [],
                        "language": "unknown",
                        "error": f"Erreur API: {response.status_code}"
                    }

                data = response.json()
                
                segments = []
                for seg in data.get("segments", []):
                    segments.append({
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0),
                        "text": seg.get("text", "")
                    })

                return {
                    "text": data.get("text", ""),
                    "segments": segments,
                    "language": data.get("language", "unknown")
                }

        except Exception as e:
            logger.error(f"Erreur transcription: {e}")
            return {
                "text": "",
                "segments": [],
                "language": "unknown",
                "error": str(e)
            }

    def analyze_transcript(self, transcript: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyse le transcript pour détecter les moments forts
        
        Critères:
        - Mots-clés: "incroyable", "wow", "regardez", "c'est fou", "oh", "yeah"
        - Exclamations, rires
        - Questions rhétoriques
        - Changements de ton
        
        Args:
            transcript: Dict avec text et segments
            
        Returns:
            Liste de moments forts avec timestamp et score
        """
        highlights = []
        
        highlight_keywords = [
            "incroyable", "wow", "regardez", "c'est fou", "oh my god",
            "incroyable", "extraordinaire", "magnifique", "superbe",
            "génial", "fantastique", "époustouflant", "surprenant",
            "yeah", "yes", "oh", "ah", "waouh", "bravo",
            "super", "top", "best", "amazing", "awesome",
            "crazy", "insane", "unbelievable", "incredible"
        ]
        
        for segment in transcript.get("segments", []):
            text = segment.get("text", "").lower()
            start = segment.get("start", 0)
            
            score = 0
            reasons = []
            
            for keyword in highlight_keywords:
                if keyword in text:
                    score += 1.5
                    reasons.append(f"Mot-clé: '{keyword}'")
            
            exclamation_count = text.count("!")
            if exclamation_count > 0:
                score += exclamation_count * 0.5
                reasons.append(f"Exclamations: {exclamation_count}")
            
            text_upper = segment.get("text", "")
            uppercase_ratio = sum(1 for c in text_upper if c.isupper()) / max(len(text_upper), 1)
            if uppercase_ratio > 0.5:
                score += 1
                reasons.append("Ton emphatique (majuscules)")
            
            if score > 0:
                highlights.append({
                    "timestamp": start,
                    "score": min(score, 10),
                    "reasons": reasons,
                    "text": segment.get("text", ""),
                    "source": "transcript"
                })
        
        return highlights

    async def analyze_audio(
        self,
        audio_path: Path,
        progress_callback: Optional[callable] = None,
        segment_duration: int = 300
    ) -> Dict[str, Any]:
        """
        Transcrit et analyse l'audio
        
        Si l'audio est trop grand, le divise en segments

        Args:
            audio_path: Chemin vers le fichier audio
            progress_callback: Fonction de callback pour la progression
            segment_duration: Durée des segments en secondes (pour gros fichiers)

        Returns:
            Dict avec transcript et highlights
        """
        from ..utils.helpers import FrameExtractor
        
        if progress_callback:
            progress_callback(0, 100, "Début de la transcription...")

        # Vérifier la taille du fichier
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        
        if file_size_mb > 20:  # Si > 20 MB, diviser en segments
            logger.info(f"Audio trop grand ({file_size_mb:.1f} MB), division en segments...")
            
            extractor = FrameExtractor(audio_path.parent)
            segments = await extractor.split_audio(audio_path, segment_duration)
            
            all_transcripts = []
            all_highlights = []
            total_segments = len(segments)
            
            for i, segment_path in enumerate(segments):
                if progress_callback:
                    progress = (i / total_segments) * 90
                    progress_callback(int(progress), 100, f"Transcription segment {i+1}/{total_segments}...")
                
                # Calculer l'offset temporel pour ce segment
                time_offset = i * segment_duration
                
                transcript = await self.transcribe(segment_path)
                
                # Ajuster les timestamps avec l'offset
                for seg in transcript.get("segments", []):
                    seg["start"] = seg.get("start", 0) + time_offset
                    seg["end"] = seg.get("end", 0) + time_offset
                
                all_transcripts.append(transcript)
                
                # Analyser les highlights de ce segment
                highlights = self.analyze_transcript(transcript)
                for h in highlights:
                    h["timestamp"] = h.get("timestamp", 0) + time_offset
                all_highlights.extend(highlights)
            
            # Merger tous les transcripts
            merged_transcript = {
                "text": " ".join(t.get("text", "") for t in all_transcripts),
                "segments": [],
                "language": all_transcripts[0].get("language", "unknown") if all_transcripts else "unknown"
            }
            for t in all_transcripts:
                merged_transcript["segments"].extend(t.get("segments", []))
            
            if progress_callback:
                progress_callback(95, 100, "Analyse finale...")
            
            return {
                "transcript": merged_transcript,
                "highlights": all_highlights
            }
        
        else:
            # Fichier assez petit, transcription normale
            transcript = await self.transcribe(audio_path)

            if progress_callback:
                progress_callback(50, 100, "Analyse du transcript...")

            highlights = self.analyze_transcript(transcript)

            if progress_callback:
                progress_callback(100, 100, "Transcription terminée")

            return {
                "transcript": transcript,
                "highlights": highlights
            }
