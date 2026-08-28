let selectedFormatId = 'best';

function fmtDuration(s) {
  if (!s) return '';
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

async function fetchInfo() {
  const url    = document.getElementById('urlInput').value.trim();
  const btn    = document.getElementById('fetchBtn');
  if (!url) return;

  btn.disabled = true;
  btn.textContent = '...';
  document.getElementById('infoCard').classList.add('hidden');
  document.getElementById('errorCard').classList.add('hidden');

  try {
    const res  = await fetch('/api/video/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();

    if (data.error) {
      document.getElementById('errorMsg').textContent = data.error;
      document.getElementById('errorCard').classList.remove('hidden');
      return;
    }

    document.getElementById('thumb').src       = data.thumbnail || '';
    document.getElementById('videoTitle').textContent = data.title;
    document.getElementById('videoMeta').textContent  =
      `${data.uploader || ''}  ·  ${fmtDuration(data.duration)}`;

    const fList = document.getElementById('formatList');
    fList.innerHTML = '';
    (data.formats || []).forEach(fmt => {
      const chip = document.createElement('div');
      chip.className = 'fmt-chip';
      chip.textContent = fmt.label;
      chip.dataset.id  = fmt.format_id;
      chip.onclick = () => {
        document.querySelectorAll('.fmt-chip').forEach(c => c.classList.remove('selected'));
        chip.classList.add('selected');
        selectedFormatId = fmt.format_id;
      };
      fList.appendChild(chip);
    });
    if (fList.firstChild) fList.firstChild.click();

    document.getElementById('infoCard').classList.remove('hidden');
  } catch (e) {
    document.getElementById('errorMsg').textContent = 'Request failed: ' + e.message;
    document.getElementById('errorCard').classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Fetch';
  }
}

// Enter key triggers fetch
document.getElementById('urlInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') fetchInfo();
});
