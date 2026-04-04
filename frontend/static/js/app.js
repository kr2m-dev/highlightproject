const API_URL = 'http://127.0.0.1:8000';

let currentJobId = null;
let pollingInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initFileUpload();
    initAnalyzeButton();
});

function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const tabId = btn.dataset.tab;
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });
}

function initFileUpload() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('videoFile');
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            updateDropZoneText(files[0].name);
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            updateDropZoneText(e.target.files[0].name);
        }
    });
}

function updateDropZoneText(filename) {
    const dropText = document.querySelector('.drop-text');
    dropText.textContent = `✓ ${filename}`;
}

function initAnalyzeButton() {
    const analyzeBtn = document.getElementById('analyzeBtn');
    analyzeBtn.addEventListener('click', startAnalysis);
}

async function startAnalysis() {
    const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
    const enableVision = document.getElementById('enableVision').checked;
    const enableTranscript = document.getElementById('enableTranscript').checked;
    const visionInterval = parseInt(document.getElementById('visionInterval').value) || 5;
    const maxClips = parseInt(document.getElementById('maxClips').value) || 20;
    
    const formData = new FormData();
    formData.append('vision_interval', visionInterval);
    formData.append('max_clips', maxClips);
    formData.append('enable_vision', enableVision);
    formData.append('enable_transcript', enableTranscript);
    
    if (activeTab === 'file') {
        const fileInput = document.getElementById('videoFile');
        if (!fileInput.files.length) {
            alert('Please select a video file');
            return;
        }
        formData.append('video', fileInput.files[0]);
    } else {
        const pathInput = document.getElementById('videoPath');
        const path = pathInput.value.trim();
        if (!path) {
            alert('Please enter a server path');
            return;
        }
        formData.append('video_path', path);
    }
    
    const analyzeBtn = document.getElementById('analyzeBtn');
    analyzeBtn.disabled = true;
    analyzeBtn.querySelector('.btn-text').textContent = '⏳ Uploading...';
    
    try {
        const response = await fetch(`${API_URL}/api/v1/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        showProgress();
        startPolling(currentJobId);
        
    } catch (error) {
        alert(`Error: ${error.message}`);
        analyzeBtn.disabled = false;
        analyzeBtn.querySelector('.btn-text').textContent = '🚀 Start Analysis';
    }
}

function showProgress() {
    document.getElementById('progressSection').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'none';
}

function startPolling(jobId) {
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_URL}/api/v1/jobs/${jobId}/status`);
            const status = await response.json();
            
            updateProgress(status.progress, status.message);
            
            if (status.status === 'completed') {
                stopPolling();
                await loadResults(jobId);
            } else if (status.status === 'failed') {
                stopPolling();
                alert(`Analysis failed: ${status.error}`);
                resetButton();
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 2000);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

function updateProgress(progress, message) {
    document.getElementById('progressFill').style.width = `${progress}%`;
    document.getElementById('progressMessage').textContent = message;
}

async function loadResults(jobId) {
    try {
        const response = await fetch(`${API_URL}/api/v1/jobs/${jobId}/result`);
        const result = await response.json();
        
        displayResults(result);
        resetButton();
        
    } catch (error) {
        alert(`Error loading results: ${error.message}`);
    }
}

function displayResults(result) {
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'block';
    
    document.getElementById('durationValue').textContent = formatDuration(result.duration);
    document.getElementById('framesValue').textContent = result.metadata.frames_extracted || 0;
    document.getElementById('transcriptValue').textContent = result.metadata.transcript_segments || 0;
    document.getElementById('highlightsValue').textContent = result.highlights.length;
    
    const highlightsList = document.getElementById('highlightsList');
    highlightsList.innerHTML = '';
    
    if (result.highlights.length === 0) {
        highlightsList.innerHTML = '<p class="no-highlights">No highlights detected. Try adjusting the analysis options.</p>';
        return;
    }
    
    result.highlights.forEach((highlight, index) => {
        const card = createHighlightCard(highlight, index + 1);
        highlightsList.appendChild(card);
    });
    
    document.getElementById('exportJsonBtn').onclick = () => exportJson(result);
}

function createHighlightCard(highlight, index) {
    const card = document.createElement('div');
    card.className = 'highlight-card';
    
    const sources = Object.entries(highlight.sources)
        .map(([source, score]) => `<span class="source-tag ${source}">${source}: ${score.toFixed(1)}</span>`)
        .join('');
    
    card.innerHTML = `
        <div class="highlight-score">${highlight.score.toFixed(1)}</div>
        <div class="highlight-info">
            <div class="highlight-time">⏱️ ${formatTimestamp(highlight.start)} - ${formatTimestamp(highlight.end)}</div>
            <div class="highlight-title">${escapeHtml(highlight.title)}</div>
            <div class="highlight-sources">${sources}</div>
        </div>
    `;
    
    return card;
}

function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
}

function formatTimestamp(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function exportJson(result) {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `highlights_${result.job_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

function resetButton() {
    const analyzeBtn = document.getElementById('analyzeBtn');
    analyzeBtn.disabled = false;
    analyzeBtn.querySelector('.btn-text').textContent = '🚀 Start Analysis';
}
