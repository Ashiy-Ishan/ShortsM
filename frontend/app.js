// Global state for pipeline
const state = {
  currentStep: 0,
  sourceUrl: '',
  selectedFormatId: 'best',
  videoInfo: null,
  downloadedFile: null,   // { filepath, filename, filesize_mb, duration }
  transcriptData: null,   // { segments, full_text, language }
  hooks: [],              // candidate clips
  selectedClip: null,
  lastRenderedShort: null,// { filepath, filename, video_url }
  activeGalleryShort: null,
  activeDownloadJob: null,
};

function addLog(message, level = 'info', time = null) {
  const terminal = document.getElementById('appLogTerminal');
  if (!terminal) return;
  const line = document.createElement('div');
  line.className = `log-line log-${level}`;
  const stamp = document.createElement('span');
  stamp.className = 'log-time';
  stamp.textContent = time ? new Date(time).toLocaleTimeString() : new Date().toLocaleTimeString();
  const text = document.createElement('span');
  text.textContent = message;
  line.append(stamp, text);
  terminal.appendChild(line);
  while (terminal.children.length > 300) terminal.removeChild(terminal.firstChild);
  terminal.scrollTop = terminal.scrollHeight;
}

async function apiRequest(url, options = {}) {
  const res = await fetch(url, options);
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Server returned an invalid response (${res.status}).`);
  }
  if (!res.ok || data.error) {
    throw new Error(data.error || `Request failed (${res.status}).`);
  }
  return data;
}

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

function clearVideoResults() {
  state.transcriptData = null;
  state.hooks = [];
  state.selectedClip = null;
  document.getElementById('transcriptCard').classList.add('hidden');
  document.getElementById('hooksList').replaceChildren();
  document.getElementById('renderResultCard').classList.add('hidden');
}

function switchStep(stepNum) {
  state.currentStep = stepNum;

  // Update sidebar active classes
  const steps = document.querySelectorAll('.steps .step');
  steps.forEach(el => {
    if (Number(el.dataset.step) === stepNum) {
      el.classList.add('step-active');
    } else {
      el.classList.remove('step-active');
    }
  });

  // Switch panels
  for (let i = 0; i <= 5; i++) {
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
    document.getElementById('transcribeFileName').textContent =
      `Using ${state.downloadedFile.filename}. Choose and upload another video to replace it.`;
  } else if (stepNum === 4) {
    const vName = state.downloadedFile ? state.downloadedFile.filename : 'None';
    document.getElementById('renderVideoName').textContent = vName;
    const clip = state.selectedClip;
    document.getElementById('renderClipTime').textContent = clip
      ? `${clip.start}s  \u2192  ${clip.end}s (Duration: ${(clip.end - clip.start).toFixed(1)}s)`
      : 'No hook selected';
  } else if (stepNum === 5) {
    loadGallery();
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
  addLog(`Fetching video information for ${url}`);

  try {
    const data = await apiRequest('/api/video/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

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
    addLog(`Found ${data.formats?.length || 0} available formats.`);
  } catch (e) {
    addLog(`Video information failed: ${e.message}`, 'error');
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
  const progressCard = document.getElementById('downloadProgressCard');
  const progressBar = document.getElementById('downloadProgressBar');
  const progressValue = document.getElementById('downloadProgressValue');
  const progressLabel = document.getElementById('downloadProgressLabel');
  const cancelBtn = document.getElementById('cancelDownloadBtn');

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
  progressCard.classList.remove('hidden');
  progressBar.style.width = '0%';
  progressValue.textContent = '0%';
  cancelBtn.disabled = false;
  showError('');
  addLog(`Starting ${isQuick ? 'quick' : 'selected-format'} download.`);

  try {
    const data = await apiRequest('/api/video/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, format_id }),
    });
    state.activeDownloadJob = data.job_id;
    addLog(`Download job ${data.job_id.slice(0, 8)} created.`);
    const result = await monitorDownload(data.job_id, {
      progressCard, progressBar, progressValue, progressLabel, cancelBtn,
    });
    if (!result) return;
    state.downloadedFile = result;
    clearVideoResults();
    document.getElementById('dlFileName').textContent = result.filename;
    document.getElementById('dlFileSize').textContent = result.filesize_mb;
    document.getElementById('dlFilePath').textContent = result.filepath;

    status.textContent = '\u2713 Video downloaded successfully!';
    dlCard.classList.remove('hidden');
    addLog(`Download complete: ${result.filename}.`);
  } catch (e) {
    status.classList.add('hidden');
    progressCard.classList.add('hidden');
    addLog(`Download failed: ${e.message}`, 'error');
    showError('Download failed: ' + e.message);
  } finally {
    state.activeDownloadJob = null;
    if (quickBtn) quickBtn.disabled = false;
    if (dlBtn) dlBtn.disabled = false;
  }
}

async function monitorDownload(jobId, elements) {
  let lastLogCount = 0;
  while (true) {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
    const job = await response.json();
    if (!response.ok || job.error && job.status === 'not_found') {
      throw new Error(job.error || 'Download job could not be found.');
    }
    const progress = Number(job.progress || 0);
    elements.progressBar.style.width = `${Math.min(100, progress)}%`;
    elements.progressValue.textContent = `${progress.toFixed(1)}%`;
    elements.progressLabel.textContent = job.message || 'Downloading...';
    document.getElementById('downloadSpeed').textContent = `Speed: ${job.speed || '--'}`;
    document.getElementById('downloadEta').textContent = `ETA: ${job.eta || '--'}`;
    (job.logs || []).slice(lastLogCount).forEach(entry => addLog(entry.message, entry.level, entry.time));
    lastLogCount = (job.logs || []).length;

    if (job.status === 'completed') {
      elements.progressCard.classList.add('hidden');
      return job.result;
    }
    if (job.status === 'cancelled') {
      elements.progressCard.classList.add('hidden');
      addLog('Download cancelled.', 'warning');
      showError('Download cancelled.');
      return null;
    }
    if (job.status === 'failed') {
      elements.progressCard.classList.add('hidden');
      throw new Error(job.error || 'Download failed.');
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
}

async function cancelDownload() {
  if (!state.activeDownloadJob) return;
  const jobId = state.activeDownloadJob;
  const button = document.getElementById('cancelDownloadBtn');
  button.disabled = true;
  addLog('Requesting download cancellation...', 'warning');
  try {
    await apiRequest(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
  } catch (e) {
    button.disabled = false;
    addLog(`Cancellation failed: ${e.message}`, 'error');
    showError(e.message);
  }
}

// ── 02 TRANSCRIBE ─────────────────────────────────────
async function startTranscribe() {
  const filepath = state.downloadedFile ? state.downloadedFile.filepath : '';
  const btn = document.getElementById('transcribeBtn');
  const status = document.getElementById('transcribeStatus');
  const card = document.getElementById('transcriptCard');

  if (!filepath) {
    showError('Choose and upload a video, or download one from the YouTube Downloader first.');
    return;
  }

  btn.disabled = true;
  status.textContent = 'Transcribing with faster-whisper (tiny model)... This takes a few seconds.';
  status.classList.remove('hidden');
  card.classList.add('hidden');
  showError('');
  addLog('Starting transcription.');

  try {
    const data = await apiRequest('/api/video/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filepath,
        model_size: 'tiny',
        save_files: document.getElementById('saveTranscriptCheck').checked,
      }),
    });

    state.transcriptData = data;
    state.hooks = [];
    state.selectedClip = null;
    document.getElementById('hooksList').replaceChildren();
    const segs = data.segments || [];
    document.getElementById('segCount').textContent = segs.length;

    const list = document.getElementById('segmentsList');
    list.innerHTML = '';
    segs.forEach(s => {
      const row = document.createElement('div');
      row.className = 'segment-row';
      const time = document.createElement('span');
      time.className = 'time-badge';
      time.textContent = `${s.start}s - ${s.end}s`;
      const text = document.createElement('span');
      text.className = 'seg-text';
      text.textContent = s.text;
      row.append(time, text);
      list.appendChild(row);
    });

    status.textContent = `\u2713 Transcribed ${segs.length} segments! Detected language: ${data.language || 'auto'}${data.srt_path ? ' Transcript files saved in ShortsM.' : ''}`;
    card.classList.remove('hidden');
    addLog(`Transcription complete: ${segs.length} segments.`);
  } catch (e) {
    status.classList.add('hidden');
    showError('Transcription failed: ' + e.message);
    addLog(`Transcription failed: ${e.message}`, 'error');
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
  addLog('Detecting candidate hooks.');

  try {
    const data = await apiRequest('/api/video/hooks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ segments, min_duration, max_duration }),
    });

    state.hooks = data.hooks || [];
    renderHooksList();

    if (state.hooks.length > 0) {
      selectHook(state.hooks[0]);
    }
    addLog(`Hook detection complete: ${state.hooks.length} candidates.`);
  } catch (e) {
    showError('Hook detection error: ' + e.message);
    addLog(`Hook detection failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Find Hooks';
  }
}

