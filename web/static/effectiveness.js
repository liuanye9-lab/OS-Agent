/* Effectiveness Dashboard JavaScript — V11.3 Updated */

const API = '/api/effectiveness';
const pageParams = new URLSearchParams(window.location.search);
const linkedRunId = pageParams.get('run_id') || '';

// -- Initialization --

document.addEventListener('DOMContentLoaded', () => {
  setupNavigationLinks();
  loadSummaries();
  loadTasks();
});

function setupNavigationLinks() {
  const observerLink = document.getElementById('observerLink');
  if (observerLink && linkedRunId) {
    observerLink.href = `/observe/${encodeURIComponent(linkedRunId)}`;
  }
}

// -- API Helpers --

async function apiFetch(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const body = await res.json();

  // New {ok, data/error} contract
  if (!res.ok) {
    throw new Error(body.error || body.detail || res.statusText);
  }
  if (body.ok === false) {
    throw new Error(body.error || 'Request failed');
  }
  return body.data !== undefined ? body.data : body;
}

// -- Summary Loading --

async function loadSummaries() {
  try {
    const data = await apiFetch('/summary');
    const summaries = data.summaries || [];
    renderSummaryCards(summaries);
    renderComparisonTable(summaries);
  } catch (err) {
    console.error('Failed to load summaries:', err);
    document.getElementById('summaryGrid').innerHTML =
      '<div class="summary-card empty"><div class="summary-label">加载失败</div><div class="summary-value error">请刷新重试</div></div>';
  }
}

async function loadTasks() {
  try {
    const data = await apiFetch('/tasks');
    const tasks = data.tasks || [];
    _cachedTasks = tasks;
    populateTaskSelect(tasks);
  } catch (err) {
    console.error('Failed to load tasks:', err);
  }
}

// -- Rendering --

function renderSummaryCards(summaries) {
  const totalTasks = summaries.length;
  let totalRuns = 0;
  let effectiveCount = 0;
  let promisingCount = 0;
  let notEffectiveCount = 0;
  let totalTokenDelta = 0;
  let tokenDeltaCount = 0;
  let totalCpDelta = 0;
  let cpDeltaCount = 0;

  summaries.forEach(s => {
    totalRuns += (s.baseline_count || 0) + (s.stableagent_count || 0);
    if (s.verdict === 'effective') effectiveCount++;
    else if (s.verdict === 'promising') promisingCount++;
    else if (s.verdict === 'not_effective') notEffectiveCount++;
    if (s.delta_tokens !== 0) {
      totalTokenDelta += s.delta_tokens;
      tokenDeltaCount++;
    }
    if (s.delta_constraint_preservation !== undefined) {
      totalCpDelta += s.delta_constraint_preservation;
      cpDeltaCount++;
    }
  });

  document.getElementById('totalTasks').textContent = totalTasks;
  document.getElementById('totalRuns').textContent = totalRuns;
  document.getElementById('effectiveTasks').textContent = effectiveCount;
  document.getElementById('promisingTasks').textContent = promisingCount;
  document.getElementById('notEffectiveTasks').textContent = notEffectiveCount;

  const avgSave = tokenDeltaCount > 0 ? (totalTokenDelta / tokenDeltaCount).toFixed(0) : '--';
  document.getElementById('avgTokenSave').textContent = avgSave === '--' ? '--' : `${avgSave} tokens`;

  const avgCpDelta = cpDeltaCount > 0 ? (totalCpDelta / cpDeltaCount).toFixed(4) : '--';
  document.getElementById('avgCpDelta').textContent = avgCpDelta === '--' ? '--' : avgCpDelta;
}

