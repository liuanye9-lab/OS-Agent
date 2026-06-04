// run_observer.js — Dashboard Observer 前端逻辑
// 后端事件驱动，前端不猜进度、不伪造状态

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

// Emoji fallback (when no Canvas avatar available)
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

// ========== State ==========
let logs = [];
let timelineItems = [];

// V9.0: 阶段中文标签映射
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

// ========== DOM refs ==========
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

// ========== URL param ==========
const params = new URLSearchParams(window.location.search);

// V11.4: 从三个位置获取 run_id（按优先级）：
// 1. URL 查询参数 ?run_id=xxx
// 2. 页面 meta 标签 <meta name="run-id" content="xxx">
// 3. URL 路径 /observe/{run_id}
let runId = params.get("run_id");

if (!runId) {
  // 尝试从 meta 标签获取（由 /observe/{run_id} 路由注入）
  const metaEl = document.querySelector('meta[name="run-id"]');
  if (metaEl) {
    runId = metaEl.getAttribute("content");
  }
}

if (!runId) {
  // 尝试从 URL 路径提取 /observe/{run_id}
  const pathMatch = window.location.pathname.match(/^\/observe\/([^\/]+)$/);
  if (pathMatch) {
    runId = pathMatch[1];
  }
}

if (runId) {
  $runId.textContent = runId;
  const v3Link = document.getElementById("v3Link");
  if (v3Link) v3Link.href = `/runs/${runId}`;
  // V11.3.1: 效果评估链接带上 run_id
  const effLink = document.getElementById("effLink");
  if (effLink) effLink.href = `/effectiveness?run_id=${encodeURIComponent(runId)}`;
  // V9.2: 先 API 回放历史事件，再 WebSocket 实时订阅
  loadHistoryAndConnect(runId);
  // V11.3.1: 页面加载后检查是否有当前 run_id 的效果评估数据，显示快捷入口
  checkEffectivenessForRun(runId);
} else {
  // 没有 run_id 时显示提示
  addLogLine("warn", "未提供 run_id 参数");
  $mcpStatus.textContent = "未连接";
  $mcpStatus.className = "mcp-status disconnected";
}

// ========== API History Replay + WebSocket ==========
async function loadHistoryAndConnect(runId) {
  let historyEvents = [];
  let apiEventCount = 0;
  let dashboardReplayOk = false;
  let apiOk = false;

  addLogLine("info", `开始加载历史事件: ${runId}`);

  // Step 1: 请求 API 获取历史事件
  try {
    const resp = await fetch(`/api/runs/${runId}/events`);

    if (resp.ok) {
      apiOk = true;
      const data = await resp.json();
      // V10: 结构化返回 { run_id, event_count, events: [...] }
      if (data && typeof data === "object" && Array.isArray(data.events)) {
        historyEvents = data.events;
        apiEventCount = data.event_count || historyEvents.length;
      } else if (Array.isArray(data) && data.length > 0) {
        // 兼容旧版直接返回列表
        historyEvents = data;
        apiEventCount = data.length;
      }

      if (historyEvents.length > 0) {
        // V11.4: 回放历史事件到 UI
        addLogLine("info", `API 返回 ${historyEvents.length} 个事件，开始回放...`);
        for (const evt of historyEvents) {
          applyEvent(evt);
        }
        addLogLine("info", `✅ API 回放 ${historyEvents.length} 个历史事件 (event_count=${apiEventCount})`);
        dashboardReplayOk = true;

        // V11.4: 检查是否有完成事件
        const hasCompletedEvent = historyEvents.some(evt =>
          evt.event_type === "run.completed" ||
          evt.event_type === "run.finished" ||
          evt.progress_pct >= 100
        );

        if (hasCompletedEvent) {
          addLogLine("info", "✅ 检测到完成事件");
        }
      } else {
        addLogLine("warn", "API 返回事件列表为空");
      }

      // 更新 API 状态显示
      updateEventApiStatus(true, apiEventCount, dashboardReplayOk);
    } else if (resp.status === 404) {
      addLogLine("warn", `Run ${runId} 不存在 (404)`);
      updateEventApiStatus(false, 0, false);
      // V11.4: 显示明确错误
      $nowStatus.textContent = "运行不存在";
      $whyText.textContent = `Run ID: ${runId} 未找到`;
    } else {
      addLogLine("warn", `API 返回 HTTP ${resp.status}`);
      updateEventApiStatus(false, 0, false);
      // V11.4: 显示 API 错误
      $nowStatus.textContent = "事件 API 读取失败";
      $whyText.textContent = `HTTP ${resp.status}`;
    }
  } catch (err) {
    console.error("API 回放失败:", err);
    addLogLine("error", `API 回放失败: ${err.message}`);
    updateEventApiStatus(false, 0, false);
    // V11.4: 显示网络错误
    $nowStatus.textContent = "事件 API 读取失败";
    $whyText.textContent = err.message;
  }

  // Step 2: 连接 WebSocket 获取实时事件
  connectWebSocket(runId);

  // Step 3: 如果 API 和 WebSocket 都无事件，显示提示
  setTimeout(() => {
    const ws = activeConnections.get(runId);
    const wsConnected = ws && ws.readyState === WebSocket.OPEN;

    if (!apiOk) {
      showSyncError("事件 API 读取失败，请检查后端服务");
    } else if (historyEvents.length === 0 && !wsConnected) {
      showSyncError("暂无历史事件，WebSocket 也未连接");
    } else if (historyEvents.length === 0 && wsConnected) {
      addLogLine("info", "暂无历史事件，等待实时事件...");
      showHistoryEmptyNotice();
      $nowStatus.textContent = "等待事件";
      $whyText.textContent = "暂无历史事件，等待实时事件流";
    } else if (historyEvents.length > 0 && !dashboardReplayOk) {
      showSyncError("事件回放失败");
    }
  }, 3000);
}

