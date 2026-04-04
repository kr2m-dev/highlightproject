"""
Utilitaires pour l'extraction de frames vidéo
"""
import subprocess
import asyncio
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class FrameExtractor:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def get_video_duration(self, video_path: Path) -> float:
        """Retourne la durée de la vidéo en secondes"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.error(f"ffprobe error: {stderr.decode()}")
                raise Exception(f"Erreur ffprobe: {stderr.decode()}")
            
            return float(stdout.decode().strip())
        except Exception as e:
            logger.error(f"Erreur récupération durée: {e}")
            raise

    async def extract_frames(
        self,
        video_path: Path,
        interval_seconds: int = 60,
        max_frames: int = 50
    ) -> List[Tuple[Path, float]]:
        """
        Extrait des frames à intervalles réguliers
        Retourne: [(frame_path, timestamp), ...]
        """
        duration = await self.get_video_duration(video_path)
        
        frames_data = []
        frame_dir = self.output_dir / video_path.stem
        frame_dir.mkdir(parents=True, exist_ok=True)
        
        interval = min(interval_seconds, duration / max_frames)
        timestamps = []
        t = 0.0
        while t < duration and len(timestamps) < max_frames:
            timestamps.append(t)
            t += interval
        
        for i, ts in enumerate(timestamps):
            frame_path = frame_dir / f"frame_{i:04d}.jpg"
            
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(ts),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                str(frame_path)
            ]
            
            try:
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0 and frame_path.exists():
                    frames_data.append((frame_path, ts))
                    logger.info(f"Frame extraite: {frame_path} à {ts}s")
                else:
                    logger.warning(f"Erreur extraction frame {i}: {stderr.decode()}")
            except Exception as e:
                logger.error(f"Erreur extraction frame {i}: {e}")
        
        return frames_data

    async def extract_audio(self, video_path: Path, max_size_mb: int = 20) -> Path:
        """
        Extrait l'audio d'une vidéo pour transcription
        Compresse si nécessaire pour respecter la limite de taille
        """
        audio_path = self.output_dir / f"{video_path.stem}.mp3"
        
        # Extraction avec compression pour réduire la taille
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-ar", "16000",  # Taux d'échantillonnage réduit
            "-ac", "1",       # Mono
            "-b:a", "64k",    # Bitrate réduit
            str(audio_path)
        ]
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.error(f"Erreur extraction audio: {stderr.decode()}")
                raise Exception(f"Erreur extraction audio: {stderr.decode()}")
            
            if not audio_path.exists():
                raise Exception("Fichier audio non créé")
            
            logger.info(f"Audio extrait: {audio_path}")
            return audio_path
        except Exception as e:
            logger.error(f"Erreur extraction audio: {e}")
            raise

    async def split_audio(self, audio_path: Path, segment_duration: int = 300) -> list:
        """
        Divise l'audio en segments pour éviter l'erreur 413 (fichier trop grand)
        
        Args:
            audio_path: Chemin vers le fichier audio
            segment_duration: Durée de chaque segment en secondes (défaut: 5 min)
            
        Returns:
            Liste des chemins des segments audio
        """
        duration = await self.get_video_duration(audio_path)
        
        if duration <= segment_duration:
            return [audio_path]
        
        segments = []
        segment_dir = self.output_dir / f"{audio_path.stem}_segments"
        segment_dir.mkdir(parents=True, exist_ok=True)
        
        start = 0
        segment_num = 0
        
        while start < duration:
            segment_path = segment_dir / f"segment_{segment_num:03d}.mp3"
            
            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(audio_path),
                "-ss", str(start),
                "-t", str(segment_duration),
                "-acodec", "copy",
                str(segment_path)
            ]
            
            try:
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0 and segment_path.exists():
                    segments.append(segment_path)
                    logger.info(f"Segment audio créé: {segment_path}")
                else:
                    logger.warning(f"Erreur création segment {segment_num}: {stderr.decode()}")
            except Exception as e:
                logger.error(f"Erreur segmentation audio: {e}")
            
            start += segment_duration
            segment_num += 1
        
        return segments