function renderComparisonTable(summaries) {
  const tbody = document.getElementById('comparisonBody');

  if (!summaries || summaries.length === 0) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty-row">暂无数据，请创建任务并记录运行</td></tr>';
    return;
  }

  tbody.innerHTML = summaries.map(s => {
    const task = getTaskById(s.task_id);
    const desc = task ? task.description : s.task_id;

    return `
      <tr>
        <td><code>${s.task_id}</code></td>
        <td>${desc}</td>
        <td>${s.baseline_count || 0}</td>
        <td>${s.stableagent_count || 0}</td>
        <td class="${deltaClass(s.delta_success, true)}">${formatDelta(s.delta_success, true)}</td>
        <td class="${deltaClass(s.delta_tokens, false)}">${formatDelta(s.delta_tokens, false)}</td>
        <td class="${deltaClass(s.delta_intent_drift, false)}">${formatDelta(s.delta_intent_drift, true)}</td>
        <td class="${deltaClass(s.delta_constraint_preservation, true)}">${formatDelta(s.delta_constraint_preservation, true)}</td>
        <td><span class="verdict verdict-${s.verdict}">${verdictLabel(s.verdict)}</span></td>
        <td><button onclick="viewTask('${s.task_id}')" class="btn btn-link">详情</button></td>
      </tr>
    `;
  }).join('');
}

// -- Helpers --

let _cachedTasks = [];

function getTaskById(taskId) {
  return _cachedTasks.find(t => t.task_id === taskId);
}

function populateTaskSelect(tasks) {
  const select = document.getElementById('runTaskIdSelect');
  if (!tasks.length) {
    select.innerHTML = '<option value="">-- 请先创建任务 --</option>';
    return;
  }
  select.innerHTML = tasks.map(t =>
    `<option value="${t.task_id}">${t.task_id} — ${t.description}</option>`
  ).join('');
}

function deltaClass(value, higherIsBetter) {
  if (value === undefined || Math.abs(value) < 0.001) return 'delta-neutral';
  const positive = higherIsBetter ? value > 0 : value < 0;
  return positive ? 'delta-positive' : 'delta-negative';
}

function formatDelta(value, higherIsBetter) {
  if (value === undefined || Math.abs(value) < 0.001) return '≈ 持平';
  const arrow = higherIsBetter ? (value > 0 ? '↑' : '↓') : (value < 0 ? '↓' : '↑');
  return `${arrow} ${Math.abs(value).toFixed(2)}`;
}

function verdictLabel(verdict) {
  const labels = {
    'insufficient_data': '数据不足',
    'promising': '有潜力',
    'effective': '有效',
    'not_effective': '未见效',
  };
  return labels[verdict] || verdict;
}

function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[ch]));
}

// -- Modal Handling --

function openTaskModal() {
  document.getElementById('taskModal').classList.add('active');
}

function closeTaskModal() {
  document.getElementById('taskModal').classList.remove('active');
  document.getElementById('taskIdInput').value = '';
  document.getElementById('taskDescInput').value = '';
}

function openRunModal() {
  document.getElementById('runModal').classList.add('active');
  loadTasks(); // Refresh task select
}

function closeRunModal() {
  document.getElementById('runModal').classList.remove('active');
}

function closeTaskDetailModal() {
  document.getElementById('taskDetailModal').classList.remove('active');
}

// Close modal on backdrop click
document.querySelectorAll('.modal').forEach(modal => {
  modal.addEventListener('click', e => {
    if (e.target === modal) {
      modal.classList.remove('active');
    }
  });
});

// -- Form Submission --

async function submitTask(e) {
  e.preventDefault();

  const taskId = document.getElementById('taskIdInput').value.trim();
  const description = document.getElementById('taskDescInput').value.trim();
  const category = document.getElementById('taskCategoryInput').value;

  if (!taskId) {
    showToast('请输入任务 ID', 'error');
    return;
  }

  try {
    await apiFetch('/task', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId, description, category }),
    });
    showToast(`任务 "${taskId}" 已创建`);
    closeTaskModal();
    loadSummaries();
    loadTasks();
  } catch (err) {
    showToast(`创建失败: ${err.message}`, 'error');
  }
}