// V10: 更新 API 状态显示
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

// V9.2: 显示同步错误
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

// V9.2: 历史事件为空但 WebSocket 有实时事件的提示
function showHistoryEmptyNotice() {
  const notice = document.createElement("div");
  notice.className = "history-empty-notice";
  notice.textContent = "⚠️ 历史事件为空，仅显示实时事件";
  if ($timelineCol && $timelineCol.parentNode) {
    $timelineCol.parentNode.insertBefore(notice, $timelineCol);
  }
}

// ========== WebSocket ==========
function connectWebSocket(runId) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl    = `${protocol}//${location.host}/dashboard-sync/ws/runs/${runId}`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    $mcpStatus.textContent = "已连接";
    $mcpStatus.className   = "mcp-status";
    addLogLine("info", `WebSocket 已连接: ${runId}`);
    // V9.2: 记录到 activeConnections 供 loadHistoryAndConnect 检查
    activeConnections.set(runId, ws);
    if (!primaryRunId) primaryRunId = runId;
    // V10: 更新 WebSocket 状态显示
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

// ========== Apply Event ==========
function applyEvent(evt) {
  addLogLine("info", `收到事件: ${evt.event_type || evt.type || "unknown"}`);

  // V9.0: 事件同步异常检查
  if (evt.event_sync_ok === false) {
    showSyncWarning();
  }

  // 1. Update progress
  if (evt.progress_pct !== undefined) {
    updateProgress(evt.progress_pct, evt.status_text_zh || evt.stage_label_zh || "");
  }

  // 2. Update avatar
  if (evt.avatar_state) {
    updateAvatar(evt.avatar_state);
  }

  // 3. Update status card text
  updateStatusCard(evt);

  // 4. Append timeline
  appendTimeline(evt);

  // 5. Update Self-Improvement Report
  if (evt.si_report || evt.self_improvement || evt.learning_triggered !== undefined) {
    updateSIReport(evt.si_report || evt.self_improvement || evt);
  }

  // 6. V11.1: Update V11 panels on real-time events
  if (evt.event_type === "understanding.trace.created" && evt.understanding_trace) {
    renderUnderstandingPanel({ok: true, understanding_trace: evt.understanding_trace});
  }
  if (evt.event_type === "token.budget.estimated" && evt.token_report) {
    renderTokenBudgetPanel({ok: true, token_report: evt.token_report});
  }
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

  // 6. Update task name
  if (evt.run_id && evt.run_id !== $runId.textContent) {
    $runId.textContent = evt.run_id;
  }
}

// ========== Update Progress ==========
function updateProgress(pct, label) {
  const safe = Math.max(0, Math.min(100, pct));
  $progressPct.textContent = `${safe}%`;
  $progressBar.style.width = `${safe}%`;
  $progressText.textContent = label ? `${safe}% — ${label}` : `${safe}%`;

  if (safe >= 100) {
    $progressPct.style.color = "#34c759";
  } else if (safe >= 80) {
    $progressPct.style.color = "#0071e3";
  } else {
    $progressPct.style.color = "#1d1d1f";
  }
}

