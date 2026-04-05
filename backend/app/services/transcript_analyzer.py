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
        - Mots-clés positifs
        - Exclamations, rires
        - Questions
        - Répétitions (indiquent l'importance)
        - Longueur des segments
        """
        highlights = []
        
        # Mots-clés forts (score élevé)
        strong_keywords = [
            "incroyable", "wow", "oh my god", "c'est fou", "extraordinaire",
            "magnifique", "époustouflant", "incroyable", "incroyable",
            "unbelievable", "amazing", "awesome", "incredible", "insane",
            "crazy", "fantastic", "superb", "brilliant", "extraordinary"
        ]
        
        # Mots-clés moyens
        medium_keywords = [
            "super", "génial", "cool", "bien", "bon", "superbe",
            "great", "good", "nice", "cool", "awesome", "perfect",
            "yes", "yeah", "ouais", "ok", "d'accord"
        ]
        
        # Marqueurs d'émotion
        emotion_markers = [
            ("!", 0.5),  # Exclamation
            ("?", 0.3),  # Question
            ("rire", 1.0),
            ("lol", 0.8),
            ("haha", 0.8),
            ("mdr", 0.8)
        ]
        
        segments = transcript.get("segments", [])
        
        for i, segment in enumerate(segments):
            text = segment.get("text", "")
            text_lower = text.lower()
            start = segment.get("start", 0)
            
            score = 0
            reasons = []
            
            # Vérifier mots-clés forts
            for keyword in strong_keywords:
                if keyword in text_lower:
                    score += 2.0
                    reasons.append(f"Mot-clé fort: '{keyword}'")
            
            # Vérifier mots-clés moyens
            for keyword in medium_keywords:
                if keyword in text_lower:
                    score += 1.0
                    reasons.append(f"Mot-clé: '{keyword}'")
            
            # Vérifier marqueurs d'émotion
            for marker, points in emotion_markers:
                count = text_lower.count(marker)
                if count > 0:
                    score += count * points
                    reasons.append(f"Émotion: {marker} (x{count})")
            
            # Segment long = potentiellement important
            duration = segment.get("end", 0) - segment.get("start", 0)
            if duration > 10:
                score += 0.5
                reasons.append("Segment long")
            
            # Vérifier la position (intro/outro moins importantes)
            total_segments = len(segments)
            if i < total_segments * 0.1:  # Premier 10%
                score *= 0.8  # Réduire l'importance de l'intro
            elif i > total_segments * 0.9:  # Dernier 10%
                score *= 0.8  # Réduire l'importance de l'outro
            else:
                score *= 1.1  # Augmenter légèrement le milieu
            
            # Score minimum pour être un highlight
            if score > 0:
                highlights.append({
                    "timestamp": start,
                    "score": min(score, 10),
                    "reasons": reasons,
                    "text": text[:100] if len(text) > 100 else text,
                    "source": "transcript"
                })
        
        # Trier par score et garder les meilleurs
        highlights.sort(key=lambda x: x["score"], reverse=True)
        
        # Éviter les chevauchements (garder max 1 highlight par tranche de 30s)
        filtered = []
        for h in highlights:
            if not any(abs(h["timestamp"] - existing["timestamp"]) < 30 for existing in filtered):
                filtered.append(h)
        
        # Re-trier par timestamp
        filtered.sort(key=lambda x: x["timestamp"])
        
        return filtered

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