async function submitRun(e) {
  e.preventDefault();

  const body = {
    task_id: document.getElementById('runTaskIdSelect').value,
    mode: document.getElementById('runModeSelect').value,
    success: document.getElementById('runSuccessSelect').value === 'true',
    edits_made: parseInt(document.getElementById('runEditsInput').value, 10),
    files_changed: parseInt(document.getElementById('runFilesInput').value, 10),
    tokens_used: parseInt(document.getElementById('runTokensInput').value, 10),
    intent_drift: parseFloat(document.getElementById('runDriftInput').value),
    duration_sec: parseFloat(document.getElementById('runDurationInput').value),
    error_message: document.getElementById('runErrorInput').value.trim(),
    // V11.3 new fields
    model: document.getElementById('runModelInput').value.trim(),
    stableagent_run_id: document.getElementById('runSaRunIdInput').value.trim(),
    test_passed: document.getElementById('runTestPassedSelect').value === 'true',
    over_editing: document.getElementById('runOverEditingSelect').value === 'true',
    rework_count: parseInt(document.getElementById('runReworkCountInput').value, 10),
    user_satisfaction: parseFloat(document.getElementById('runSatisfactionInput').value),
    constraint_preservation: parseFloat(document.getElementById('runCpInput').value),
  };

  if (!body.task_id) {
    showToast('请选择任务', 'error');
    return;
  }

  try {
    await apiFetch('/run', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    showToast('运行结果已记录');
    closeRunModal();
    loadSummaries();
  } catch (err) {
    showToast(`记录失败: ${err.message}`, 'error');
  }
}

function viewTask(taskId) {
  openTaskDetailModal(taskId);
}

async function openTaskDetailModal(taskId) {
  const modal = document.getElementById('taskDetailModal');
  const title = document.getElementById('taskDetailTitle');
  const body = document.getElementById('taskDetailBody');
  title.textContent = `任务详情 · ${taskId}`;
  body.innerHTML = '<div class="empty-row">加载中...</div>';
  modal.classList.add('active');

  try {
    const detail = await apiFetch(`/task/${encodeURIComponent(taskId)}`);
    const runs = detail.runs || [];
    const summary = detail.summary || {};
    body.innerHTML = `
      <div class="detail-grid">
        <div class="detail-card">
          <div class="detail-label">任务 ID</div>
          <div class="detail-value">${escapeHtml(detail.task_id)}</div>
        </div>
        <div class="detail-card">
          <div class="detail-label">分类</div>
          <div class="detail-value">${escapeHtml(detail.category || 'general')}</div>
        </div>
        <div class="detail-card">
          <div class="detail-label">Baseline</div>
          <div class="detail-value">${summary.baseline_count || 0}</div>
        </div>
        <div class="detail-card">
          <div class="detail-label">StableAgent</div>
          <div class="detail-value">${summary.stableagent_count || 0}</div>
        </div>
      </div>
      <div>
        <div class="detail-label">描述</div>
        <div>${escapeHtml(detail.description || '')}</div>
      </div>
      <div>
        <div class="detail-label">运行记录</div>
        <div class="runs-list">
          ${runs.length ? runs.map(renderRunRow).join('') : '<div class="empty-row">暂无运行记录</div>'}
        </div>
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div class="empty-row">加载失败: ${escapeHtml(err.message)}</div>`;
  }
}

function renderRunRow(run) {
  const linkedRun = run.stableagent_run_id
    ? `<a href="/observe/${encodeURIComponent(run.stableagent_run_id)}">${escapeHtml(run.stableagent_run_id)}</a>`
    : escapeHtml(run.run_id);
  return `
    <div class="run-row">
      <code>${linkedRun}</code>
      <span>${escapeHtml(run.mode)}</span>
      <span>${run.success ? '成功' : '失败'}</span>
      <span>${escapeHtml(run.tokens_used ?? 0)} tokens</span>
      <span>${escapeHtml(run.created_at ? new Date(run.created_at * 1000).toLocaleDateString() : '')}</span>
    </div>
  `;
}
