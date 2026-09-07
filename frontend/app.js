// Global state for pipeline
const state = {
  currentStep: 1,
  sourceUrl: '',
  selectedFormatId: 'best',
  videoInfo: null,
  downloadedFile: null,   // { filepath, filename, filesize_mb, duration }
  transcriptData: null,   // { segments, full_text, language }
  hooks: [],              // candidate clips
  selectedClip: { start: 0.0, end: 30.0, title: '' },
  lastRenderedShort: null,// { filepath, filename, video_url }
  activeGalleryShort: null,
};

function fmtDuration(s) {
  if (!s) return '0:00';
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

function showError(msg) {
  const card = document.getElementById('errorCard');
  const txt = document.getElementById('errorMsg');
  if (!msg) {
    card.classList.add('hidden');
    return;
  }
  txt.textContent = msg;
  card.classList.remove('hidden');
  setTimeout(() => card.classList.add('hidden'), 6000);
}

function switchStep(stepNum) {
  state.currentStep = stepNum;

  // Update sidebar active classes
  const steps = document.querySelectorAll('.steps .step');
  steps.forEach((el, idx) => {
    if (idx + 1 === stepNum) {
      el.classList.add('step-active');
    } else {
      el.classList.remove('step-active');
    }
  });

  // Switch panels
  for (let i = 1; i <= 6; i++) {
    const panel = document.getElementById(`panel-${i}`);
    if (panel) {
      if (i === stepNum) {
        panel.classList.remove('hidden');
      } else {
        panel.classList.add('hidden');
      }
    }
  }

  // Auto-sync inputs
  if (stepNum === 2 && state.downloadedFile) {
    document.getElementById('transcribePathInput').value = state.downloadedFile.filepath;
  } else if (stepNum === 4) {
    const vName = state.downloadedFile ? state.downloadedFile.filename : 'None';
    document.getElementById('renderVideoName').textContent = vName;
    document.getElementById('renderClipTime').textContent =
      `${state.selectedClip.start}s  \u2192  ${state.selectedClip.end}s (Duration: ${(state.selectedClip.end - state.selectedClip.start).toFixed(1)}s)`;
  } else if (stepNum === 5) {
    loadGallery();
  } else if (stepNum === 6 && state.lastRenderedShort) {
    document.getElementById('uploadFilePath').value = state.lastRenderedShort.filepath || '';
  }
}

// ── 01 SOURCE & DOWNLOAD ──────────────────────────────
async function fetchInfo() {
  const url = document.getElementById('urlInput').value.trim();
  const btn = document.getElementById('fetchBtn');
  if (!url) return;

  state.sourceUrl = url;
  btn.disabled = true;
  btn.textContent = 'Fetching...';
  document.getElementById('infoCard').classList.add('hidden');
  showError('');

  try {
    const res = await fetch('/api/video/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();

    if (data.error) {
      showError(data.error);
      return;
    }

    state.videoInfo = data;
    document.getElementById('thumb').src = data.thumbnail || '';
    document.getElementById('videoTitle').textContent = data.title;
    document.getElementById('videoMeta').textContent =
      `${data.uploader || ''}  \u00B7  ${fmtDuration(data.duration)}`;

    const fList = document.getElementById('formatList');
    fList.innerHTML = '';

    const bestChip = document.createElement('div');
    bestChip.className = 'fmt-chip selected';
    bestChip.textContent = 'Auto / Best Quality';
    bestChip.dataset.id = 'best';
    bestChip.onclick = () => selectFormat('best', bestChip);
    fList.appendChild(bestChip);
    state.selectedFormatId = 'best';

    (data.formats || []).forEach(fmt => {
      const chip = document.createElement('div');
      chip.className = 'fmt-chip';
      chip.textContent = fmt.label;
      chip.dataset.id = fmt.format_id;
      chip.onclick = () => selectFormat(fmt.format_id, chip);
      fList.appendChild(chip);
    });

    document.getElementById('infoCard').classList.remove('hidden');
  } catch (e) {
    showError('Request failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Fetch Formats';
  }
}

function selectFormat(fmtId, chipEl) {
  document.querySelectorAll('.fmt-chip').forEach(c => c.classList.remove('selected'));
  chipEl.classList.add('selected');
  state.selectedFormatId = fmtId;
}

async function startDownload(isQuick = false) {
  const url = document.getElementById('urlInput').value.trim();
  const quickBtn = document.getElementById('quickDlBtn');
  const dlBtn = document.getElementById('dlSelectedBtn');
  const status = document.getElementById('dlStatus');
  const dlCard = document.getElementById('dlCard');

  if (!url) {
    showError('Please enter a YouTube video URL first.');
    return;
  }

  state.sourceUrl = url;
  const format_id = isQuick ? 'best' : state.selectedFormatId;

  if (quickBtn) quickBtn.disabled = true;
  if (dlBtn) dlBtn.disabled = true;

  status.textContent = 'Downloading video and merging audio streams... Please wait.';
  status.classList.remove('hidden');
  dlCard.classList.add('hidden');
  showError('');

  try {
    const res = await fetch('/api/video/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, format_id }),
    });
    const data = await res.json();

    if (data.error) {
      status.classList.add('hidden');
      showError(data.error);
      return;
    }

    state.downloadedFile = data;
    document.getElementById('dlFileName').textContent = data.filename;
    document.getElementById('dlFileSize').textContent = data.filesize_mb;
    document.getElementById('dlFilePath').textContent = data.filepath;

    status.textContent = '\u2713 Video downloaded successfully!';
    dlCard.classList.remove('hidden');
  } catch (e) {
    showError('Download failed: ' + e.message);
  } finally {
    if (quickBtn) quickBtn.disabled = false;
    if (dlBtn) dlBtn.disabled = false;
  }
}

// ── 02 TRANSCRIBE ─────────────────────────────────────
async function startTranscribe() {
  const filepath = document.getElementById('transcribePathInput').value.trim() ||
    (state.downloadedFile ? state.downloadedFile.filepath : '');
  const btn = document.getElementById('transcribeBtn');
  const status = document.getElementById('transcribeStatus');
  const card = document.getElementById('transcriptCard');

  if (!filepath) {
    showError('No downloaded video found. Please download a video in Step 1.');
    return;
  }

  btn.disabled = true;
  status.textContent = 'Transcribing with faster-whisper (tiny model)... This takes a few seconds.';
  status.classList.remove('hidden');
  card.classList.add('hidden');
  showError('');

  try {
    const res = await fetch('/api/video/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filepath, model_size: 'tiny' }),
    });
    const data = await res.json();

    if (data.error) {
      status.classList.add('hidden');
      showError(data.error);
      return;
    }

    state.transcriptData = data;
    const segs = data.segments || [];
    document.getElementById('segCount').textContent = segs.length;

    const list = document.getElementById('segmentsList');
    list.innerHTML = '';
    segs.forEach(s => {
      const row = document.createElement('div');
      row.className = 'segment-row';
      row.innerHTML = `<span class="time-badge">${s.start}s - ${s.end}s</span> <span class="seg-text">${s.text}</span>`;
      list.appendChild(row);
    });

    status.textContent = `\u2713 Transcribed ${segs.length} segments! Detected language: ${data.language || 'auto'}`;
    card.classList.remove('hidden');
  } catch (e) {
    showError('Transcription failed: ' + e.message);
  } finally {
    btn.disabled = false;
  }
}

// ── 03 DETECT HOOKS ───────────────────────────────────
async function detectHooks() {
  const btn = document.getElementById('detectBtn');
  const min_duration = parseFloat(document.getElementById('minDurInput').value) || 15.0;
  const max_duration = parseFloat(document.getElementById('maxDurInput').value) || 50.0;
  const segments = state.transcriptData ? state.transcriptData.segments : [];

  if (!segments || segments.length === 0) {
    showError('No transcript segments found. Please transcribe in Step 2 first.');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Detecting...';
  showError('');

  try {
    const res = await fetch('/api/video/hooks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ segments, min_duration, max_duration }),
    });
    const data = await res.json();

    state.hooks = data.hooks || [];
    renderHooksList();

    if (state.hooks.length > 0) {
      selectHook(state.hooks[0]);
    }
  } catch (e) {
    showError('Hook detection error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Find Hooks';
  }
}

function renderHooksList() {
  const list = document.getElementById('hooksList');
  list.innerHTML = '';

  if (state.hooks.length === 0) {
    list.innerHTML = '<p class="page-sub">No candidate hooks found. You can adjust the manual start/end times above.</p>';
    return;
  }

  state.hooks.forEach(h => {
    const card = document.createElement('div');
    card.className = 'hook-card card';
    if (state.selectedClip.start === h.start && state.selectedClip.end === h.end) {
      card.classList.add('selected-hook');
    }

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
        <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text);">${h.title}</h4>
        <span class="score-badge">\u2605 Score: ${h.score}</span>
      </div>
      <p class="hook-preview">${h.preview}</p>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
        <span class="time-badge">${h.start}s &rarr; ${h.end}s (${h.duration}s)</span>
        <button class="btn btn-sm btn-accent" onclick='selectHook(${JSON.stringify(h)})'>Select Hook</button>
      </div>
    `;
    list.appendChild(card);
  });
}

function selectHook(h) {
  state.selectedClip = { start: h.start, end: h.end, title: h.title };
  document.getElementById('clipStartInput').value = h.start;
  document.getElementById('clipEndInput').value = h.end;
  renderHooksList();
}

// ── 04 RENDER SHORT ───────────────────────────────────
async function startRender() {
  const video_path = state.downloadedFile ? state.downloadedFile.filepath : '';
  const start_time = parseFloat(document.getElementById('clipStartInput').value) || state.selectedClip.start;
  const end_time = parseFloat(document.getElementById('clipEndInput').value) || state.selectedClip.end;
  const with_subtitles = document.getElementById('subtitlesCheck').checked;
  const segments = state.transcriptData ? state.transcriptData.segments : [];

  const btn = document.getElementById('renderBtn');
  const status = document.getElementById('renderStatus');
  const resultCard = document.getElementById('renderResultCard');

  if (!video_path) {
    showError('No input video found. Please download a video first.');
    return;
  }

  btn.disabled = true;
  status.textContent = 'Rendering vertical 9:16 video with FFmpeg... Please wait.';
  status.classList.remove('hidden');
  resultCard.classList.add('hidden');
  showError('');

  try {
    const res = await fetch('/api/video/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path, start_time, end_time, segments, with_subtitles }),
    });
    const data = await res.json();

    if (data.error) {
      status.classList.add('hidden');
      showError(data.error);
      return;
    }

    state.lastRenderedShort = data;
    status.textContent = '\u2713 Render complete!';
    document.getElementById('renderResultInfo').textContent =
      `${data.filename} (${data.duration}s, ${data.size_mb} MB)`;
    resultCard.classList.remove('hidden');
  } catch (e) {
    showError('Render failed: ' + e.message);
  } finally {
    btn.disabled = false;
  }
}

function sendRenderToUpload() {
  if (state.lastRenderedShort) {
    document.getElementById('uploadFilePath').value = state.lastRenderedShort.filepath;
  }
  switchStep(6);
}

// ── 05 GALLERY ────────────────────────────────────────
async function loadGallery() {
  const container = document.getElementById('galleryItems');
  container.innerHTML = '<p class="page-sub">Loading shorts...</p>';

  try {
    const res = await fetch('/api/gallery');
    const data = await res.json();
    const shorts = data.shorts || [];

    container.innerHTML = '';
    if (shorts.length === 0) {
      container.innerHTML = '<p class="page-sub">No shorts rendered yet. Render your first short in Step 4!</p>';
      return;
    }

    shorts.forEach(s => {
      const item = document.createElement('div');
      item.className = 'gallery-item card';
      item.innerHTML = `
        <div style="font-weight: 700; font-size: 0.9rem; color: var(--text);">${s.filename}</div>
        <div class="page-sub" style="margin: 4px 0 8px;">Size: ${s.size_mb} MB</div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-sm btn-primary" onclick="playInGallery('${s.video_url}', '${s.filename}', '${s.filepath}')">Play</button>
          <button class="btn btn-sm btn-secondary" onclick="sendToUploadDirect('${s.filepath}')">Upload</button>
        </div>
      `;
      container.appendChild(item);
    });

    if (shorts.length > 0 && !state.activeGalleryShort) {
      playInGallery(shorts[0].video_url, shorts[0].filename, shorts[0].filepath);
    }
  } catch (e) {
    showError('Failed to load gallery: ' + e.message);
  }
}

function playInGallery(url, title, filepath) {
  const player = document.getElementById('galleryVideoPlayer');
  player.src = url;
  player.play().catch(() => {});
  document.getElementById('playerTitle').textContent = title;
  state.activeGalleryShort = { filepath, filename: title, url };
}

function uploadCurrentGalleryVideo() {
  if (!state.activeGalleryShort) return;
  sendToUploadDirect(state.activeGalleryShort.filepath);
}

function sendToUploadDirect(filepath) {
  document.getElementById('uploadFilePath').value = filepath;
  switchStep(6);
}

// ── 06 UPLOAD ─────────────────────────────────────────
async function startUpload() {
  const filepath = document.getElementById('uploadFilePath').value.trim();
  const folder = document.getElementById('uploadFolder').value.trim() || '/shorts';
  const btn = document.getElementById('uploadBtn');
  const status = document.getElementById('uploadStatus');
  const resultCard = document.getElementById('uploadResultCard');

  if (!filepath) {
    showError('Please specify a video file path to upload.');
    return;
  }

  btn.disabled = true;
  status.textContent = 'Uploading to ImageKit CDN...';
  status.classList.remove('hidden');
  resultCard.classList.add('hidden');
  showError('');

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filepath, folder }),
    });
    const data = await res.json();

    if (data.error) {
      status.classList.add('hidden');
      showError(data.error);
      return;
    }

    status.textContent = '\u2713 Uploaded successfully to ImageKit!';
    document.getElementById('cdnUrlInput').value = data.url;
    resultCard.classList.remove('hidden');
  } catch (e) {
    showError('Upload failed: ' + e.message);
  } finally {
    btn.disabled = false;
  }
}

function copyCdnUrl() {
  const inp = document.getElementById('cdnUrlInput');
  inp.select();
  navigator.clipboard.writeText(inp.value);
  alert('CDN URL copied to clipboard!');
}

// Enter key trigger on URL input
document.getElementById('urlInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') fetchInfo();
});
