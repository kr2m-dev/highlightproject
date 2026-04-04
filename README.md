# Video Highlight Extractor

Extract automatic highlights from your videos using AI (Groq Vision + Whisper).

## Features

- **Upload videos** via file upload or server path (for AWS deployment)
- **Visual analysis** using Groq Vision API (Llama 3.2 11B Vision)
- **Audio transcription** using Groq Whisper
- **Multi-source fusion** to combine visual and audio highlights
- **Modern web interface** with real-time progress

## Installation

```bash
# Clone repository
git clone https://github.com/kr2m-dev/highlightproject.git
cd highlightproject

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

## Configuration

Create `.env` file at project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

Get your API key at: https://console.groq.com/keys

## Usage

### Start server

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### Access

- **Web Interface:** http://127.0.0.1:8000
- **API Docs:** http://127.0.0.1:8000/docs

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/upload` | POST | Upload video for analysis |
| `/api/v1/jobs/{job_id}/status` | GET | Get job status |
| `/api/v1/jobs/{job_id}/result` | GET | Get analysis results |
| `/api/v1/jobs` | GET | List all jobs |
| `/api/v1/jobs/{job_id}` | DELETE | Delete a job |

## Upload Options

### 1. File Upload (for local testing)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/upload \
  -F "video=@/path/to/video.mp4" \
  -F "vision_interval=5" \
  -F "max_clips=20"
```

### 2. Server Path (for AWS deployment)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/upload \
  -F "video_path=/home/user/videos/my_video.mp4" \
  -F "vision_interval=5" \
  -F "max_clips=20"
```

## Requirements

- Python 3.11+
- FFmpeg (for video processing)
- Groq API key

## Tech Stack

- **Backend:** FastAPI, Python
- **AI:** Groq Vision (Llama 3.2 11B), Whisper
- **Frontend:** Vanilla HTML/CSS/JavaScript
- **Video Processing:** FFmpeg

## License

MIT
