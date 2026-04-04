# Problèmes connus et solutions

## 1. Modèle Vision décommissionné ❌

### Erreur
```
The model `llama-3.2-11b-vision-preview` has been decommissioned
```

### Cause
Groq a retiré le modèle `llama-3.2-11b-vision-preview`.

### Solutions possibles

#### Option A: Utiliser un autre fournisseur (recommandé)
- **OpenAI GPT-4 Vision** (`gpt-4o`, `gpt-4-vision-preview`)
- **Google Gemini Vision** (`gemini-pro-vision`)
- **Anthropic Claude 3** (`claude-3-opus`, `claude-3-sonnet`)

#### Option B: Désactiver l'analyse visuelle
Utiliser uniquement la transcription Whisper pour détecter les highlights.

#### Option C: Vérifier les nouveaux modèles Groq
Aller sur https://console.groq.com/docs/deprecations pour voir les modèles recommandés.

---

## 2. Audio trop volumineux pour Whisper ❌

### Erreur
```
Erreur API Whisper: 413 - Request Entity Too Large
```

### Cause
L'API Groq Whisper a une limite de taille de fichier (25 MB max).

### Solutions

#### Option A: Compresser l'audio avant envoi
```python
# Dans transcript_analyzer.py, réduire la qualité audio
ffmpeg -i audio.mp3 -ar 16000 -ac 1 -b:a 64k audio_compressed.mp3
```

#### Option B: Segmenter l'audio
Découper la vidéo en segments de 10 minutes max.

#### Option C: Utiliser Whisper local
Installer `whisper` localement sur le serveur:
```bash
pip install openai-whisper
whisper audio.mp3 --model medium
```

---

## 3. Problème AWS / Rate Limiting ⚠️

### Erreur
Groq peut bloquer les requêtes venant d'IP AWS (détecté comme bot).

### Solutions
- Utiliser un proxy résidentiel
- Ajouter des headers "humains" (déjà fait)
- Héberger sur une VPS résidentielle

---

## 4. Configuration frontend ⚠️

### Problème
Le frontend envoie les requêtes à `http://127.0.0.1:8000` au lieu du domaine.

### Solution
Modifier `frontend/static/js/app.js`:
```javascript
const API_URL = window.location.origin; // Utilise le domaine actuel
```

---

## Corrections à appliquer

### 1. Mettre à jour le modèle Vision

Vérifier sur Groq Console les modèles disponibles:
```bash
curl http://127.0.0.1:8000/api/v1/debug/groq-models
```

### 2. Compresser l'audio

Ajouter une compression dans `helpers.py` avant transcription.

### 3. Configurer le domaine

Mettre à jour l'URL de l'API dans le frontend.

---

## Status actuel

| Fonctionnalité | Status | Note |
|----------------|--------|------|
| Upload vidéo | ✅ OK | Fonctionne |
| Extraction frames | ✅ OK | FFmpeg OK |
| Analyse Vision | ❌ KO | Modèle décommissionné |
| Transcription | ❌ KO | Audio trop grand |
| Fusion | ⏸️ | En attente des analyses |
| Frontend | ⚠️ | CORS OK, URL à configurer |