// ========== Update Avatar ==========
function updateAvatar(state) {
  const info = AVATAR_SCENE_MAP[state] || AVATAR_SCENE_MAP.idle;

  // Canvas pixel avatar (from avatar_scene.js)
  if (typeof renderAvatarScene === "function") {
    renderAvatarScene(info.scene, "avatarCanvas");
  }

  // Emoji fallback shown inside canvas as well
  $sceneLabel.textContent = info.labelZh;
  $sceneProp.textContent = `场景: ${info.scene} | 道具: ${info.prop}`;
}

// ========== Update Status Card ==========
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

// ========== Append Timeline ==========
function appendTimeline(evt) {
  // Remove empty state
  if ($timelineEmpty) {
    $timelineEmpty.remove();
    // reclaim reference
    window._timelineEmptyRemoved = true;
  }

  const stage = evt.stage_label_zh || evt.stage || "";
  const what  = evt.what_happened_zh || evt.status_text_zh || evt.event_type || "";
  const pct   = evt.progress_pct !== undefined ? `${evt.progress_pct}%` : "";

  // V9.0: 阶段中文标签
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

  // Limit to 50 items
  while (timelineItems.length > 50) {
    const old = timelineItems.shift();
    if (old) old.remove();
  }
}

// ========== Update Self-Improvement Report ==========
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

  // V9.0: 验证状态显式显示
  const valEl = document.getElementById("siValidation");
  valEl.querySelector(".si-value").textContent =
    report.validation_passed === true ? "✅ 通过" :
    report.validation_passed === false ? "❌ 未通过" : "--";
  valEl.className = report.validation_passed ? "si-item ok" : "si-item warn";

  // V9.0: 审核状态完整展示
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

  // V9.0: 导出状态 — approved 不等于已导出
  document.getElementById("siExport").querySelector(".si-value").textContent =
    report.best_skill_exported ? "✅ 已导出" : "未导出";

  document.getElementById("siSummary").querySelector(".si-value").textContent =
    report.summary_zh || "--";
}

// V9.0: 显示同步异常
function showSyncWarning() {
  const banner = document.getElementById("syncWarning");
  if (banner) {
    banner.style.display = "flex";
  }
}

// ========== Log ==========
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

// ========== Utility ==========
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

// ==================================================================
// V8.0: Multi-Agent Collaboration — parallel run observation
// ==================================================================

// Active WebSocket connections (runId → WebSocket)
const activeConnections = new Map();
// Per-run event buffers (runId → events[])
const runBuffers = new Map();

/**
 * Observe multiple runs in parallel.
 * @param {string[]} runIds - list of run IDs to observe
 */
function observeMultipleRuns(runIds) {
  // Close existing connections
  for (const [id, ws] of activeConnections) {
    if (!runIds.includes(id)) {
      ws.close();
      activeConnections.delete(id);
      runBuffers.delete(id);
    }
  }

  // Open new connections
  for (const runId of runIds) {
    if (!activeConnections.has(runId)) {
      connectMultiAgentWebSocket(runId);
    }
  }

  // Update display
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

      // If this is the "primary" run, also apply to main UI
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

  // Replay all events to main UI
  for (const event of buffer) {
    applyEvent(event);
  }
  // Update display
  document.getElementById("runId").textContent = runId;
  updateMultiAgentDisplay();
  addLogLine("info", `切换到 Agent: ${runId.slice(0, 10)}`);
}

// Auto-refresh multi-agent display every 2 seconds
setInterval(updateMultiAgentDisplay, 2000);

// ==================================================================
// V11.1: Six Panels + Feedback Buttons
// ==================================================================

/**
 * Load V11 panels data after history events are loaded.
 */
