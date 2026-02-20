/* ═══════════════════════════════════════════════════════════════════════════
   Paper2Code — Application Logic
   ═══════════════════════════════════════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000';
const WS_BASE = 'ws://localhost:8000';

let currentRunId = null;
let ws = null;
let paperCatalog = [];       // full catalog from API
let selectedPaper = null;    // currently selected paper object
let activeCategory = 'all';

/* ── Navigation ──────────────────────────────────────────────────────────── */

function navigate(viewName) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));

  const view = document.getElementById(`view-${viewName}`);
  if (view) view.classList.add('active');

  const link = document.querySelector(`.nav-link[data-view="${viewName}"]`);
  if (link) link.classList.add('active');

  if (viewName === 'dashboard') loadHistory();
}

/* ── Paper Catalog ───────────────────────────────────────────────────────── */

async function loadPaperCatalog() {
  try {
    const res = await fetch(`${API_BASE}/api/papers`);
    if (!res.ok) return;
    const data = await res.json();
    paperCatalog = data.papers || [];
    const categories = data.categories || [];

    // Update paper count badge
    document.getElementById('paper-count').textContent = `${paperCatalog.length} papers`;

    // Render category chips
    const chipsEl = document.getElementById('category-chips');
    chipsEl.innerHTML = `<button class="chip active" data-cat="all" onclick="selectCategory('all')">All</button>`;
    categories.forEach(cat => {
      chipsEl.innerHTML += `<button class="chip" data-cat="${cat}" onclick="selectCategory('${cat}')">${cat}</button>`;
    });

    // Render paper grid
    renderPaperGrid(paperCatalog);
  } catch (e) {
    // Backend not running
  }
}

function selectCategory(cat) {
  activeCategory = cat;
  // Update chip active state
  document.querySelectorAll('.chip').forEach(c => {
    c.classList.toggle('active', c.dataset.cat === cat);
  });
  filterPapers();
}

function filterPapers() {
  const query = (document.getElementById('catalog-search').value || '').toLowerCase().trim();
  let filtered = paperCatalog;

  if (activeCategory !== 'all') {
    filtered = filtered.filter(p => p.category === activeCategory);
  }

  if (query) {
    filtered = filtered.filter(p =>
      p.title.toLowerCase().includes(query) ||
      p.authors.toLowerCase().includes(query) ||
      p.description.toLowerCase().includes(query) ||
      p.category.toLowerCase().includes(query)
    );
  }

  renderPaperGrid(filtered);
}

function renderPaperGrid(papers) {
  const grid = document.getElementById('paper-grid');

  if (papers.length === 0) {
    grid.innerHTML = '<div class="paper-grid-empty">No papers match your search.</div>';
    return;
  }

  grid.innerHTML = papers.map(p => `
    <div class="paper-card ${selectedPaper && selectedPaper.id === p.id ? 'selected' : ''}"
         onclick='selectPaper(${JSON.stringify(p).replace(/'/g, "\\'")})'>
      <div class="paper-card-title">${escapeHtml(p.title)}</div>
      <div class="paper-card-meta">
        <span class="paper-card-cat">${escapeHtml(p.category)}</span>
        <span>${escapeHtml(p.authors)} · ${p.year}</span>
      </div>
      <div class="paper-card-desc">${escapeHtml(p.description)}</div>
    </div>
  `).join('');
}

function selectPaper(paper) {
  selectedPaper = paper;

  // Highlight selected card
  document.querySelectorAll('.paper-card').forEach(c => c.classList.remove('selected'));
  // Find the card by matching title
  document.querySelectorAll('.paper-card').forEach(c => {
    if (c.querySelector('.paper-card-title').textContent === paper.title) {
      c.classList.add('selected');
    }
  });

  // Auto-fill form
  document.getElementById('paper-input').value =
    paper.arxiv_url || `${paper.title} — ${paper.description}`;
  document.getElementById('repo-name').value = paper.suggested_repo_name || '';

  // Scroll to launch section
  document.getElementById('launch-section').scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Check for duplicates
  checkDuplicate(paper.title);
}

async function checkDuplicate(title) {
  const banner = document.getElementById('dup-banner');
  banner.classList.add('hidden');

  try {
    const res = await fetch(`${API_BASE}/api/check-duplicate?paper_title=${encodeURIComponent(title)}`);
    if (!res.ok) return;
    const data = await res.json();

    if (data.has_duplicate && data.matches.length > 0) {
      const linksEl = document.getElementById('dup-banner-links');
      linksEl.innerHTML = data.matches.map(m =>
        `<a href="${m.url}" target="_blank">${escapeHtml(m.name)}</a>`
      ).join('');

      document.getElementById('dup-banner-text').textContent =
        `You already have ${data.matches.length} repo${data.matches.length > 1 ? 's' : ''} that may implement this paper:`;

      banner.classList.remove('hidden');
    }
  } catch (e) {
    // Silently fail — GITHUB_TOKEN may not be set
  }
}