function renderHooksList() {
  const list = document.getElementById('hooksList');
  list.innerHTML = '';

  if (state.hooks.length === 0) {
    list.innerHTML = '<p class="page-sub">No candidate hooks found. Try a wider duration range or transcribe the video again.</p>';
    return;
  }

  state.hooks.forEach(h => {
    const card = document.createElement('div');
    card.className = 'hook-card card';
    if (state.selectedClip &&
        state.selectedClip.start === h.start &&
        state.selectedClip.end === h.end) {
      card.classList.add('selected-hook');
    }

    const heading = document.createElement('div');
    heading.className = 'hook-heading';
    const title = document.createElement('h4');
    title.textContent = h.title;
    const score = document.createElement('span');
    score.className = 'score-badge';
    score.textContent = `★ Score: ${h.score}`;
    heading.append(title, score);
    const preview = document.createElement('p');
    preview.className = 'hook-preview';
    preview.textContent = h.preview;
    const footer = document.createElement('div');
    footer.className = 'hook-footer';
    const range = document.createElement('span');
    range.className = 'time-badge';
    range.textContent = `${h.start}s → ${h.end}s (${h.duration}s)`;
    const select = document.createElement('button');
    select.className = 'btn btn-sm btn-accent';
    select.textContent = 'Select Hook';
    select.addEventListener('click', () => selectHook(h));
    footer.append(range, select);
    card.append(heading, preview, footer);
    list.appendChild(card);
  });
}

