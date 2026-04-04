"""
Analyseur de frames vidéo avec Groq Vision API (Llama 3.2 11B Vision)
"""
import base64
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx

from PIL import Image

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1"
        # Modèle vision mis à jour (llama-3.2-11b-vision-preview décommissionné)
        # Voir: https://console.groq.com/docs/deprecations
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        self.max_tokens = 800
        self.temperature = 0.2

    def _encode_image(self, image_path: Path, max_size: int = 1024, quality: int = 85) -> str:
        """
        Encode une image en base64 JPEG
        - Redimensionne si nécessaire (max 1024px)
        - Convertit en RGB
        - Qualité 85%
        """
        try:
            with Image.open(image_path) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                
                width, height = img.size
                if max(width, height) > max_size:
                    ratio = max_size / max(width, height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                from io import BytesIO
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=quality)
                return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Erreur encodage image {image_path}: {e}")
            raise

    def _build_prompt(self) -> str:
        """Construit le prompt pour l'analyse"""
        return """Tu es un expert en analyse de contenu vidéo YouTube.

Analyse cette image et identifie si elle contient un moment fort potentiel.

Un moment fort se caractérise par:
- Une action intense ou spectaculaire
- Une réaction émotionnelle forte
- Un changement de rythme visuel
- Un contenu particulièrement engageant
- Une révélation ou surprise

Réponds UNIQUEMENT en JSON valide avec ce format exact:
{
    "is_highlight": true ou false,
    "score": nombre de 0 à 10,
    "reasons": ["raison1", "raison2"],
    "emotions": ["emotion1"],
    "visual_elements": ["element1"],
    "suggested_title": "Titre court du moment"
}"""

    async def analyze_frame(self, image_path: Path, timestamp: float) -> Dict[str, Any]:
        """
        Analyse une frame avec Groq Vision
        
        Args:
            image_path: Chemin vers l'image
            timestamp: Timestamp de la frame en secondes
            
        Returns:
            Dict avec: timestamp, is_highlight, score, reasons, emotions, visual_elements, suggested_title
        """
        if not self.api_key:
            logger.warning("Pas de clé API Groq - retourne un score par défaut")
            return {
                "timestamp": timestamp,
                "is_highlight": False,
                "score": 5.0,
                "reasons": ["Mode sans API - score par défaut"],
                "emotions": [],
                "visual_elements": [],
                "suggested_title": "Frame non analysée"
            }

        try:
            image_base64 = self._encode_image(image_path)
            
            logger.info(f"Analyzing frame with model: {self.model}")
            logger.info(f"Image size: {len(image_base64)} bytes (base64)")

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": self._build_prompt()
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyse cette image et évalue son potentiel comme moment fort vidéo."},
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
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9,fr;q=0.8"
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                logger.info(f"API Response Status: {response.status_code}")
                logger.info(f"API Response Body: {response.text[:500]}")

                if response.status_code != 200:
                    logger.error(f"Erreur API Groq: {response.status_code} - {response.text}")
                    return self._default_result(timestamp, f"Erreur API: {response.status_code}")

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                try:
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    if json_start != -1 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        result = json.loads(json_str)
                    else:
                        result = json.loads(content)
                    
                    return {
                        "timestamp": timestamp,
                        "is_highlight": result.get("is_highlight", False),
                        "score": float(result.get("score", 5.0)),
                        "reasons": result.get("reasons", []),
                        "emotions": result.get("emotions", []),
                        "visual_elements": result.get("visual_elements", []),
                        "suggested_title": result.get("suggested_title", "Moment non nommé")
                    }
                except json.JSONDecodeError as e:
                    logger.warning(f"Erreur parsing JSON: {e} - Content: {content}")
                    return self._default_result(timestamp, "Erreur parsing réponse")

        except Exception as e:
            logger.error(f"Erreur analyse frame {image_path}: {e}")
            return self._default_result(timestamp, str(e))

    def _default_result(self, timestamp: float, error: str) -> Dict[str, Any]:
        """Retourne un résultat par défaut en cas d'erreur"""
        return {
            "timestamp": timestamp,
            "is_highlight": False,
            "score": 5.0,
            "reasons": [f"Erreur: {error}"],
            "emotions": [],
            "visual_elements": [],
            "suggested_title": "Erreur d'analyse"
        }

    async def analyze_frames(
        self,
        frames: List[tuple],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyse plusieurs frames
        
        Args:
            frames: Liste de (image_path, timestamp)
            progress_callback: Fonction appelée avec (current, total, message)
            
        Returns:
            Liste de résultats d'analyse
        """
        results = []
        total = len(frames)
        
        for i, (image_path, timestamp) in enumerate(frames):
            if progress_callback:
                progress_callback(i, total, f"Analyse frame {i+1}/{total}")
            
            result = await self.analyze_frame(image_path, timestamp)
            results.append(result)
            
            logger.info(f"Frame {i+1}/{total}: score={result['score']}, highlight={result['is_highlight']}")
        
        return results
