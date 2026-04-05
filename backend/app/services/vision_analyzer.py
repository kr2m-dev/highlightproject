"""
Analyseur de frames vidéo avec Groq Vision API
Gère le rate limiting avec retry automatique
"""
import base64
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx

from PIL import Image

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        self.max_tokens = 400  # Réduit pour économiser les tokens
        self.temperature = 0.2
        self.max_retries = 3
        self.retry_delay = 3.0  # Secondes entre retries
        self.request_delay = 2.0  # Délai entre chaque requête

    def _encode_image(self, image_path: Path, max_size: int = 512, quality: int = 70) -> str:
        """
        Encode une image en base64 JPEG
        - Redimensionne si nécessaire (max 512px pour économiser tokens)
        - Convertit en RGB
        - Qualité 70%
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
        """Construit un prompt court pour économiser les tokens"""
        return """Analyse cette image. Est-ce un moment fort vidéo?
Réponds UNIQUEMENT en JSON:
{"is_highlight": false, "score": 5, "reasons": [], "suggested_title": "Titre"}"""

    async def analyze_frame(self, image_path: Path, timestamp: float) -> Dict[str, Any]:
        """
        Analyse une frame avec Groq Vision
        Gère le rate limiting avec retry automatique
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

        for attempt in range(self.max_retries):
            try:
                image_base64 = self._encode_image(image_path)
                
                logger.info(f"Analyzing frame (attempt {attempt+1}/{self.max_retries}): {image_path.name}")

                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": self._build_prompt()},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}"
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
                    "Content-Type": "application/json"
                }

                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers
                    )
                    
                    if response.status_code == 429:
                        # Rate limit - attendre et retry
                        retry_after = float(response.json().get("error", {}).get("message", "").split("try again in ")[1].split("s")[0]) if "try again in" in response.text else self.retry_delay
                        logger.warning(f"Rate limit atteint, attente {retry_after:.1f}s avant retry...")
                        await asyncio.sleep(retry_after + 1)
                        continue
                    
                    if response.status_code != 200:
                        logger.error(f"Erreur API Groq: {response.status_code} - {response.text}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
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
                        logger.warning(f"Erreur parsing JSON: {e}")
                        return self._default_result(timestamp, "Erreur parsing réponse")

            except Exception as e:
                logger.error(f"Erreur analyse frame {image_path}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                return self._default_result(timestamp, str(e))
        
        return self._default_result(timestamp, "Max retries atteint")

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
        Analyse plusieurs frames avec délai entre chaque
        """
        results = []
        total = len(frames)
        
        for i, (image_path, timestamp) in enumerate(frames):
            if progress_callback:
                progress_callback(i, total, f"Analyse frame {i+1}/{total}")
            
            result = await self.analyze_frame(image_path, timestamp)
            results.append(result)
            
            logger.info(f"Frame {i+1}/{total}: score={result['score']}, highlight={result['is_highlight']}")
            
            # Délai entre les frames pour éviter le rate limiting
            if i < total - 1:
                await asyncio.sleep(self.request_delay)
        
        return results