async function loadV11Panels(runId) {
  // Load in parallel
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

// ========== Render Functions ==========

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
  // V11.2: Show review status detail
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

// ========== Real-time V11 event handling ==========
// Patch applyEvent to handle V11 events
const _originalApplyEvent = applyEvent;
// We can't reassign applyEvent since it's already used, so we extend it via a wrapper
// Instead, we'll add V11 handling in the existing applyEvent by extending the WebSocket handler

// ========== Feedback Buttons ==========
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

// ==================================================================
// V11.2: Intervention Buttons + Auto-refresh
// ==================================================================

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

// Load V11 panels after history is loaded
if (runId) {
  setTimeout(() => loadV11Panels(runId), 1500);
}

// ==================================================================
// V12.1: Learning Impact Report
// ==================================================================

/**
 * Load Learning Impact Report from events API.
 */
async function loadImpactReport(runId) {
  try {
    const resp = await fetch(`/api/runs/${runId}/events`);
    if (!resp.ok) return;
    const data = await resp.json();
    const events = (data && Array.isArray(data.events)) ? data.events : (Array.isArray(data) ? data : []);
    if (events.length === 0) return;

    // Extract token_report and si_report from events
    let tokenReport = null;
    let siReport = null;
    let curatorReport = null;
    for (const evt of events) {
      if (evt.event_type === "token.budget.estimated" && evt.token_report) {
        tokenReport = evt.token_report;
      }
      if (evt.si_report) {
        siReport = evt.si_report;
      }
      if (evt.learning_triggered !== undefined) {
        siReport = siReport || {};
        siReport.learning_triggered = evt.learning_triggered;
        siReport.validation_passed = evt.validation_passed;
        siReport.skill_patches = evt.skill_patches || [];
        siReport.human_review_required = evt.human_review_required;
        siReport.best_skill_exported = evt.best_skill_exported || false;
      }
    }

    // Build impact report client-side (lightweight scoring)
    const report = buildImpactReportClient(events, tokenReport, siReport, curatorReport);
    if (report) {
      renderImpactReport(report);
    }
  } catch (e) {
    console.error("Impact report load failed:", e);
  }
}

/**
 * Client-side impact report builder (mirrors Python LearningImpactBuilder logic).
 */
function buildImpactReportClient(events, tokenReport, siReport, curatorReport) {
  const report = {
    run_id: runId || "",
    overall_impact_score: 0,
    memory_impact_score: 0,
    token_impact_score: 0,
    skill_impact_score: 0,
    personalization_score: 0,
    memory_hits: [],
    token_impact: null,
    skills_used: [],
    skill_candidates_created: [],
    what_improved_zh: [],
    what_did_not_improve_zh: [],
    next_learning_actions_zh: [],
    user_visible_summary_zh: "",
  };

  // 1. Memory Impact
  const memEvt = events.find(e => e.event_type === "temporal_memory.retrieved");
  if (memEvt) {
    const selected = memEvt.selected_memories || [];
    const count = memEvt.count || selected.length;
    if (count > 0) {
      report.memory_hits = selected.slice(0, 5).map(m => ({
        memory_id: m.memory_id || "",
        content_preview: (m.reason_zh || "").slice(0, 80),
        reason_zh: m.reason_zh || "相关性匹配",
        used_in_stage: "temporal_memory_retrieving",
        confidence: m.confidence || 0.7,
      }));
      report.memory_impact_score = Math.min(1.0, count / 5.0);
      report.what_improved_zh.push(`本次命中 ${count} 条历史记忆，提升了任务个性化程度。`);
    } else {
      report.what_did_not_improve_zh.push("本次没有命中历史记忆，不会产生明显个性化提升。");
    }
  }

  // 2. Token Impact
  if (tokenReport && typeof tokenReport === "object") {
    const saved = tokenReport.saved_tokens_estimated || 0;
    const baseline = tokenReport.baseline_tokens_estimated || 0;
    const ratio = tokenReport.saving_ratio || 0;
    report.token_impact = {
      baseline_tokens_estimated: baseline,
      injected_tokens: tokenReport.injected_tokens || 0,
      dropped_tokens: tokenReport.dropped_tokens || 0,
      saved_tokens_estimated: saved,
      saving_ratio: ratio,
      summary_zh: tokenReport.summary_zh || "",
      is_estimated: tokenReport.is_estimated !== false,
    };
    if (ratio > 0) {
      report.token_impact_score = Math.min(0.8, ratio);
      report.what_improved_zh.push(`本次通过上下文压缩节省了约 ${Math.round(ratio * 100)}% token。`);
    } else if (baseline < 500) {
      report.what_did_not_improve_zh.push("本次上下文较短，token 优化体感不明显。");
    }
  } else {
    report.what_did_not_improve_zh.push("本次上下文较短或无 token 压缩数据，token 优化体感不明显。");
  }

  // 3. Skill Impact
  let skillScore = 0;
  if (curatorReport && curatorReport.candidates_created > 0) {
    skillScore += 0.4;
    for (let i = 0; i < curatorReport.candidates_created; i++) {
      report.skill_candidates_created.push({
        skill_id: `candidate_${i + 1}`,
        status: "candidate",
        reason_zh: "Curator 从本次运行中提炼出改进规则",
        used: false,
        generated_this_run: true,
        needs_validation: true,
        needs_human_review: false,
      });
    }
    report.next_learning_actions_zh.push("已生成 candidate skill，需要后续相关任务验证。");
  }
  if (siReport && typeof siReport === "object") {
    if (siReport.learning_triggered) skillScore += 0.2;
    const patches = siReport.skill_patches || [];
    if (patches.length > 0) {
      skillScore += 0.2;
      for (const p of patches) {
        report.skill_candidates_created.push({
          skill_id: p.patch_id || "",
          status: "candidate",
          reason_zh: `针对 ${p.failure_mode || "未知"} 模式生成的改进规则`,
          used: false,
          generated_this_run: true,
          needs_validation: !siReport.validation_passed,
          needs_human_review: !!siReport.human_review_required,
        });
      }
    }
    if (siReport.validation_passed) {
      skillScore += 0.2;
      report.what_improved_zh.push("Skill 验证通过，改进已确认有效。");
    }
    if (siReport.human_review_required) {
      report.next_learning_actions_zh.push("有 skill patch 等待人工审核。");
    }
    if (siReport.best_skill_exported) {
      skillScore += 0.1;
      report.what_improved_zh.push("最佳 skill 已导出。");
    }
  }
  report.skill_impact_score = Math.min(1.0, skillScore);
  if (skillScore === 0) {
    report.what_did_not_improve_zh.push("本次未使用 promoted skill，也未触发技能更新。");
  }

  // 4. Personalization
  report.personalization_score = Math.round((0.4 * report.memory_impact_score + 0.3 * report.skill_impact_score + 0.3 * 0) * 10000) / 10000;

  // 5. Overall
  report.overall_impact_score = Math.round((0.25 * report.memory_impact_score + 0.25 * report.token_impact_score + 0.30 * report.skill_impact_score + 0.20 * report.personalization_score) * 10000) / 10000;

  // 6. Low score honesty
  if (report.overall_impact_score < 0.3) {
    const lowReasons = [];
    if (report.memory_impact_score < 0.2) lowReasons.push("历史记忆不足");
    if (report.skill_impact_score < 0.2) lowReasons.push("未命中已验证 skill");
    if (report.token_impact_score < 0.2) lowReasons.push("token 优化不明显");
    if (lowReasons.length === 0) lowReasons.push("任务较简单或缺少用户反馈");
    report.what_did_not_improve_zh.push(`本次个性化提升较弱，原因可能是：${lowReasons.join("、")}。`);
  }

  // 7. Summary
  const pct = Math.round(report.overall_impact_score * 100);
  const summaryParts = [`本次学习提升: ${pct}%`];
  if (report.memory_hits.length > 0) summaryParts.push(`命中 ${report.memory_hits.length} 条记忆`);
  if (report.token_impact && report.token_impact.saved_tokens_estimated > 0) summaryParts.push(`节省约 ${report.token_impact.saved_tokens_estimated} token`);
  if (report.skill_candidates_created.length > 0) summaryParts.push(`生成 ${report.skill_candidates_created.length} 个候选 skill`);
  if (report.overall_impact_score < 0.3) summaryParts.push("体感提升较弱，建议继续积累历史数据。");
  report.user_visible_summary_zh = summaryParts.join(" | ");

  return report;
}

/**
 * Render Learning Impact Report into the dashboard panel.
 */
function renderImpactReport(report) {
  const bar = document.getElementById("impactReportBar");
  if (!bar) return;
  bar.style.display = "block";

  // Score cards
  const scoreConfigs = [
    { id: "impactOverall", value: report.overall_impact_score },
    { id: "impactMemory", value: report.memory_impact_score },
    { id: "impactToken", value: report.token_impact_score },
    { id: "impactSkill", value: report.skill_impact_score },
  ];
  for (const cfg of scoreConfigs) {
    const el = document.getElementById(cfg.id);
    if (!el) continue;
    const pct = Math.round(cfg.value * 100);
    el.querySelector(".impact-score-value").textContent = `${pct}%`;
    el.className = `impact-score-card ${pct >= 50 ? "high" : pct >= 20 ? "medium" : "low"}`;
  }

  // Memory hits
  const memEl = document.getElementById("impactMemoryHits");
  if (memEl) {
    if (report.memory_hits.length === 0) {
      memEl.innerHTML = '<div class="empty-state" style="padding:12px"><div class="empty-icon">🗂️</div>本次未命中历史记忆</div>';
    } else {
      let html = '<div class="impact-list">';
      for (const m of report.memory_hits) {
        html += `<li class="positive">${esc(m.content_preview || m.reason_zh)} <span style="color:var(--text-secondary);font-size:11px">(${Math.round(m.confidence * 100)}%)</span></li>`;
      }
      html += "</div>";
      memEl.innerHTML = html;
    }
  }

  // Token detail
  const tokenEl = document.getElementById("impactTokenDetail");
  if (tokenEl) {
    if (!report.token_impact) {
      tokenEl.innerHTML = '<div class="empty-state" style="padding:12px"><div class="empty-icon">📊</div>无 Token 数据</div>';
    } else {
      const t = report.token_impact;
      const ratio = Math.round(t.saving_ratio * 100);
      tokenEl.innerHTML = `
        <div class="impact-item"><span class="impact-label">Baseline</span><span class="impact-value">${t.baseline_tokens_estimated} tokens</span></div>
        <div class="impact-item"><span class="impact-label">Saved</span><span class="impact-value">${t.saved_tokens_estimated} tokens (${ratio}%)</span></div>
        <div class="v11-bar"><div class="v11-bar-fill" style="width:${ratio}%;background:${ratio > 30 ? "#2e7d32" : ratio > 10 ? "#e65100" : "#86868b"}"></div></div>
        ${t.summary_zh ? `<div style="font-size:11px;color:var(--text-secondary);margin-top:4px">${esc(t.summary_zh)}</div>` : ""}
      `;
    }
  }

  // Skill detail
  const skillEl = document.getElementById("impactSkillDetail");
  if (skillEl) {
    const candidates = report.skill_candidates_created || [];
    if (candidates.length === 0 && report.skills_used.length === 0) {
      skillEl.innerHTML = '<div class="empty-state" style="padding:12px"><div class="empty-icon">🧬</div>本次未触发 Skill 更新</div>';
    } else {
      let html = "";
      for (const s of report.skills_used) {
        html += `<div class="impact-item"><span class="impact-label">${esc(s.skill_id)}</span><span class="v11-tag green">已使用</span></div>`;
      }
      for (const s of candidates) {
        const tag = s.needs_validation ? '<span class="v11-tag orange">待验证</span>' : '<span class="v11-tag green">已验证</span>';
        html += `<div class="impact-item"><span class="impact-label">${esc(s.skill_id)}</span>${tag}</div>`;
      }
      skillEl.innerHTML = html;
    }
  }

  // Improved / Not improved
  const improvedEl = document.getElementById("impactImproved");
  if (improvedEl) {
    const items = report.what_improved_zh || [];
    if (items.length > 0) {
      let html = '<ul class="impact-list">';
      for (const item of items) html += `<li class="positive">${esc(item)}</li>`;
      html += "</ul>";
      improvedEl.innerHTML = html;
    } else {
      improvedEl.innerHTML = "";
    }
  }
  const notImprovedEl = document.getElementById("impactNotImproved");
  if (notImprovedEl) {
    const items = report.what_did_not_improve_zh || [];
    if (items.length > 0) {
      let html = '<ul class="impact-list">';
      for (const item of items) html += `<li class="negative">${esc(item)}</li>`;
      html += "</ul>";
      notImprovedEl.innerHTML = html;
    } else {
      notImprovedEl.innerHTML = "";
    }
  }

  // Next actions
  const nextEl = document.getElementById("impactNextActions");
  if (nextEl) {
    const items = report.next_learning_actions_zh || [];
    if (items.length > 0) {
      let html = '<ul class="impact-list">';
      for (const item of items) html += `<li class="action">${esc(item)}</li>`;
      html += "</ul>";
      nextEl.innerHTML = html;
    } else {
      nextEl.innerHTML = '<div style="font-size:12px;color:var(--text-secondary)">暂无待执行的学习动作</div>';
    }
  }

  // Summary
  const summaryEl = document.getElementById("impactSummary");
  if (summaryEl) {
    summaryEl.textContent = report.user_visible_summary_zh || "";
  }
}

// Load impact report after V11 panels
if (runId) {
  setTimeout(() => loadImpactReport(runId), 2000);
}

// ==================================================================
// V11.3.1: Effectiveness Run Check — show badge if A/B data exists
// ==================================================================

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
    // Only show if there's actual comparison data
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

    // Insert after the status card
    const statusCard = document.getElementById("statusCard");
    if (statusCard && statusCard.parentNode) {
      statusCard.parentNode.appendChild(effBadge);
    }
  } catch (e) {
    // Silently ignore — effectiveness data may not exist yet
  }
}
