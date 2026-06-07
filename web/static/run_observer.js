const AVATAR_SCENE_MAP = {
  listening:       { scene: "desk",           labelZh: "接收任务",    prop: "task_card" },
  thinking:        { scene: "thinking_board",  labelZh: "理解需求",    prop: "magnifier" },
  calculating:     { scene: "budget_panel",    labelZh: "计算预算",    prop: "abacus" },
  reading_notes:   { scene: "memory_wall",     labelZh: "找时间记忆",  prop: "memory_cards" },
  searching_books: { scene: "library",         labelZh: "查项目资料",  prop: "books" },
  organizing:      { scene: "context_table",   labelZh: "压缩上下文",  prop: "context_blocks" },
  planning:        { scene: "map_table",       labelZh: "规划步骤",    prop: "route_map" },
  tooling:         { scene: "tool_bench",      labelZh: "调用工具",    prop: "wrench" },
  watching:        { scene: "monitor",         labelZh: "观察结果",    prop: "screen" },
  grading:         { scene: "exam_table",      labelZh: "评估结果",    prop: "score_sheet" },
  diagnosing:      { scene: "diagnosis_board", labelZh: "分析失败",    prop: "warning_card" },
  writing_case:    { scene: "case_desk",       labelZh: "生成错题",    prop: "case_file" },
  learning:        { scene: "skill_book",      labelZh: "提出改法",    prop: "skill_patch" },
  waiting_approval:{ scene: "approval_gate",   labelZh: "等待审核",    prop: "red_card" },
  archiving:       { scene: "archive_cabinet", labelZh: "导出规则",    prop: "best_skill" },
  done:            { scene: "delivery_desk",   labelZh: "完成任务",    prop: "checkmark" },
  failed:          { scene: "error_board",     labelZh: "任务失败",    prop: "error_sign" },
  idle:            { scene: "desk",            labelZh: "空闲",        prop: "coffee" }
};
const AVATAR_EMOJI = {
  listening:        "📥",
  thinking:         "🔎",
  calculating:      "🧮",
  reading_notes:    "🗂️",
  searching_books:  "📚",
  organizing:       "🧩",
  planning:         "🗺️",
  tooling:          "🔧",
  watching:         "📝",
  grading:          "📖",
  diagnosing:       "🔍",
  writing_case:     "📋",
  learning:         "✅",
  waiting_approval: "⏳",
  archiving:        "📦",
  done:             "🎉",
  failed:           "⚠️",
  idle:             "☕"
};
let logs = [];
let timelineItems = [];
const STAGE_LABEL_MAP = {
  "temporal_memory_retrieving": "时间记忆",
  "context_compressing": "上下文压缩",
  "rag_retrieving": "RAG 检索",
  "context_building": "构建上下文",
  "evaluating": "评估",
  "regression_generation": "回归用例",
  "memory_update_candidate": "候选记忆",
  "skill_patch_proposal": "自我优化",
  "validation": "验证",
  "human_review": "人工审核",
  "exporting": "导出规则",
  "acting": "执行",
  "observing": "观察",
  "planning": "规划",
  "intent_parsing": "理解需求",
  "context_budgeting": "预算计算",
  "received": "接收任务",
  "completed": "完成",
  "failed": "失败",
};
const $taskName    = document.getElementById("taskName");
const $runId       = document.getElementById("runId");
const $progressPct = document.getElementById("progressPct");
const $progressBar = document.getElementById("progressBar");
const $mcpStatus   = document.getElementById("mcpStatus");
const $avatarScene = document.getElementById("avatarScene");
const $sceneLabel  = document.getElementById("sceneLabel");
const $sceneProp   = document.getElementById("sceneProp");
const $nowStatus   = document.getElementById("nowStatus");
const $whyText     = document.getElementById("whyText");
const $evidenceText = document.getElementById("evidenceText");
const $nextStepText = document.getElementById("nextStepText");
const $progressText = document.getElementById("progressText");
const $logPanel    = document.getElementById("logPanel");
const $timelineEmpty = document.getElementById("timelineEmpty");
const $timelineCol   = document.getElementById("timelineCol");
const $siReport    = document.getElementById("siReport");
const params = new URLSearchParams(window.location.search);
const runId   = params.get("run_id");
if (runId) {
  $runId.textContent = runId;
  const v3Link = document.getElementById("v3Link");
  if (v3Link) v3Link.href = `/runs/${runId}`;
  const effLink = document.getElementById("effLink");
  if (effLink) effLink.href = `/effectiveness?run_id=${encodeURIComponent(runId)}`;
  loadHistoryAndConnect(runId);
  checkEffectivenessForRun(runId);
}
async function loadHistoryAndConnect(runId) {
  let historyEvents = [];
  let apiEventCount = 0;
  let dashboardReplayOk = false;
  try {
    const resp = await fetch(`/api/runs/${runId}/events`);
    if (resp.ok) {
      const data = await resp.json();
      if (data && typeof data === "object" && Array.isArray(data.events)) {
        historyEvents = data.events;
        apiEventCount = data.event_count || historyEvents.length;
      } else if (Array.isArray(data) && data.length > 0) {
        historyEvents = data;
        apiEventCount = data.length;
      }
      if (historyEvents.length > 0) {
        for (const evt of historyEvents) {
          applyEvent(evt);
        }
        addLogLine("info", `API 回放 ${historyEvents.length} 个历史事件 (event_count=${apiEventCount})`);
        dashboardReplayOk = true;
      }
      updateEventApiStatus(true, apiEventCount, dashboardReplayOk);
    } else if (resp.status === 404) {
      addLogLine("warn", `Run ${runId} 不存在 (404)`);
      updateEventApiStatus(false, 0, false);
    } else {
      addLogLine("warn", `API 返回 HTTP ${resp.status}`);
      updateEventApiStatus(false, 0, false);
    }
  } catch (err) {
    addLogLine("warn", `API 回放失败: ${err.message}`);
    updateEventApiStatus(false, 0, false);
  }
  connectWebSocket(runId);
  setTimeout(() => {
    const ws = activeConnections.get(runId);
    const wsConnected = ws && ws.readyState === WebSocket.OPEN;
    const timelineEmpty = $timelineCol && $timelineCol.children.length === 0;
    if (historyEvents.length === 0 && !wsConnected) {
      showSyncError("同步异常：未收到任何事件（API 和 WebSocket 均无数据）");
    } else if (historyEvents.length === 0 && wsConnected) {
      addLogLine("warn", "历史事件为空，仅显示实时事件");
      showHistoryEmptyNotice();
    }
  }, 3000);
}
function updateEventApiStatus(apiOk, eventCount, replayOk) {
  const statusEl = document.getElementById("eventApiStatus");
  if (statusEl) {
    statusEl.textContent = apiOk ? `${eventCount} events` : "无事件";
    statusEl.className = apiOk ? "api-status ok" : "api-status error";
  }
  const replayEl = document.getElementById("dashboardReplayOk");
  if (replayEl) {
    replayEl.textContent = replayOk ? "✅ 已回放" : "❌ 未回放";
    replayEl.className = replayOk ? "api-status ok" : "api-status error";
  }
  const wsEl = document.getElementById("websocketStatus");
  if (wsEl) {
    wsEl.textContent = "等待连接";
    wsEl.className = "api-status";
  }
}
function showSyncError(message) {
  const banner = document.getElementById("syncWarning");
  if (banner) {
    banner.style.display = "flex";
    const text = banner.querySelector(".sync-warning-text");
    if (text) text.textContent = message || "事件同步异常";
  }
  $mcpStatus.textContent = "同步错误";
  $mcpStatus.className = "mcp-status disconnected";
}
function showHistoryEmptyNotice() {
  const notice = document.createElement("div");
  notice.className = "history-empty-notice";
  notice.textContent = "⚠️ 历史事件为空，仅显示实时事件";
  if ($timelineCol && $timelineCol.parentNode) {
    $timelineCol.parentNode.insertBefore(notice, $timelineCol);
  }
}
function connectWebSocket(runId) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl    = `${protocol}//${location.host}/dashboard-sync/ws/runs/${runId}`;
  const ws = new WebSocket(wsUrl);
  ws.onopen = () => {
    $mcpStatus.textContent = "已连接";
    $mcpStatus.className   = "mcp-status";
    addLogLine("info", `WebSocket 已连接: ${runId}`);
    activeConnections.set(runId, ws);
    if (!primaryRunId) primaryRunId = runId;
    const wsEl = document.getElementById("websocketStatus");
    if (wsEl) {
      wsEl.textContent = "✅ 已连接";
      wsEl.className = "api-status ok";
    }
  };
  ws.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      applyEvent(event);
    } catch (err) {
      addLogLine("error", `消息解析失败: ${err.message}`);
    }
  };
  ws.onclose = () => {
    $mcpStatus.textContent = "已断开";
    $mcpStatus.className   = "mcp-status disconnected";
    addLogLine("warn", "WebSocket 已断开");
    activeConnections.delete(runId);
  };
  ws.onerror = () => {
    addLogLine("error", "WebSocket 连接错误");
  };
}
function applyEvent(evt) {
  addLogLine("info", `收到事件: ${evt.event_type || evt.type || "unknown"}`);
  if (evt.event_sync_ok === false) {
    showSyncWarning();
  }
  if (evt.progress_pct !== undefined) {
    updateProgress(evt.progress_pct, evt.status_text_zh || evt.stage_label_zh || "");
  }
  if (evt.avatar_state) {
    updateAvatar(evt.avatar_state);
  }
  updateStatusCard(evt);
  appendTimeline(evt);
  if (evt.si_report || evt.self_improvement || evt.learning_triggered !== undefined) {
    updateSIReport(evt.si_report || evt.self_improvement || evt);
  }
  if (evt.event_type === "understanding.trace.created" && evt.understanding_trace) {
    renderUnderstandingPanel({ok: true, understanding_trace: evt.understanding_trace});
  }
  if (evt.event_type === "token.budget.estimated" && evt.token_report) {
    renderTokenBudgetPanel({ok: true, token_report: evt.token_report});
  }
  updateRecursiveHarnessPanels(evt);
  if (evt.event_type === "regression.generated" || evt.event_type === "bad_case.recorded") {
    const bcEl = document.getElementById("badCaseContent");
    if (bcEl) {
      const item = document.createElement("div");
      item.className = "v11-item";
      item.innerHTML = `<span class="label">${esc(evt.event_type)}</span><span class="value">${esc(evt.decision_summary_zh || evt.summary_zh || "")}</span>`;
      bcEl.appendChild(item);
    }
  }
  if (evt.event_type === "skill.patch.proposed" || evt.event_type === "validation.checked" || evt.event_type === "human_review.required") {
    if (evt.si_report || evt.learning_triggered !== undefined) {
      loadLearning(runId).catch(() => {});
    }
  }
  if (evt.run_id && evt.run_id !== $runId.textContent) {
    $runId.textContent = evt.run_id;
  }
}
function updateProgress(pct, label) {
  const safe = Math.max(0, Math.min(100, pct));
  $progressPct.textContent = `${safe}%`;
  $progressBar.style.width = `${safe}%`;
  $progressText.textContent = label ? `${safe}% — ${label}` : `${safe}%`;
  $progressPct.style.color = "inherit";
}
function updateAvatar(state) {
  const info = AVATAR_SCENE_MAP[state] || AVATAR_SCENE_MAP.idle;
  if (typeof renderAvatarScene === "function") {
    renderAvatarScene(info.scene, "avatarCanvas");
  }
  $sceneLabel.textContent = info.labelZh;
  $sceneProp.textContent = `场景: ${info.scene} | 道具: ${info.prop}`;
}
function updateStatusCard(evt) {
  const now = evt.stage_label_zh || evt.status_text_zh || evt.what_happened_zh || "";
  const why = evt.why_zh || evt.decision_summary_zh || "";
  const next = evt.next_step_zh || "";
  const evidence = evt.evidence || [];
  if (now) $nowStatus.textContent = now;
  if (why) $whyText.textContent = why;
  if (evidence.length > 0) {
    $evidenceText.textContent = evidence.slice(0, 3).join(" | ");
  } else if (evt.decision_summary_zh) {
    $evidenceText.textContent = evt.decision_summary_zh;
  } else {
    $evidenceText.textContent = "--";
  }
  if (next) $nextStepText.textContent = next;
  if (evt.task_name) $taskName.textContent = evt.task_name;
}
function appendTimeline(evt) {
  if ($timelineEmpty) {
    $timelineEmpty.remove();
    window._timelineEmptyRemoved = true;
  }
  const stage = evt.stage_label_zh || evt.stage || "";
  const what  = evt.what_happened_zh || evt.status_text_zh || evt.event_type || "";
  const pct   = evt.progress_pct !== undefined ? `${evt.progress_pct}%` : "";
  const stageKey = evt.stage || "";
  const stageZhLabel = STAGE_LABEL_MAP[stageKey] || stage;
  const item = document.createElement("div");
  item.className = "timeline-item";
  item.innerHTML = `
    <div class="tl-stage">${escapeHtml(stageZhLabel)}</div>
    <div class="tl-what">${escapeHtml(what)}</div>
    <div class="tl-progress">${pct}</div>
  `;
  $timelineCol.appendChild(item);
  timelineItems.push(item);
  while (timelineItems.length > 50) {
    const old = timelineItems.shift();
    if (old) old.remove();
  }
}
function updateSIReport(report) {
  if (!report) return;
  $siReport.classList.add("visible");
  document.getElementById("siTriggered").querySelector(".si-value").textContent =
    report.learning_triggered ? "是" : "否";
  document.getElementById("siRegressions").querySelector(".si-value").textContent =
    (report.regression_cases || []).length;
  document.getElementById("siMemories").querySelector(".si-value").textContent =
    (report.memory_candidates || []).length;
  document.getElementById("siPatches").querySelector(".si-value").textContent =
    (report.skill_patches || []).length;
  const valEl = document.getElementById("siValidation");
  valEl.querySelector(".si-value").textContent =
    report.validation_passed === true ? "✅ 通过" :
    report.validation_passed === false ? "❌ 未通过" : "--";
  valEl.className = report.validation_passed ? "si-item ok" : "si-item warn";
  const reviewEl = document.getElementById("siReview");
  const hrStatus = report.human_review_status || "--";
  const reviewLabelMap = {
    "pending": "⏳ 等待审核",
    "approved": "✅ 已通过",
    "rejected": "❌ 已拒绝",
    "validation_failed": "⚠️ 验证失败",
    "dry_run": "🧪 试运行",
    "none": "无需审核",
  };
  reviewEl.querySelector(".si-value").textContent = reviewLabelMap[hrStatus] || hrStatus;
  reviewEl.className = hrStatus === "approved" ? "si-item ok"
    : hrStatus === "rejected" || hrStatus === "validation_failed" ? "si-item warn"
    : "si-item";
  document.getElementById("siExport").querySelector(".si-value").textContent =
    report.best_skill_exported ? "✅ 已导出" : "未导出";
  document.getElementById("siSummary").querySelector(".si-value").textContent =
    report.summary_zh || "--";
}
function showSyncWarning() {
  const banner = document.getElementById("syncWarning");
  if (banner) {
    banner.style.display = "flex";
  }
}
function addLogLine(level, msg) {
  const time = new Date().toLocaleTimeString("zh-CN");
  logs.push(`[${time}] [${level}] ${msg}`);
  if (logs.length > 200) logs.shift();
  $logPanel.textContent = logs.join("\n");
  if ($logPanel.classList.contains("open")) {
    $logPanel.scrollTop = $logPanel.scrollHeight;
  }
}
function toggleLog() {
  $logPanel.classList.toggle("open");
  if ($logPanel.classList.contains("open")) {
    $logPanel.scrollTop = $logPanel.scrollHeight;
  }
}
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}
const activeConnections = new Map();
const runBuffers = new Map();
/**
 * Observe multiple runs in parallel.
 * @param {string[]} runIds - list of run IDs to observe
 */