function selectHook(h) {
  state.selectedClip = { start: h.start, end: h.end, title: h.title };
  renderHooksList();
}

// ── 04 RENDER SHORT ───────────────────────────────────
async function startRender() {
  const video_path = state.downloadedFile ? state.downloadedFile.filepath : '';
  if (!state.selectedClip) {
    showError('Select a detected hook before rendering.');
    return;
  }
  const start_time = state.selectedClip.start;
  const end_time = state.selectedClip.end;
  const with_subtitles = document.getElementById('subtitlesCheck').checked;
  const segments = state.transcriptData ? state.transcriptData.segments : [];

  const btn = document.getElementById('renderBtn');
  const status = document.getElementById('renderStatus');
  const resultCard = document.getElementById('renderResultCard');

  if (!video_path) {
    showError('No input video found. Upload a video or download one first.');
    return;
  }

  btn.disabled = true;
  status.textContent = 'Rendering vertical 9:16 video with FFmpeg... Please wait.';
  status.classList.remove('hidden');
  resultCard.classList.add('hidden');
  showError('');
  addLog(`Rendering clip ${start_time}s to ${end_time}s.`);

  try {
    const data = await apiRequest('/api/video/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path, start_time, end_time, segments, with_subtitles }),
    });

    state.lastRenderedShort = data;
    status.textContent = '\u2713 Render complete!';
    document.getElementById('renderResultInfo').textContent =
      `${data.filename} (${data.duration}s, ${data.size_mb} MB)`;
    resultCard.classList.remove('hidden');
    addLog(`Render complete: ${data.filename}.`);
  } catch (e) {
    status.classList.add('hidden');
    showError('Render failed: ' + e.message);
    addLog(`Render failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
  }
}

// ── 05 GALLERY ────────────────────────────────────────
async function loadGallery() {
  const container = document.getElementById('galleryItems');
  container.innerHTML = '<p class="page-sub">Loading shorts...</p>';

  try {
    const data = await apiRequest('/api/gallery');
    const shorts = data.shorts || [];

    container.innerHTML = '';
    if (shorts.length === 0) {
      container.innerHTML = '<p class="page-sub">No shorts rendered yet. Render your first short in Step 4!</p>';
      return;
    }

    shorts.forEach(s => {
      const item = document.createElement('div');
      item.className = 'gallery-item card';
      const name = document.createElement('div');
      name.className = 'gallery-name';
      name.textContent = s.filename;
      const size = document.createElement('div');
      size.className = 'page-sub gallery-size';
      size.textContent = `Size: ${s.size_mb} MB`;
      const actions = document.createElement('div');
      actions.className = 'gallery-actions';
      const play = document.createElement('button');
      play.className = 'btn btn-sm btn-primary';
      play.textContent = 'Play';
      play.addEventListener('click', () => playInGallery(s.video_url, s.filename));
      actions.append(play);
      item.append(name, size, actions);
      container.appendChild(item);
    });

    if (shorts.length > 0 && !state.activeGalleryShort) {
      playInGallery(shorts[0].video_url, shorts[0].filename);
    }
  } catch (e) {
    showError('Failed to load gallery: ' + e.message);
    addLog(`Gallery load failed: ${e.message}`, 'error');
  }
}

function playInGallery(url, title, filepath) {
  const player = document.getElementById('galleryVideoPlayer');
  const normalizedUrl = new URL(url, window.location.href).href;
  const playableUrl = `${normalizedUrl}${normalizedUrl.includes('?') ? '&' : '?'}v=${Date.now()}`;
  player.addEventListener('error', () => {
    const detail = player.error ? ` (${player.error.code})` : '';
    addLog(`Unable to play ${title}${detail}.`, 'error');
    showError('The selected short could not be played.');
  }, { once: true });
  player.pause();
  player.src = playableUrl;
  player.load();
  player.play().then(
    () => addLog(`Playing ${title}.`),
    error => addLog(`Video loaded. Press play to start ${title}: ${error.message}`, 'warning')
  );
  document.getElementById('playerTitle').textContent = title;
  state.activeGalleryShort = { filename: title, url: playableUrl };
}

async function uploadTranscriptionVideo() {
  const fileInput = document.getElementById('transcribeFileInput');
  const file = fileInput.files[0];
  const button = document.getElementById('uploadVideoBtn');
  const status = document.getElementById('transcribeStatus');
  if (!file) {
    showError('Choose a video file to upload first.');
    return;
  }

  button.disabled = true;
  status.textContent = `Uploading ${file.name}...`;
  status.classList.remove('hidden');
  showError('');
  addLog(`Uploading video ${file.name}.`);
  try {
    const body = new FormData();
    body.append('file', file);
    const data = await apiRequest('/api/video/upload', { method: 'POST', body });
    state.downloadedFile = data;
    clearVideoResults();
    document.getElementById('transcribeFileName').textContent = `Ready to transcribe: ${data.filename}`;
    status.textContent = `Video uploaded: ${data.filename} (${data.filesize_mb} MB).`;
    addLog(`Video upload complete: ${data.filename}.`);
  } catch (e) {
    status.classList.add('hidden');
    showError(`Video upload failed: ${e.message}`);
    addLog(`Video upload failed: ${e.message}`, 'error');
  } finally {
    button.disabled = false;
  }
}

function downloadTranscript(format) {
  if (!state.transcriptData) return;
  const segments = state.transcriptData.segments || [];
  const content = format === 'srt'
    ? segments.map((segment, index) => {
      const stamp = seconds => {
        const millis = Math.round((seconds - Math.floor(seconds)) * 1000);
        const totalSeconds = Math.floor(seconds);
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const secs = totalSeconds % 60;
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(millis).padStart(3, '0')}`;
      };
      return `${index + 1}\n${stamp(segment.start)} --> ${stamp(segment.end)}\n${segment.text}`;
    }).join('\n\n')
    : (state.transcriptData.full_text || segments.map(segment => segment.text).join(' '));
  const blob = new Blob([content], { type: format === 'srt' ? 'text/plain;charset=utf-8' : 'text/plain;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${state.downloadedFile?.filename?.replace(/\.[^.]+$/, '') || 'transcript'}.${format}`;
  link.click();
  URL.revokeObjectURL(link.href);
}

document.querySelectorAll('.steps .step').forEach(step => {
  const go = () => switchStep(Number(step.dataset.step));
  step.addEventListener('click', go);
  step.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      go();
    }
  });
});
document.querySelectorAll('[data-go-step]').forEach(button => {
  button.addEventListener('click', () => switchStep(Number(button.dataset.goStep)));
});
document.getElementById('fetchBtn').addEventListener('click', fetchInfo);
document.getElementById('quickDlBtn').addEventListener('click', () => startDownload(true));
document.getElementById('dlSelectedBtn').addEventListener('click', () => startDownload(false));
document.getElementById('cancelDownloadBtn').addEventListener('click', cancelDownload);
document.getElementById('transcribeBtn').addEventListener('click', startTranscribe);
document.getElementById('uploadVideoBtn').addEventListener('click', uploadTranscriptionVideo);
document.getElementById('downloadSrtBtn').addEventListener('click', () => downloadTranscript('srt'));
document.getElementById('downloadTxtBtn').addEventListener('click', () => downloadTranscript('txt'));
document.getElementById('detectBtn').addEventListener('click', detectHooks);
document.getElementById('renderBtn').addEventListener('click', startRender);
document.getElementById('galleryRefreshBtn').addEventListener('click', loadGallery);
document.getElementById('clearLogsBtn').addEventListener('click', () => {
  document.getElementById('appLogTerminal').replaceChildren();
  addLog('Application log cleared.');
});
document.getElementById('urlInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') fetchInfo();
});