function dismissDupBanner() {
  document.getElementById('dup-banner').classList.add('hidden');
}

/* ── Form submission ─────────────────────────────────────────────────────── */

async function handleSubmit(e) {
  e.preventDefault();

  const paperInput = document.getElementById('paper-input').value.trim();
  const repoName = document.getElementById('repo-name').value.trim();
  const framework = document.getElementById('framework').value;
  const maxIter = parseInt(document.getElementById('max-iter').value, 10);

  if (!paperInput || !repoName) return;

  const btn = document.getElementById('btn-generate');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting…';

  try {
    const res = await fetch(`${API_BASE}/api/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        paper_input: paperInput,
        repo_name: repoName,
        framework: framework,
        max_iterations: maxIter,
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const run = await res.json();
    currentRunId = run.id;

    // Show run view and connect WebSocket
    document.getElementById('nav-run').style.display = '';
    document.getElementById('run-title').textContent = `Generating: ${repoName}`;
    document.getElementById('run-meta').textContent =
      `Run ${run.id} • ${framework} • max ${maxIter} iterations`;

    resetPipelineSteps();
    clearLogs();
    navigate('run');
    connectWebSocket(run.id);

  } catch (err) {
    alert('Failed to start run: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">🚀</span> Generate Implementation';
  }
}

/* ── WebSocket ───────────────────────────────────────────────────────────── */

function connectWebSocket(runId) {
  if (ws) ws.close();

  setConnectionStatus('running', 'Agent working…');

  ws = new WebSocket(`${WS_BASE}/ws/runs/${runId}`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleProgressEvent(data);
  };

  ws.onclose = () => {
    fetchRunDetail(runId).then(run => {
      if (run && run.status === 'completed') {
        setConnectionStatus('success', 'Completed');
      } else if (run && run.status === 'failed') {
        setConnectionStatus('error', 'Failed');
      } else {
        setConnectionStatus('offline', 'Disconnected');
      }
    });
  };

  ws.onerror = () => {
    setConnectionStatus('error', 'Connection error');
  };
}

function setConnectionStatus(state, text) {
  const dot = document.querySelector('.status-dot');
  const label = document.querySelector('.status-text');
  dot.className = `status-dot ${state}`;
  label.textContent = text;
}

/* ── Progress events ─────────────────────────────────────────────────────── */

const STEP_ORDER = [
  'parsing_paper',
  'generating_architecture',
  'generating_code',
  'executing_code',
  'refining_code',
  'generating_readme',
  'generating_notebook',
  'pushing_to_github',
];

const STATUS_TO_STEP = {
  parsing_paper: 'parsing_paper',
  generating_architecture: 'generating_architecture',
  generating_code: 'generating_code',
  executing_code: 'executing_code',
  refining_code: 'executing_code',
  generating_readme: 'generating_readme',
  generating_notebook: 'generating_notebook',
  pushing_to_github: 'pushing_to_github',
  completed: 'pushing_to_github',
  failed: null,
};

function handleProgressEvent(evt) {
  addLog(evt.message);

  const stepKey = STATUS_TO_STEP[evt.status];
  if (stepKey) {
    updatePipelineStep(stepKey, evt.status);
  }

  if (evt.status === 'completed') {
    markAllStepsDone();
    setConnectionStatus('success', 'Completed');
    setTimeout(() => showResults(evt.run_id), 800);
  }

  if (evt.status === 'failed') {
    setConnectionStatus('error', 'Failed');
  }
}

function resetPipelineSteps() {
  document.querySelectorAll('.step').forEach(s => {
    s.classList.remove('active', 'done', 'error');
  });
}

function updatePipelineStep(stepKey, status) {
  const steps = document.querySelectorAll('.step');
  steps.forEach(s => {
    const sKey = s.dataset.step;
    const sIdx = STEP_ORDER.indexOf(sKey);
    const currentIdx = STEP_ORDER.indexOf(stepKey);

    if (sIdx < currentIdx) {
      s.classList.remove('active');
      s.classList.add('done');
    } else if (sKey === stepKey) {
      s.classList.remove('done');
      s.classList.add('active');
    }
  });
}

function markAllStepsDone() {
  document.querySelectorAll('.step').forEach(s => {
    s.classList.remove('active');
    s.classList.add('done');
  });
}

/* ── Logs ─────────────────────────────────────────────────────────────────── */

let logCount = 0;

function clearLogs() {
  logCount = 0;
  const body = document.getElementById('log-body');
  body.innerHTML = '<div class="log-placeholder">Waiting for agent to start…</div>';
  document.getElementById('log-count').textContent = '0 events';
}

function addLog(message) {
  const body = document.getElementById('log-body');
  const ph = body.querySelector('.log-placeholder');
  if (ph) ph.remove();

  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.textContent = message;
  body.appendChild(entry);
  body.scrollTop = body.scrollHeight;

  logCount++;
  document.getElementById('log-count').textContent = `${logCount} events`;
}

/* ── Results ─────────────────────────────────────────────────────────────── */

async function showResults(runId) {
  const run = await fetchRunDetail(runId);
  if (!run) return;

  document.getElementById('nav-results').style.display = '';

  const linksEl = document.getElementById('results-links');
  linksEl.innerHTML = '';
  if (run.github_url) {
    linksEl.innerHTML += `<a href="${run.github_url}" target="_blank">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
      View on GitHub
    </a>`;
  }
  if (run.colab_url) {
    linksEl.innerHTML += `<a href="${run.colab_url}" target="_blank">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0L2 4v8l6 4 6-4V4L8 0zm4.5 11.5L8 14l-4.5-2.5v-5L8 4l4.5 2.5v5z"/></svg>
      Open in Colab
    </a>`;
  }

  const codeEl = document.getElementById('result-code');
  codeEl.textContent = run.generated_code || '# No code generated';
  if (window.Prism) Prism.highlightElement(codeEl);

  const archEl = document.getElementById('result-architecture');
  archEl.innerHTML = run.architecture_doc
    ? (window.marked ? marked.parse(run.architecture_doc) : `<pre>${run.architecture_doc}</pre>`)
    : '<p>No architecture document generated.</p>';

  const readmeEl = document.getElementById('result-readme');
  readmeEl.innerHTML = run.readme
    ? (window.marked ? marked.parse(run.readme) : `<pre>${run.readme}</pre>`)
    : '<p>No README generated.</p>';

  navigate('results');
}

function switchTab(tabName) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

  document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');
  document.getElementById(`panel-${tabName}`).classList.add('active');
}

/* ── History ──────────────────────────────────────────────────────────────── */

async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE}/api/runs`);
    if (!res.ok) return;
    const runs = await res.json();

    const section = document.getElementById('history-section');
    const grid = document.getElementById('history-grid');

    if (runs.length === 0) {
      section.style.display = 'none';
      return;
    }

    section.style.display = '';
    grid.innerHTML = runs.map(r => {
      const statusClass = ['completed', 'failed'].includes(r.status)
        ? r.status
        : (['pending'].includes(r.status) ? 'pending' : 'running');

      return `
        <div class="history-item" onclick="viewRun('${r.id}')">
          <div class="history-item-info">
            <div class="history-item-name">${escapeHtml(r.repo_name)}</div>
            <div class="history-item-paper">${escapeHtml(truncate(r.paper_input, 80))}</div>
          </div>
          <span class="history-item-status status-${statusClass}">${r.status}</span>
        </div>
      `;
    }).join('');
  } catch (e) {
    // Backend not running
  }
}

async function viewRun(runId) {
  const run = await fetchRunDetail(runId);
  if (!run) return;
  currentRunId = runId;

  if (run.status === 'completed') {
    showResults(runId);
  } else {
    document.getElementById('nav-run').style.display = '';
    document.getElementById('run-title').textContent = `Run: ${run.repo_name}`;
    document.getElementById('run-meta').textContent = `Run ${run.id} • ${run.framework}`;
    resetPipelineSteps();
    clearLogs();
    run.logs.forEach(addLog);
    navigate('run');

    if (!['completed', 'failed'].includes(run.status)) {
      connectWebSocket(runId);
    }
  }
}

/* ── API helpers ─────────────────────────────────────────────────────────── */

async function fetchRunDetail(runId) {
  try {
    const res = await fetch(`${API_BASE}/api/runs/${runId}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/* ── Utils ────────────────────────────────────────────────────────────────── */

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function truncate(str, len) {
  return str.length > len ? str.slice(0, len) + '…' : str;
}

/* ── Init ─────────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  loadPaperCatalog();
  loadHistory();
});