function observeMultipleRuns(runIds) {
  for (const [id, ws] of activeConnections) {
    if (!runIds.includes(id)) {
      ws.close();
      activeConnections.delete(id);
      runBuffers.delete(id);
    }
  }
  for (const runId of runIds) {
    if (!activeConnections.has(runId)) {
      connectMultiAgentWebSocket(runId);
    }
  }
  updateMultiAgentDisplay();
}
function connectMultiAgentWebSocket(runId) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${location.host}/dashboard-sync/ws/runs/${runId}`;
  const ws = new WebSocket(wsUrl);
  ws.onopen = () => {
    addLogLine("info", `[Agent ${runId.slice(0, 8)}] 已连接`);
    activeConnections.set(runId, ws);
    runBuffers.set(runId, []);
  };
  ws.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      const buffer = runBuffers.get(runId) || [];
      buffer.push(event);
      if (buffer.length > 100) buffer.shift();
      runBuffers.set(runId, buffer);
      if (runId === primaryRunId) {
        applyEvent(event);
      }
    } catch (err) {
      addLogLine("error", `[Agent ${runId.slice(0, 8)}] 消息解析失败`);
    }
  };
  ws.onclose = () => {
    addLogLine("warn", `[Agent ${runId.slice(0, 8)}] 断开`);
    activeConnections.delete(runId);
  };
}
let primaryRunId = null;
/**
 * Update the multi-agent display panel.
 */
function updateMultiAgentDisplay() {
  const panel = document.getElementById("multiAgentPanel");
  if (!panel) return;
  let html = "";
  for (const [runId, ws] of activeConnections) {
    const buffer = runBuffers.get(runId) || [];
    const lastEvent = buffer.length > 0 ? buffer[buffer.length - 1] : null;
    const status = lastEvent ? (lastEvent.status_text_zh || lastEvent.event_type) : "connecting";
    const progress = lastEvent ? (lastEvent.progress_pct || 0) : 0;
    html += `
      <div class="agent-card ${runId === primaryRunId ? 'primary' : ''}"
           onclick="switchPrimaryAgent('${runId}')">
        <div class="agent-header">
          <span class="agent-id">${runId.slice(0, 10)}...</span>
          <span class="agent-status ${ws.readyState === WebSocket.OPEN ? 'online' : 'offline'}">
            ${ws.readyState === WebSocket.OPEN ? '●' : '○'}
          </span>
        </div>
        <div class="agent-progress">
          <div class="agent-progress-bar" style="width:${progress}%"></div>
        </div>
        <div class="agent-label">${status}</div>
        <div class="agent-event-count">${buffer.length} events</div>
      </div>`;
  }
  panel.innerHTML = html;
}
function switchPrimaryAgent(runId) {
  primaryRunId = runId;
  const buffer = runBuffers.get(runId) || [];
  for (const event of buffer) {
    applyEvent(event);
  }
  document.getElementById("runId").textContent = runId;
  updateMultiAgentDisplay();
  addLogLine("info", `切换到 Agent: ${runId.slice(0, 10)}`);
}
setInterval(updateMultiAgentDisplay, 2000);
/**
 * Load V11 panels data after history events are loaded.
 */
async function loadV11Panels(runId) {
  await Promise.allSettled([
    loadUnderstanding(runId),
    loadTokenBudget(runId),
    loadLearning(runId),
    loadMemoryHealth(),
  ]);
}
async function loadUnderstanding(runId) {
  try {
    const resp = await fetch(`/api/runs/${runId}/understanding`);
    if (resp.ok) {
      const data = await resp.json();
      renderUnderstandingPanel(data);
    }
  } catch (e) {
    renderErrorPanel("understandingContent", e.message);
  }
}
async function loadTokenBudget(runId) {
  try {
    const resp = await fetch(`/api/runs/${runId}/token`);
    if (resp.ok) {
      const data = await resp.json();
      renderTokenBudgetPanel(data);
    }
  } catch (e) {
    renderErrorPanel("tokenBudgetContent", e.message);
  }
}
async function loadLearning(runId) {
  try {
    const [learningResp, badcaseResp] = await Promise.all([
      fetch(`/api/runs/${runId}/learning`),
      fetch(`/api/runs/${runId}/badcases`),
    ]);
    if (learningResp.ok) {
      const data = await learningResp.json();
      renderSkillEvolutionPanel(data);
    }
    if (badcaseResp.ok) {
      const data = await badcaseResp.json();
      renderBadCasePanel(data);
    }
  } catch (e) {
    renderErrorPanel("badCaseContent", e.message);
  }
}
async function loadMemoryHealth() {
  try {
    const resp = await fetch("/api/memory/health");
    if (resp.ok) {
      const data = await resp.json();
      renderMemoryHealthPanel(data);
      renderMemoryMapPanel(data);
    }
  } catch (e) {
    renderErrorPanel("memoryHealthContent", e.message);
  }
}
function renderUnderstandingPanel(data) {
  const el = document.getElementById("understandingContent");
  if (!data.ok || !data.understanding_trace) {
    el.innerHTML = '<div class="empty-state"><div class="empty-icon">🧠</div>暂无理解轨迹数据</div>';
    return;
  }
  const t = data.understanding_trace;
  el.innerHTML = `
    <div class="v11-item"><span class="label">用户原话</span><span class="value">${esc(t.user_original_input || "").slice(0,60)}</span></div>
    <div class="v11-item"><span class="label">系统理解</span><span class="value">${esc(t.interpreted_goal || "").slice(0,60)}</span></div>
    <div class="v11-item"><span class="label">任务类型</span><span class="value"><span class="v11-tag blue">${esc(t.task_type || "unknown")}</span></span></div>
    <div class="v11-item"><span class="label">置信度</span><span class="value">${((t.confidence || 0) * 100).toFixed(0)}%</span></div>
    <div class="v11-item"><span class="label">需要确认</span><span class="value">${t.needs_user_confirmation ? '<span class="v11-tag orange">是</span>' : '<span class="v11-tag green">否</span>'}</span></div>
    ${(t.assumptions || []).length > 0 ? `<div class="v11-item"><span class="label">假设</span><span class="value">${t.assumptions.map(a => `<span class="v11-tag blue">${esc(a)}</span>`).join("")}</span></div>` : ""}
    ${(t.protected_constraints || []).length > 0 ? `<div class="v11-item"><span class="label">保护约束</span><span class="value">${t.protected_constraints.map(c => `<span class="v11-tag green">${esc(c)}</span>`).join("")}</span></div>` : ""}
    ${(t.uncertainties || []).length > 0 ? `<div class="v11-item"><span class="label">不确定点</span><span class="value">${t.uncertainties.map(u => `<span class="v11-tag orange">${esc(u)}</span>`).join("")}</span></div>` : ""}
    ${(t.semantic_risk_flags || []).length > 0 ? `<div class="v11-item"><span class="label">风险标记</span><span class="value">${t.semantic_risk_flags.map(f => `<span class="v11-tag red">${esc(f)}</span>`).join("")}</span></div>` : ""}
    ${(t.expression_matches || []).length > 0 ? `<div class="v11-item"><span class="label">表达习惯匹配</span><span class="value">${t.expression_matches.map(m => `<span class="v11-tag green">${esc(m.phrase || m.normalized_meaning || JSON.stringify(m))}</span>`).join("")}</span></div>` : ""}
  `;
}
function renderTokenBudgetPanel(data) {
  const el = document.getElementById("tokenBudgetContent");
  if (!data.ok || !data.token_report) {
    el.innerHTML = '<div class="empty-state"><div class="empty-icon">📊</div>暂无 Token 数据</div>';
    return;
  }
  const t = data.token_report;
  const ratio = ((t.saving_ratio || 0) * 100).toFixed(0);
  const barColor = t.risk_level === "high" ? "#bf360c" : t.risk_level === "medium" ? "#e65100" : "#2e7d32";
  el.innerHTML = `
    <div class="v11-item"><span class="label">Baseline Tokens</span><span class="value">${t.baseline_tokens_estimated || 0}</span></div>
    <div class="v11-item"><span class="label">Injected Tokens</span><span class="value">${t.injected_tokens || 0}</span></div>
    <div class="v11-item"><span class="label">Saved Tokens</span><span class="value">${t.saved_tokens_estimated || 0}</span></div>
    <div class="v11-item"><span class="label">Saving Ratio</span><span class="value">${ratio}%</span></div>
    <div class="v11-bar"><div class="v11-bar-fill" style="width:${ratio}%;background:${barColor}"></div></div>
    <div class="v11-item"><span class="label">Protected</span><span class="value">${(t.protected_items || []).length} 条</span></div>
    <div class="v11-item"><span class="label">Dropped</span><span class="value">${(t.dropped_items || []).length} 条</span></div>
    <div class="v11-item"><span class="label">Risk Level</span><span class="value"><span class="v11-tag ${t.risk_level === 'high' ? 'red' : t.risk_level === 'medium' ? 'orange' : 'green'}">${t.risk_level || "low"}</span></span></div>
    <!-- V11.2: estimation metadata -->
    <div class="v11-item"><span class="label">是否估算</span><span class="value"><span class="v11-tag ${t.is_estimated ? 'orange' : 'green'}">${t.is_estimated ? '是（估算）' : '否（实际）'}</span></span></div>
    <div class="v11-item"><span class="label">估算方法</span><span class="value">${esc(t.estimation_method || "unknown")}</span></div>
    ${t.summary_zh ? `<div style="margin-top:8px;font-size:11px;color:var(--text-secondary)">${esc(t.summary_zh)}</div>` : ""}
  `;
}
function renderBadCasePanel(data) {
  const el = document.getElementById("badCaseContent");
  if (!data.ok || !data.badcases || data.badcases.length === 0) {
    el.innerHTML = '<div class="empty-state"><div class="empty-icon">📋</div>本次未记录失败案例</div>';
    return;
  }
  let html = "";
  for (const bc of data.badcases) {
    html += `<div class="v11-item"><span class="label">${esc(bc.event_type || "bad_case")}</span><span class="value">${esc(bc.decision_summary_zh || bc.summary_zh || "").slice(0,60)}</span></div>`;
  }
  el.innerHTML = html;
}
function renderSkillEvolutionPanel(data) {
  const el = document.getElementById("skillEvolutionContent");
  const reviewEl = document.getElementById("skillReviewStatus");
  if (!data.ok || !data.summary || Object.keys(data.summary).length === 0) {
    el.innerHTML = '<div class="empty-state"><div class="empty-icon">🧬</div>暂无 Skill 进化数据</div>';
    if (reviewEl) reviewEl.innerHTML = "";
    return;
  }
  const s = data.summary;
  const hrLabel = {
    "pending": "⏳ 等待审核", "approved": "✅ 已通过", "rejected": "❌ 已拒绝",
    "validation_failed": "⚠️ 验证失败", "dry_run": "🧪 试运行", "none": "无需审核",
  };
  el.innerHTML = `
    <div class="v11-item"><span class="label">触发学习</span><span class="value">${s.learning_triggered ? '<span class="v11-tag orange">是</span>' : '<span class="v11-tag green">否</span>'}</span></div>
    <div class="v11-item"><span class="label">回归用例</span><span class="value">${s.regression_cases || 0}</span></div>
    <div class="v11-item"><span class="label">记忆候选</span><span class="value">${s.memory_candidates || 0}</span></div>
    <div class="v11-item"><span class="label">Skill Patches</span><span class="value">${s.skill_patches || 0}</span></div>
    <div class="v11-item"><span class="label">验证状态</span><span class="value">${s.validation_passed === true ? '<span class="v11-tag green">通过</span>' : s.validation_passed === false ? '<span class="v11-tag red">未通过</span>' : '--'}</span></div>
    <div class="v11-item"><span class="label">审核状态</span><span class="value">${hrLabel[s.human_review_status] || s.human_review_status || "--"}</span></div>
  `;
  if (reviewEl) {
    if (s.human_review_status === "pending") {
      reviewEl.innerHTML = '<span class="v11-tag orange">待人工审核</span> — 请前往审核队列确认';
    } else if (s.human_review_status === "validation_failed") {
      reviewEl.innerHTML = '<span class="v11-tag red">验证未通过</span> — Skill Patch 未进入审核';
    } else {
      reviewEl.innerHTML = "";
    }
  }
}
function renderMemoryMapPanel(data) {
  const el = document.getElementById("memoryMapContent");
  if (!data.ok || data.total_memories === 0) {
    el.innerHTML = '<div class="empty-state"><div class="empty-icon">🗂️</div>暂无长期记忆</div>';
    return;
  }
  el.innerHTML = `
    <div class="v11-item"><span class="label">总记忆数</span><span class="value">${data.total_memories || 0}</span></div>
    <div class="v11-item"><span class="label">建议保留</span><span class="value">${(data.suggest_keep || []).length} 条</span></div>
    <div class="v11-item"><span class="label">建议合并</span><span class="value">${(data.suggest_merge || []).length} 对</span></div>
    <div class="v11-item"><span class="label">建议删除</span><span class="value">${(data.suggest_delete || []).length} 条</span></div>
    <div class="v11-item"><span class="label">冲突记忆</span><span class="value">${(data.conflicts || []).length} 条</span></div>
    <div class="v11-item"><span class="label">高价值</span><span class="value">${(data.high_value_items || []).length} 条</span></div>
  `;
}
function renderMemoryHealthPanel(data) {
  const el = document.getElementById("memoryHealthContent");
  if (!data.ok) {
    el.innerHTML = '<div class="empty-state"><div class="empty-icon">💊</div>暂无记忆健康数据</div>';
    return;
  }
  el.innerHTML = `
    <div class="v11-item"><span class="label">总记忆数</span><span class="value">${data.total_memories || 0}</span></div>
    <div class="v11-item"><span class="label">建议保留</span><span class="value"><span class="v11-tag green">${(data.suggest_keep || []).length} 条</span></span></div>
    <div class="v11-item"><span class="label">建议合并</span><span class="value"><span class="v11-tag blue">${(data.suggest_merge || []).length} 对</span></span></div>
    <div class="v11-item"><span class="label">建议删除</span><span class="value"><span class="v11-tag red">${(data.suggest_delete || []).length} 条</span></span></div>
    <div class="v11-item"><span class="label">过期条目</span><span class="value"><span class="v11-tag orange">${(data.stale_items || []).length} 条</span></span></div>
    <div class="v11-item"><span class="label">冲突</span><span class="value">${(data.conflicts || []).length} 条</span></div>
    ${data.summary_zh ? `<div style="margin-top:8px;font-size:12px;color:var(--text-secondary)">${esc(data.summary_zh)}</div>` : ""}
  `;
}
function renderErrorPanel(panelId, error) {
  const el = document.getElementById(panelId);
  if (el) el.innerHTML = `<div class="empty-state" style="color:#bf360c">加载失败: ${esc(error)}</div>`;
}
function esc(text) {
  const d = document.createElement("div");
  d.textContent = text || "";
  return d.innerHTML;
}
function updateRecursiveHarnessPanels(evt) {
  if (!evt || typeof evt !== "object") return;
  const publicDecision = pickPublicDecisionFields(evt);
  if (evt.profile_hits) renderListPanel("rhProfileContent", evt.profile_hits, ["profile", "rule", "why_zh"]);
  if (evt.memory_hit_report) renderMemoryHitPanel(evt.memory_hit_report);
  if (evt.learning_impact_report) renderImpactPanel(evt.learning_impact_report);
  if (evt.si_report || evt.skill_hits) renderSkillHitPanel(evt.si_report || {skill_hits: evt.skill_hits});
  if (evt.research_findings) renderListPanel("rhResearchContent", evt.research_findings, ["title", "status", "source_url"]);
  if (evt.learning_impact_report && evt.learning_impact_report.candidate_created) {
    renderListPanel("rhCandidateContent", evt.learning_impact_report.candidate_created, ["type", "status"]);
  }
  if (evt.validation_ab) renderKeyValuePanel("rhValidationContent", evt.validation_ab);
  if (evt.human_review_queue) renderKeyValuePanel("rhReviewContent", evt.human_review_queue);
  if (evt.self_iteration_proposal) renderKeyValuePanel("rhSelfIterationContent", evt.self_iteration_proposal);
  if (publicDecision.decision_summary_zh || publicDecision.why_zh || publicDecision.next_step_zh) {
    const target = document.getElementById("rhImpactContent");
    if (target && !evt.learning_impact_report) {
      target.innerHTML = renderPublicDecision(publicDecision);
    }
  }
}
function pickPublicDecisionFields(evt) {
  return {
    decision_summary_zh: evt.decision_summary_zh || "",
    why_zh: evt.why_zh || "",
    evidence: Array.isArray(evt.evidence) ? evt.evidence : [],
    next_step_zh: evt.next_step_zh || "",
  };
}
function renderPublicDecision(data) {
  return `
    ${data.decision_summary_zh ? `<div class="v11-item"><span class="label">decision_summary_zh</span><span class="value">${esc(data.decision_summary_zh)}</span></div>` : ""}
    ${data.why_zh ? `<div class="v11-item"><span class="label">why_zh</span><span class="value">${esc(data.why_zh)}</span></div>` : ""}
    ${data.evidence.length ? `<div class="v11-item"><span class="label">evidence</span><span class="value">${data.evidence.map(x => esc(String(x))).join(" | ")}</span></div>` : ""}
    ${data.next_step_zh ? `<div class="v11-item"><span class="label">next_step_zh</span><span class="value">${esc(data.next_step_zh)}</span></div>` : ""}
  `;
}
function renderListPanel(panelId, items, keys) {
  const el = document.getElementById(panelId);
  if (!el) return;
  if (!Array.isArray(items) || items.length === 0) {
    el.innerHTML = '<div class="empty-state">暂无数据</div>';
    return;
  }
  el.innerHTML = items.slice(0, 6).map((item) => {
    const rows = keys.map((key) => {
      const value = item && typeof item === "object" ? item[key] : "";
      return `<div class="v11-item"><span class="label">${esc(key)}</span><span class="value">${esc(formatPublicValue(value))}</span></div>`;
    }).join("");
    return `<div style="margin-bottom:8px">${rows}</div>`;
  }).join("");
}
function renderKeyValuePanel(panelId, data) {
  const el = document.getElementById(panelId);
  if (!el) return;
  if (!data || data.status === "none") {
    el.innerHTML = '<div class="empty-state">暂无数据</div>';
    return;
  }
  const allowed = ["status", "reason_zh", "decision_summary_zh", "why_zh", "next_step_zh", "queue_count", "proposal_id", "branch_name"];
  el.innerHTML = allowed
    .filter((key) => data[key] !== undefined && data[key] !== null && data[key] !== "")
    .map((key) => `<div class="v11-item"><span class="label">${esc(key)}</span><span class="value">${esc(formatPublicValue(data[key]))}</span></div>`)
    .join("") || '<div class="empty-state">暂无数据</div>';
}
function renderMemoryHitPanel(report) {
  const hits = report.memory_hits || [];
  renderListPanel("rhMemoryContent", hits, ["memory_id", "reason_zh", "source"]);
}
function renderSkillHitPanel(report) {
  const skillHits = report.skill_hits || [];
  if (skillHits.length) {
    renderListPanel("rhSkillContent", skillHits, ["skill", "status"]);
    return;
  }
  const patches = report.skill_patches || [];
  if (patches.length) {
    renderListPanel("rhSkillContent", patches.map(() => ({skill: "candidate_skill_patch", status: "等待验证"})), ["skill", "status"]);
    return;
  }
  renderListPanel("rhSkillContent", [], ["skill", "status"]);
}
function renderImpactPanel(report) {
  const el = document.getElementById("rhImpactContent");
  if (!el) return;
  if (!report) {
    el.innerHTML = '<div class="empty-state">暂无 impact report</div>';
    return;
  }
  el.innerHTML = `
    <div class="v11-item"><span class="label">overall</span><span class="value">${formatScore(report.overall_impact_score)}</span></div>
    <div class="v11-item"><span class="label">personalization</span><span class="value">${formatScore(report.personalization_score)}</span></div>
    <div class="v11-item"><span class="label">memory</span><span class="value">${formatScore(report.memory_impact_score)}</span></div>
    <div class="v11-item"><span class="label">skill</span><span class="value">${formatScore(report.skill_impact_score)}</span></div>
    <div class="v11-item"><span class="label">token</span><span class="value">${formatScore(report.token_impact_score)}</span></div>
    <div class="v11-item"><span class="label">summary</span><span class="value">${esc(report.user_visible_summary_zh || "")}</span></div>
  `;
}
function formatScore(value) {
  const num = Number(value || 0);
  return `${Math.round(num * 100)}%`;
}
function formatPublicValue(value) {
  if (Array.isArray(value)) return value.map((x) => String(x)).join(" | ");
  if (value && typeof value === "object") return value.decision_summary_zh || value.why_zh || value.status || JSON.stringify(value);
  return String(value || "");
}
const _originalApplyEvent = applyEvent;
async function feedbackRemember() {
  if (!runId) return;
  const el = document.getElementById("feedbackResult");
  el.textContent = "提交中...";
  try {
    const resp = await fetch("/api/feedback/remember", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({run_id: runId, user_note: "用户标记: 记住这个"}),
    });
    const data = await resp.json();
    el.textContent = data.ok ? data.summary_zh : "提交失败";
    el.style.color = data.ok ? "#2e7d32" : "#bf360c";
  } catch (e) {
    el.textContent = "网络错误";
    el.style.color = "#bf360c";
  }
}
async function feedbackDontDoThis() {
  if (!runId) return;
  const el = document.getElementById("feedbackResult");
  el.textContent = "提交中...";
  try {
    const resp = await fetch("/api/feedback/dont-do-this-again", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({run_id: runId, user_note: "用户标记: 下次别这样"}),
    });
    const data = await resp.json();
    el.textContent = data.ok ? data.summary_zh : "提交失败";
    el.style.color = data.ok ? "#2e7d32" : "#bf360c";
  } catch (e) {
    el.textContent = "网络错误";
    el.style.color = "#bf360c";
  }
}
async function feedbackCorrectAndRemember() {
  if (!runId) return;
  const correction = prompt("请输入纠正内容:");
  if (!correction) return;
  const el = document.getElementById("feedbackResult");
  el.textContent = "提交中...";
  try {
    const resp = await fetch("/api/feedback/correct-and-remember", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({run_id: runId, user_note: correction}),
    });
    const data = await resp.json();
    el.textContent = data.ok ? data.summary_zh : "提交失败";
    el.style.color = data.ok ? "#2e7d32" : "#bf360c";
  } catch (e) {
    el.textContent = "网络错误";
    el.style.color = "#bf360c";
  }
}
/**
 * "理解正确" — POST /api/feedback/remember
 */
async function feedbackUnderstandingCorrect() {
  if (!runId) return;
  const el = document.getElementById("feedbackResult");
  el.textContent = "提交中...";
  try {
    const resp = await fetch("/api/feedback/remember", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({run_id: runId, note: "本次语义理解正确", context: {source: "understanding_panel"}}),
    });
    const data = await resp.json();
    el.textContent = data.ok ? "✅ 已确认理解正确" : "提交失败";
    el.style.color = data.ok ? "#2e7d32" : "#bf360c";
    if (data.ok) refreshV11Panels();
  } catch (e) {
    el.textContent = "网络错误";
    el.style.color = "#bf360c";
  }
}
/**
 * "有偏差，纠正" — POST /api/feedback/correct-and-remember
 */
async function feedbackUnderstandingFix() {
  if (!runId) return;
  const wrongPart = prompt("你刚才哪里理解错了？");
  if (!wrongPart) return;
  const correctMeaning = prompt("正确理解应该是什么？");
  if (!correctMeaning) return;
  const el = document.getElementById("feedbackResult");
  el.textContent = "提交中...";
  try {
    const resp = await fetch("/api/feedback/correct-and-remember", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        run_id: runId,
        note: `${wrongPart} → ${correctMeaning}`,
        context: {phrase: wrongPart, corrected_meaning: correctMeaning, source: "understanding_panel"},
      }),
    });
    const data = await resp.json();
    el.textContent = data.ok ? `✅ ${data.summary_zh || "已记录纠正"}` : "提交失败";
    el.style.color = data.ok ? "#2e7d32" : "#bf360c";
    if (data.ok) refreshV11Panels();
  } catch (e) {
    el.textContent = "网络错误";
    el.style.color = "#bf360c";
  }
}
/**
 * Memory action buttons — placeholder for future MCP integration
 */
function memoryAction(action) {
  const el = document.getElementById("memoryActionResult");
  const labels = {keep: "保留", delete: "删除", defer: "稍后处理"};
  el.textContent = `已记录决策: ${labels[action] || action}（第一版仅记录，不执行删除）`;
  el.style.color = "#0071e3";
  addLogLine("info", `Memory action: ${action}`);
}
/**
 * "生成回归测试" — show eval_case_id if available
 */
async function generateRegressionTest() {
  if (!runId) return;
  const el = document.getElementById("regressionTestResult");
  el.textContent = "查询中...";
  try {
    const resp = await fetch(`/api/runs/${runId}/badcases`);
    if (resp.ok) {
      const data = await resp.json();
      if (data.badcases && data.badcases.length > 0) {
        const evalId = data.badcases[0].eval_case_id || data.badcases[0].payload?.eval_case_id;
        el.textContent = evalId ? `已有关联回归测试: ${evalId}` : "失败案例已记录，回归测试将在下次反馈时自动生成";
      } else {
        el.textContent = "暂无失败案例，请先点击「下次别这样」记录";
      }
    }
  } catch (e) {
    el.textContent = "查询失败";
  }
}
/**
 * Auto-refresh V11 panels after feedback
 */
async function refreshV11Panels() {
  if (!runId) return;
  await Promise.allSettled([
    loadUnderstanding(runId),
    loadTokenBudget(runId),
    loadLearning(runId),
    loadMemoryHealth(),
  ]);
}
if (runId) {
  setTimeout(() => loadV11Panels(runId), 1500);
}
/**
 * Check if the current run_id has associated effectiveness A/B data.
 * If so, show a small badge/card in the observer page linking to the comparison.
 */
async function checkEffectivenessForRun(runId) {
  try {
    const resp = await fetch(`/api/effectiveness/summary?run_id=${encodeURIComponent(runId)}`);
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data.ok || !data.data) return;
    const summary = data.data;
    if ((summary.baseline_count || 0) < 1 && (summary.stableagent_count || 0) < 1) return;
    const verdictLabel = {
      "effective": "✅ 已验证有效",
      "promising": "🔶 有潜力",
      "not_effective": "⚠️ 未见效",
      "insufficient_data": "⏳ 数据不足",
    }[summary.verdict] || "⏳ 评估中";
    const verdictColor = {
      "effective": "#2e7d32",
      "promising": "#e65100",
      "not_effective": "#bf360c",
      "insufficient_data": "#86868b",
    }[summary.verdict] || "#86868b";
    const effBadge = document.createElement("div");
    effBadge.id = "effectivenessBadge";
    effBadge.style.cssText = `
      margin-top:16px;
      background:var(--glass-bg);
      backdrop-filter:blur(24px);
      border:1px solid var(--glass-border);
      border-radius:12px;
      padding:12px 16px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
    `;
    effBadge.innerHTML = `
      <div>
        <div style="font-size:13px;font-weight:600;color:${verdictColor}">${verdictLabel}</div>
        <div style="font-size:11px;color:var(--text-secondary)">
          baseline: ${summary.baseline_count || 0} runs · stableagent: ${summary.stableagent_count || 0} runs
        </div>
      </div>
      <a href="/effectiveness?run_id=${encodeURIComponent(runId)}" style="font-size:12px;color:var(--accent);text-decoration:none;white-space:nowrap">查看详情 →</a>
    `;
    const statusCard = document.getElementById("statusCard");
    if (statusCard && statusCard.parentNode) {
      statusCard.parentNode.appendChild(effBadge);
    }
  } catch (e) {
  }
}
