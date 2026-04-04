"""
Moteur de fusion pour combiner les scores de différentes sources
"""
import logging
from typing import List, Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class FusionEngine:
    def __init__(self):
        self.weights = {
            "vision": 0.55,
            "transcript": 0.45
        }
        self.time_window = 10.0
        self.min_score_threshold = 3.0

    def combine_scores(
        self,
        vision_highlights: List[Dict[str, Any]],
        transcript_highlights: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Combine les highlights de vision et transcript
        
        Algorithme:
        1. Regrouper par fenêtre temporelle (±10s)
        2. Score pondéré = Σ(score_source × poids)
        3. Normaliser 0-10
        4. Filtrer > seuil (3.0)
        5. Éviter chevauchements
        
        Args:
            vision_highlights: Liste des highlights visuels
            transcript_highlights: Liste des highlights audio
            
        Returns:
            Liste des highlights fusionnés
        """
        time_groups = defaultdict(list)
        
        for h in vision_highlights:
            timestamp = h.get("timestamp", h.get("start", 0))
            time_key = int(timestamp / self.time_window)
            time_groups[time_key].append({
                "timestamp": timestamp,
                "score": h.get("score", 0),
                "source": "vision",
                "title": h.get("suggested_title", h.get("title", "")),
                "reasons": h.get("reasons", []),
                "text": h.get("text", "")
            })
        
        for h in transcript_highlights:
            timestamp = h.get("timestamp", h.get("start", 0))
            time_key = int(timestamp / self.time_window)
            time_groups[time_key].append({
                "timestamp": timestamp,
                "score": h.get("score", 0),
                "source": "transcript",
                "title": h.get("title", ""),
                "reasons": h.get("reasons", []),
                "text": h.get("text", "")
            })
        
        fused_highlights = []
        
        for time_key, highlights in time_groups.items():
            weighted_score = 0
            sources_scores = {}
            reasons = []
            texts = []
            title_parts = []
            
            for h in highlights:
                source = h["source"]
                score = h["score"]
                weight = self.weights.get(source, 0.5)
                
                weighted_score += score * weight
                sources_scores[source] = score
                
                if h.get("reasons"):
                    reasons.extend(h["reasons"])
                if h.get("text"):
                    texts.append(h["text"])
                if h.get("title"):
                    title_parts.append(h["title"])
            
            total_weight = sum(self.weights.values())
            normalized_score = min(weighted_score / total_weight, 10.0)
            
            if normalized_score >= self.min_score_threshold:
                avg_timestamp = sum(h["timestamp"] for h in highlights) / len(highlights)
                
                title = " | ".join(title_parts[:2]) if title_parts else "Moment fort détecté"
                if len(title) > 80:
                    title = title[:77] + "..."
                
                fused_highlights.append({
                    "timestamp": avg_timestamp,
                    "score": normalized_score,
                    "sources": sources_scores,
                    "title": title,
                    "reasons": list(set(reasons)),
                    "text": " ".join(texts[:3])
                })
        
        fused_highlights.sort(key=lambda x: x["timestamp"])
        
        deduplicated = []
        for h in fused_highlights:
            if not deduplicated:
                deduplicated.append(h)
            else:
                last = deduplicated[-1]
                if abs(h["timestamp"] - last["timestamp"]) >= self.time_window:
                    deduplicated.append(h)
                elif h["score"] > last["score"]:
                    deduplicated[-1] = h
        
        logger.info(f"Fusion: {len(vision_highlights)} vision + {len(transcript_highlights)} transcript = {len(deduplicated)} highlights")
        
        return deduplicated

    def get_highlight_confidence(self, highlight: Dict[str, Any]) -> str:
        """
        Retourne le niveau de confiance d'un highlight
        
        Args:
            highlight: Highlight à évaluer
            
        Returns:
            "high", "medium" ou "low"
        """
        score = highlight.get("score", 0)
        sources = highlight.get("sources", {})
        
        if len(sources) >= 2:
            return "high" if score >= 5 else "medium"
        elif score >= 6:
            return "medium"
        else:
            return "low"
