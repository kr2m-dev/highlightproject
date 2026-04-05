"""
Analyseur de frames vidéo avec support multi-provider (Groq, NVIDIA Kimi, GLM)
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
    def __init__(self, api_key: str, provider: str = "nvidia"):
        self.api_key = api_key
        self.provider = provider
        
        if provider == "nvidia":
            # NVIDIA API avec modèles multimodaux
            self.base_url = "https://integrate.api.nvidia.com/v1"
            self.model = "meta/llama-3.2-11b-vision-instruct"  # Multimodal
            # Alternatives: "microsoft/phi-3-vision-128k-instruct", "nvidia/neva-22b"
        else:
            # Groq API
            self.base_url = "https://api.groq.com/openai/v1"
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

IMPORTANT: Tu DOIS répondre UNIQUEMENT avec un objet JSON valide, sans aucun texte avant ou après.

Format de réponse obligatoire (JSON uniquement):
{"is_highlight": false, "score": 5, "reasons": ["raison1"], "emotions": [], "visual_elements": ["element1"], "suggested_title": "Titre"}

Exemple de réponse correcte:
{"is_highlight": true, "score": 8, "reasons": ["Action intense visible", "Expression faciale marquée"], "emotions": ["surprise"], "visual_elements": ["mouvement rapide"], "suggested_title": "Moment de réaction"}"""

    async def analyze_frame(self, image_path: Path, timestamp: float) -> Dict[str, Any]:
        """
        Analyse une frame avec l'API Vision
        
        Args:
            image_path: Chemin vers l'image
            timestamp: Timestamp de la frame en secondes
            
        Returns:
            Dict avec: timestamp, is_highlight, score, reasons, emotions, visual_elements, suggested_title
        """
        if not self.api_key:
            logger.warning("Pas de clé API - retourne un score par défaut")
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
            
            logger.info(f"Analyzing frame with {self.provider} - model: {self.model}")
            logger.info(f"Image size: {len(image_base64)} bytes (base64)")

            # Format du message pour Kimi (vision)
            messages = [
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
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }

            # Headers selon le provider
            if self.provider == "nvidia":
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            else:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                }

            timeout = 120.0 if self.provider == "nvidia" else 60.0
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                logger.info(f"API Response Status: {response.status_code}")
                logger.info(f"API Response Body: {response.text[:500]}")

                if response.status_code != 200:
                    logger.error(f"Erreur API {self.provider}: {response.status_code} - {response.text}")
                    return self._default_result(timestamp, f"Erreur API: {response.status_code}")

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Essayer de parser le JSON
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
                    # Si pas de JSON, analyser le texte pour extraire les infos
                    logger.warning(f"Erreur parsing JSON, analyse texte: {e}")
                    return self._parse_text_response(content, timestamp)

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

    def _parse_text_response(self, text: str, timestamp: float) -> Dict[str, Any]:
        """
        Parse une réponse texte quand le modèle ne renvoie pas de JSON
        Analyse le contenu pour déterminer si c'est un highlight
        """
        text_lower = text.lower()
        
        # Mots-clés positifs
        positive_keywords = ["spectaculaire", "intense", "émotionnel", "surprenant", 
                            "engageant", "intéressant", "moment fort", "révélation"]
        
        # Mots-clés négatifs
        negative_keywords = ["pas de moment fort", "ne contient pas", "pas d'action",
                            "pas intéressant", "flou", "pas de détails"]
        
        # Calculer un score basé sur les mots-clés
        score = 5.0
        reasons = []
        
        positive_count = sum(1 for kw in positive_keywords if kw in text_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in text_lower)
        
        if positive_count > 0:
            score += positive_count * 1.0
            reasons.append(f"Éléments positifs détectés: {positive_count}")
        
        if negative_count > 0:
            score -= negative_count * 1.0
            reasons.append(f"Éléments négatifs détectés: {negative_count}")
        
        score = max(0, min(10, score))
        is_highlight = score >= 6.0
        
        # Extraire un titre suggéré du texte
        lines = text.split('\n')
        title = "Moment analysé"
        for line in lines[:3]:
            if len(line.strip()) > 10 and not line.startswith('*'):
                title = line.strip()[:50]
                break
        
        return {
            "timestamp": timestamp,
            "is_highlight": is_highlight,
            "score": score,
            "reasons": reasons if reasons else ["Analyse textuelle"],
            "emotions": [],
            "visual_elements": [],
            "suggested_title": title
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
